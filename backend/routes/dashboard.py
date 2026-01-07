"""
Dashboard Routes

API endpoints for dashboard generation, refinement, and refresh.
All endpoints require authentication.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from routes.auth import get_current_active_user, User
from langchain_agents.dashboard.models import (
    DashboardGenerateRequest,
    DashboardRefineRequest,
    DashboardRefreshRequest,
    DashboardResponse,
    LayoutUpdateRequest,
    DashboardFilterRequest,
    LayoutConfig,
    ChartLayoutPosition,
    ComposedDashboardSpec,
)
from langchain_agents.dashboard.filter_utils import apply_filters_to_sql
from langchain_agents.dashboard.graph import (
    run_dashboard_generation,
    run_dashboard_refresh,
    run_selective_refinement,
    stream_dashboard_generation,
)
from services.dashboard.session_service import (
    save_dashboard_session,
    get_dashboard_session,
    update_dashboard_session,
    update_dashboard_layout,
    update_chart_customizations,
    list_dashboard_sessions,
    delete_dashboard_session,
)
from langchain_agents.dashboard.agents.refinement_classifier import (
    classify_refinement_intent,
)
from services.database.db_connection_service import (
    run_query_and_return_df,
    build_connection_string,
)
from services.database.db_config_models import get_db_config
from services.sse_utils import (
    format_progress_event,
    format_complete_event,
    format_error_event,
)
from utilities import create_simple_logger

logger = create_simple_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _sanitize_for_json(data: list) -> list:
    """
    Sanitize data for JSON serialization.

    Handles types that are not natively JSON serializable:
    - Decimal -> float
    - datetime/date -> ISO string
    - bytes -> base64 string
    - NaN/Inf -> None
    """
    from decimal import Decimal
    from datetime import datetime, date
    import math

    def sanitize_value(val):
        if val is None:
            return None
        if isinstance(val, Decimal):
            return float(val)
        if isinstance(val, (datetime, date)):
            return val.isoformat()
        if isinstance(val, bytes):
            import base64

            return base64.b64encode(val).decode("utf-8")
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return None
        return val

    return [{k: sanitize_value(v) for k, v in row.items()} for row in data]


# =============================================================================
# Chart Data Endpoint (URL-based data loading)
# =============================================================================


@router.get("/{session_id}/chart/{chart_id}/data")
async def get_chart_data(
    session_id: str,
    chart_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get fresh data for a specific chart by executing its stored SQL query.

    This endpoint requires authentication via Bearer token.
    The frontend configures Vega with a custom loader that includes the auth header.

    Returns:
        JSON array of data records
    """
    username = current_user.username

    # Get session for this user
    session = get_dashboard_session(username, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    connection_name = session.get("connection_name")

    # Find the SQL query for this chart
    sql_queries = session.get("sql_queries", [])
    sql_query = None
    for q in sql_queries:
        if q.get("chart_id") == chart_id:
            sql_query = q.get("sql_query")
            break

    if not sql_query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No SQL query found for chart {chart_id}",
        )

    # Get database configuration
    db_config = get_db_config(username, connection_name)
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database configuration not found for {connection_name}",
        )

    connection_string = build_connection_string(**db_config)

    try:
        result = run_query_and_return_df(connection_string, sql_query)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to execute query",
            )

        # Convert DataFrame to list of dicts
        data = result.to_dict(orient="records")

        # Sanitize data for JSON serialization (handle Decimal, datetime, etc.)
        data = _sanitize_for_json(data)

        # Return as JSON array (Vega expects array format)
        return JSONResponse(content=data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chart data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{session_id}/chart/{chart_id}")
async def delete_chart(
    session_id: str,
    chart_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a specific chart from a dashboard.

    This directly removes the chart without LLM calls - useful for quick deletions.
    """
    username = current_user.username

    # Get session
    session = get_dashboard_session(username, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    dashboard_spec = session.get("dashboard_spec", {})
    sql_queries = session.get("sql_queries", [])
    chart_goals = session.get("chart_goals", [])

    # Check if chart exists
    individual_specs = dashboard_spec.get("individual_specs", [])
    chart_exists = any(s.get("chart_id") == chart_id for s in individual_specs)

    if not chart_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart {chart_id} not found in dashboard",
        )

    # Remove from individual_specs
    dashboard_spec["individual_specs"] = [
        s for s in individual_specs if s.get("chart_id") != chart_id
    ]

    # Remove from layout
    if dashboard_spec.get("layout_config"):
        dashboard_spec["layout_config"]["layout"] = [
            l
            for l in dashboard_spec["layout_config"].get("layout", [])
            if l.get("i") != chart_id
        ]

    # Remove from sql_queries
    sql_queries = [q for q in sql_queries if q.get("chart_id") != chart_id]

    # Remove from chart_goals
    chart_goals = [g for g in chart_goals if g.get("chart_id") != chart_id]

    # Update chart count
    dashboard_spec["chart_count"] = len(dashboard_spec.get("individual_specs", []))

    # Save updated session
    update_dashboard_session(
        username=username,
        session_id=session_id,
        dashboard_spec=dashboard_spec,
        chart_goals=chart_goals,
    )

    # Also update sql_queries in dashboard_spec for consistency
    dashboard_spec["sql_queries"] = sql_queries

    logger.info(f"Deleted chart {chart_id} from session {session_id}")

    # Build response with updated dashboard
    layout_config = None
    if dashboard_spec.get("layout_config"):
        lc = dashboard_spec["layout_config"]
        layout_config = LayoutConfig(
            cols=lc.get("cols", 12),
            row_height=lc.get("row_height", 100),
            layout=[ChartLayoutPosition(**pos) for pos in lc.get("layout", [])],
            custom=lc.get("custom", False),
        )

    response_dashboard = ComposedDashboardSpec(
        title=dashboard_spec.get("title", "Dashboard"),
        description=dashboard_spec.get("description"),
        vega_lite_spec=dashboard_spec.get("vega_lite_spec", {}),
        individual_specs=dashboard_spec.get("individual_specs", []),
        chart_count=dashboard_spec.get("chart_count", 0),
        layout_config=layout_config,
        sql_queries=sql_queries,
    )

    return DashboardResponse(
        success=True,
        session_id=session_id,
        dashboard=response_dashboard,
    )


# =============================================================================
# Main Endpoints
# =============================================================================


@router.post("/generate", response_model=DashboardResponse)
async def generate_dashboard(
    request: DashboardGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate a dashboard from a natural language prompt.

    This runs the full 4-agent pipeline:
    1. Strategy Agent: Plans chart objectives
    2. Data Agent: Generates and executes SQL
    3. Viz Spec Agent: Creates Vega-Lite specs
    4. Layout Agent: Composes final dashboard

    Returns:
        DashboardResponse with the generated Vega-Lite specification
    """
    username = current_user.username
    session_id = str(uuid.uuid4())

    logger.info(
        f"Dashboard generation request from {username}: {request.user_prompt[:100]}..."
    )

    try:
        # Run the generation pipeline
        result = await run_dashboard_generation(
            user_prompt=request.user_prompt,
            username=username,
            connection_name=request.connection_name,
            session_id=session_id,
            max_charts=request.max_charts,
            theme=request.theme or "default",
        )

        # Check for errors
        if result.get("error"):
            return DashboardResponse(
                success=False,
                session_id=session_id,
                dashboard=None,
                error=result.get("error"),
                generation_time_ms=result.get("total_time_ms"),
            )

        # Get the dashboard spec
        dashboard_spec = result.get("dashboard_spec")

        if not dashboard_spec:
            return DashboardResponse(
                success=False,
                session_id=session_id,
                dashboard=None,
                error="No dashboard was generated",
                generation_time_ms=result.get("total_time_ms"),
            )

        # Save session for future refinement/refresh
        try:
            save_dashboard_session(
                username=username,
                session_id=session_id,
                user_prompt=request.user_prompt,
                connection_name=request.connection_name,
                dashboard_spec=dashboard_spec,
                chart_goals=result.get("chart_goals", []),
                sql_queries=dashboard_spec.get("sql_queries", []),
                generation_time_ms=result.get("total_time_ms", 0),
            )
            logger.info(f"Dashboard session {session_id} saved to MongoDB")
        except Exception as save_error:
            logger.error(f"Failed to save dashboard session: {save_error}")

        # Build layout_config if present
        layout_config = None
        if dashboard_spec.get("layout_config"):
            lc = dashboard_spec["layout_config"]
            layout_config = LayoutConfig(
                cols=lc.get("cols", 12),
                row_height=lc.get("row_height", 100),
                layout=[ChartLayoutPosition(**pos) for pos in lc.get("layout", [])],
                custom=lc.get("custom", False),
            )

        return DashboardResponse(
            success=True,
            session_id=session_id,
            dashboard=ComposedDashboardSpec(
                title=dashboard_spec.get("title", "Dashboard"),
                description=dashboard_spec.get("description"),
                vega_lite_spec=dashboard_spec.get("vega_lite_spec", {}),
                individual_specs=dashboard_spec.get("individual_specs", []),
                layout_config=layout_config,
                layout_type=dashboard_spec.get("layout_type", "grid"),
                chart_count=dashboard_spec.get("chart_count", 0),
                sql_queries=dashboard_spec.get("sql_queries", []),
            ),
            error=None,
            generation_time_ms=result.get("total_time_ms"),
        )

    except Exception as e:
        logger.exception(f"Dashboard generation failed: {e}")
        return DashboardResponse(
            success=False,
            session_id=session_id,
            dashboard=None,
            error=str(e),
        )


@router.post("/generate/stream")
async def generate_dashboard_stream(
    request: DashboardGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate a dashboard with real-time progress updates via SSE.

    Returns a Server-Sent Events stream with:
    - 'progress' events: {stage, progress, message, details}
    - 'complete' event: {success, session_id, dashboard, ...}
    - 'error' event: {error, failed_stage}
    """
    username = current_user.username
    session_id = str(uuid.uuid4())

    logger.info(
        f"Streaming dashboard generation request from {username}: {request.user_prompt[:100]}..."
    )

    async def event_generator():
        async for event in stream_dashboard_generation(
            user_prompt=request.user_prompt,
            username=username,
            connection_name=request.connection_name,
            session_id=session_id,
            max_charts=request.max_charts,
            theme=request.theme or "default",
        ):
            event_type = event.get("type")

            if event_type == "progress":
                yield format_progress_event(
                    stage=event["stage"],
                    progress=event["progress"],
                    message=event["message"],
                    details=event.get("details"),
                )

            elif event_type == "complete":
                result = event["result"]
                dashboard_spec = result.get("dashboard_spec")

                # Save session (same as non-streaming endpoint)
                if dashboard_spec:
                    try:
                        save_dashboard_session(
                            username=username,
                            session_id=session_id,
                            user_prompt=request.user_prompt,
                            connection_name=request.connection_name,
                            dashboard_spec=dashboard_spec,
                            chart_goals=result.get("chart_goals", []),
                            sql_queries=dashboard_spec.get("sql_queries", []),
                            generation_time_ms=result.get("total_time_ms", 0),
                        )
                        logger.info(f"Dashboard session {session_id} saved to MongoDB")
                    except Exception as save_error:
                        logger.error(f"Failed to save session: {save_error}")

                # Build response (same structure as non-streaming)
                layout_config = None
                if dashboard_spec and dashboard_spec.get("layout_config"):
                    lc = dashboard_spec["layout_config"]
                    layout_config = {
                        "cols": lc.get("cols", 12),
                        "row_height": lc.get("row_height", 100),
                        "layout": lc.get("layout", []),
                        "custom": lc.get("custom", False),
                    }

                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "dashboard": (
                        {
                            "title": (
                                dashboard_spec.get("title", "Dashboard")
                                if dashboard_spec
                                else None
                            ),
                            "description": (
                                dashboard_spec.get("description")
                                if dashboard_spec
                                else None
                            ),
                            "vega_lite_spec": (
                                dashboard_spec.get("vega_lite_spec", {})
                                if dashboard_spec
                                else {}
                            ),
                            "individual_specs": (
                                dashboard_spec.get("individual_specs", [])
                                if dashboard_spec
                                else []
                            ),
                            "layout_config": layout_config,
                            "layout_type": (
                                dashboard_spec.get("layout_type", "grid")
                                if dashboard_spec
                                else "grid"
                            ),
                            "chart_count": (
                                dashboard_spec.get("chart_count", 0)
                                if dashboard_spec
                                else 0
                            ),
                            "sql_queries": (
                                dashboard_spec.get("sql_queries", [])
                                if dashboard_spec
                                else []
                            ),
                        }
                        if dashboard_spec
                        else None
                    ),
                    "generation_time_ms": result.get("total_time_ms"),
                }

                yield format_complete_event(response_data)

            elif event_type == "error":
                yield format_error_event(
                    error=event["error"],
                    stage=event.get("stage"),
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/refine", response_model=DashboardResponse)
async def refine_dashboard(
    request: DashboardRefineRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Smart refinement of an existing dashboard based on user feedback.

    Uses Intent Classification to determine what changes are needed:
    1. Classify user feedback into specific actions
    2. If clarification needed, return question to user
    3. Execute only the required pipeline stages
    4. Return updated dashboard

    Requires a valid session_id from a previous generation.
    """
    username = current_user.username
    session_id = request.session_id

    logger.info(f"Smart refinement request from {username}, session: {session_id}")

    # Validate feedback is provided
    if not request.new_feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback is required for refinement. Use /filter endpoint for filter-only updates.",
        )

    # Get existing session
    session = get_dashboard_session(username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    try:
        current_dashboard = session.get("dashboard_spec", {})
        chart_goals = session.get("chart_goals", [])
        sql_queries = session.get("sql_queries", [])

        # Step 1: Classify the user's intent
        intent = await classify_refinement_intent(
            user_feedback=request.new_feedback,
            current_dashboard=current_dashboard,
            chart_goals=chart_goals,
            target_chart_hint=request.target_chart_id,
        )

        # Step 2: If clarification is needed, return the question
        if intent.requires_clarification:
            logger.info(f"Clarification needed: {intent.clarification_question}")
            # Return a special response indicating clarification is needed
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "session_id": session_id,
                    "dashboard": None,
                    "error": None,
                    "requires_clarification": True,
                    "clarification_question": intent.clarification_question,
                    "reasoning": intent.reasoning,
                },
            )

        # Step 3: Execute selective refinement based on classified actions
        logger.info(f"Executing {len(intent.actions)} refinement actions")

        result = await run_selective_refinement(
            session_id=session_id,
            username=username,
            connection_name=session["connection_name"],
            actions=intent.actions,
            current_dashboard=current_dashboard,
            chart_goals=chart_goals,
            sql_queries=sql_queries,
            user_feedback=request.new_feedback,
            original_prompt=session.get("user_prompt", ""),
        )

        if result.get("error"):
            return DashboardResponse(
                success=False,
                session_id=session_id,
                dashboard=None,
                error=result.get("error"),
            )

        dashboard_spec = result.get("dashboard_spec")

        # Ensure sql_queries are in dashboard_spec before saving
        if result.get("updated_sql_queries"):
            if isinstance(dashboard_spec, dict):
                dashboard_spec["sql_queries"] = result["updated_sql_queries"]

        # Update session with new dashboard and chart_goals
        update_dashboard_session(
            username=username,
            session_id=session_id,
            dashboard_spec=(
                dashboard_spec
                if isinstance(dashboard_spec, dict)
                else (
                    dashboard_spec.model_dump()
                    if hasattr(dashboard_spec, "model_dump")
                    else dashboard_spec
                )
            ),
            refinement_feedback=request.new_feedback,
            chart_goals=result.get("updated_chart_goals"),
        )

        # Build response
        if isinstance(dashboard_spec, dict):
            # Parse layout config
            layout_config = None
            if dashboard_spec.get("layout_config"):
                lc = dashboard_spec["layout_config"]
                layout_config = LayoutConfig(
                    cols=lc.get("cols", 12),
                    row_height=lc.get("row_height", 100),
                    layout=[ChartLayoutPosition(**pos) for pos in lc.get("layout", [])],
                    custom=lc.get("custom", False),
                )

            dashboard_spec = ComposedDashboardSpec(
                title=dashboard_spec.get("title", "Dashboard"),
                description=dashboard_spec.get("description"),
                vega_lite_spec=dashboard_spec.get("vega_lite_spec", {}),
                individual_specs=dashboard_spec.get("individual_specs", []),
                layout_config=layout_config,
                layout_type=dashboard_spec.get("layout_type", "grid"),
                chart_count=dashboard_spec.get("chart_count", 0),
                sql_queries=result.get("updated_sql_queries", sql_queries),
            )

        return DashboardResponse(
            success=True,
            session_id=session_id,
            dashboard=dashboard_spec,
            error=None,
            generation_time_ms=result.get("total_time_ms", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Dashboard refinement failed: {e}")
        return DashboardResponse(
            success=False,
            session_id=session_id,
            dashboard=None,
            error=str(e),
        )


@router.post("/filter", response_model=DashboardResponse)
async def filter_dashboard(
    request: "DashboardFilterRequest",
    current_user: User = Depends(get_current_active_user),
):
    """
    Apply filters to dashboard charts without LLM processing.

    This is a fast endpoint (~1s) for drill-down filtering:
    1. Retrieve stored SQL queries
    2. Inject WHERE clauses using subqueries
    3. Re-execute SQL to get filtered data
    4. Return updated dashboard with filtered data

    Note: Filters are NOT persisted to session. Frontend maintains filter state.
    """

    username = current_user.username
    session_id = request.session_id

    logger.info(
        f"Filter request from {username}, session: {session_id}, filters: {request.filter_state}"
    )

    # Get existing session
    session = get_dashboard_session(username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    try:
        current_queries = session.get("sql_queries", [])
        if not current_queries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No SQL queries found to filter. Try generating a new dashboard.",
            )

        # Apply filters to each query
        filtered_queries = []
        for q in current_queries:
            chart_id = q.get("chart_id")
            original_sql = q.get("sql_query")

            if chart_id and original_sql:
                new_sql = apply_filters_to_sql(original_sql, request.filter_state)
                filtered_queries.append({"chart_id": chart_id, "sql_query": new_sql})

        # Run the refresh logic with filtered queries
        result = await run_dashboard_refresh(
            session_id=session_id,
            username=username,
            connection_name=session["connection_name"],
            sql_queries=filtered_queries,
        )

        if result.get("error"):
            return DashboardResponse(
                success=False,
                session_id=session_id,
                dashboard=None,
                error=result.get("error"),
            )

        # Construct updated dashboard spec (preserving layout/viz)
        existing_spec = session.get("dashboard_spec", {})
        chart_data_results = result.get("chart_data_results", [])
        data_map = {
            r["chart_id"]: r["data"] for r in chart_data_results if not r.get("error")
        }

        # Update data in individual_specs
        individual_specs = existing_spec.get("individual_specs", [])
        updated_specs = []
        for spec in individual_specs:
            new_spec = spec.copy()
            chart_id = new_spec.get("chart_id")
            if chart_id in data_map:
                new_spec["data"] = {"values": data_map[chart_id]}
            updated_specs.append(new_spec)

        # Parse layout config
        layout_config = None
        if existing_spec.get("layout_config"):
            lc = existing_spec["layout_config"]
            layout_config = LayoutConfig(
                cols=lc.get("cols", 12),
                row_height=lc.get("row_height", 100),
                layout=[ChartLayoutPosition(**pos) for pos in lc.get("layout", [])],
                custom=lc.get("custom", False),
            )

        dashboard_spec = ComposedDashboardSpec(
            title=existing_spec.get("title", "Dashboard"),
            description=existing_spec.get("description"),
            vega_lite_spec=existing_spec.get("vega_lite_spec", {}),
            individual_specs=updated_specs,
            layout_config=layout_config,
            layout_type=existing_spec.get("layout_type", "grid"),
            chart_count=existing_spec.get("chart_count", 0),
            sql_queries=current_queries,  # Keep original queries (filters not persisted)
        )

        return DashboardResponse(
            success=True,
            session_id=session_id,
            dashboard=dashboard_spec,
            error=None,
            generation_time_ms=result.get("total_time_ms", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Dashboard filtering failed: {e}")
        return DashboardResponse(
            success=False,
            session_id=session_id,
            dashboard=None,
            error=str(e),
        )


@router.post("/refresh", response_model=DashboardResponse)
async def refresh_dashboard(
    request: DashboardRefreshRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Refresh dashboard data without re-running LLM agents.

    This re-executes the stored SQL queries to fetch fresh data,
    keeping the same visualization structure.
    """
    username = current_user.username
    session_id = request.session_id

    logger.info(f"Dashboard refresh request from {username}, session: {session_id}")

    # Get existing session
    session = get_dashboard_session(username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    try:
        sql_queries = session.get("sql_queries", [])

        if not sql_queries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No SQL queries stored for this session",
            )

        # Re-execute queries
        result = await run_dashboard_refresh(
            session_id=session_id,
            username=username,
            connection_name=session["connection_name"],
            sql_queries=sql_queries,
        )

        if result.get("error"):
            return DashboardResponse(
                success=False,
                session_id=session_id,
                dashboard=None,
                error=result.get("error"),
            )

        # Update the dashboard spec with fresh data
        dashboard_spec = session.get("dashboard_spec", {})
        chart_data_results = result.get("chart_data_results", [])

        # Update data in viz specs
        vega_lite_spec = dashboard_spec.get("vega_lite_spec", {})

        # Map new data by chart_id
        data_map = {
            r["chart_id"]: r["data"] for r in chart_data_results if not r.get("error")
        }

        # Update data in the spec (simplified - full implementation would traverse the spec)
        for key in ["hconcat", "vconcat"]:
            if key in vega_lite_spec:
                for i, chart in enumerate(vega_lite_spec[key]):
                    chart_id = f"chart_{i+1}"
                    if chart_id in data_map:
                        if "data" in chart:
                            chart["data"]["values"] = data_map[chart_id]

        # Also update data in individual_specs (for flexible layout)
        individual_specs = dashboard_spec.get("individual_specs", [])
        for spec in individual_specs:
            chart_id = spec.get("chart_id")
            if chart_id and chart_id in data_map:
                if "data" in spec:
                    spec["data"]["values"] = data_map[chart_id]
                else:
                    spec["data"] = {"values": data_map[chart_id]}

        # Preserve existing layout_config
        layout_config = dashboard_spec.get("layout_config")

        # Update session with refreshed data
        update_dashboard_session(
            username=username,
            session_id=session_id,
            dashboard_spec=dashboard_spec,
        )

        # Build layout_config if present
        layout_config_obj = None
        if layout_config:
            layout_config_obj = LayoutConfig(
                cols=layout_config.get("cols", 12),
                row_height=layout_config.get("row_height", 100),
                layout=[
                    ChartLayoutPosition(**pos)
                    for pos in layout_config.get("layout", [])
                ],
                custom=layout_config.get("custom", False),
            )

        return DashboardResponse(
            success=True,
            session_id=session_id,
            dashboard=ComposedDashboardSpec(
                title=dashboard_spec.get("title", "Dashboard"),
                description=dashboard_spec.get("description"),
                vega_lite_spec=vega_lite_spec,
                individual_specs=individual_specs,
                layout_config=layout_config_obj,
                layout_type=dashboard_spec.get("layout_type", "grid"),
                chart_count=dashboard_spec.get("chart_count", 0),
                sql_queries=sql_queries,
            ),
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Dashboard refresh failed: {e}")
        return DashboardResponse(
            success=False,
            session_id=session_id,
            dashboard=None,
            error=str(e),
        )


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    skip: int = 0,
    current_user: User = Depends(get_current_active_user),
):
    """List all dashboard sessions for the current user."""
    sessions = list_dashboard_sessions(
        username=current_user.username,
        limit=limit,
        skip=skip,
    )
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific dashboard session."""
    session = get_dashboard_session(current_user.username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Migrate old dashboard format to new format if needed
    dashboard_spec = session.get("dashboard_spec", {})
    if dashboard_spec and not dashboard_spec.get("individual_specs"):
        # Extract individual charts from vega_lite_spec if it uses concat
        vega_spec = dashboard_spec.get("vega_lite_spec", {})
        individual_specs = []

        # Check for vconcat, hconcat, or concat
        charts = (
            vega_spec.get("vconcat")
            or vega_spec.get("hconcat")
            or vega_spec.get("concat")
            or []
        )

        if charts:
            for i, chart in enumerate(charts):
                chart_copy = {**chart}
                chart_copy["chart_id"] = f"chart_{i+1}"
                chart_copy["$schema"] = (
                    "https://vega.github.io/schema/vega-lite/v6.json"
                )
                chart_copy["width"] = "container"
                chart_copy["height"] = "container"
                chart_copy["autosize"] = {"type": "fit", "contains": "padding"}
                individual_specs.append(chart_copy)
        elif vega_spec:
            # Single chart dashboard
            chart_copy = {**vega_spec}
            chart_copy["chart_id"] = "chart_1"
            chart_copy["width"] = "container"
            chart_copy["height"] = "container"
            chart_copy["autosize"] = {"type": "fit", "contains": "padding"}
            individual_specs.append(chart_copy)

        if individual_specs:
            # Generate default layout
            layout_positions = []
            num_charts = len(individual_specs)
            for i, spec in enumerate(individual_specs):
                # Simple 2-column layout
                layout_positions.append(
                    {
                        "i": spec["chart_id"],
                        "x": (i % 2) * 6,
                        "y": (i // 2) * 3,
                        "w": 6 if num_charts > 1 else 12,
                        "h": 3,
                        "minW": 3,
                        "minH": 2,
                    }
                )

            dashboard_spec["individual_specs"] = individual_specs
            dashboard_spec["layout_config"] = {
                "cols": 12,
                "row_height": 100,
                "layout": layout_positions,
                "custom": False,
            }
            session["dashboard_spec"] = dashboard_spec

    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a dashboard session."""
    deleted = delete_dashboard_session(current_user.username, session_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    return {"message": "Session deleted", "session_id": session_id}


@router.patch("/sessions/{session_id}/layout")
async def update_layout(
    session_id: str,
    request: LayoutUpdateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Update the layout configuration for a dashboard session.

    This endpoint is called when the user customizes the layout
    by dragging/resizing charts in the frontend.

    The layout is marked as 'custom: true' to indicate user modifications.
    """
    username = current_user.username

    logger.info(f"Layout update request from {username} for session: {session_id}")

    # Check if session exists
    session = get_dashboard_session(username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Update the layout
    layout_dict = request.layout_config.model_dump()
    updated = update_dashboard_layout(username, session_id, layout_dict)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update layout",
        )

    return {
        "success": True,
        "message": "Layout updated successfully",
        "session_id": session_id,
    }


@router.patch("/sessions/{session_id}/customizations")
async def update_chart_customizations_route(
    session_id: str,
    request: dict,
    current_user: User = Depends(get_current_active_user),
):
    """
    Update chart customizations for a dashboard session.

    Stores user's visual preferences (colors, themes, axis settings)
    for charts in MongoDB.
    """
    username = current_user.username

    logger.info(f"Chart customization update from {username} for session: {session_id}")

    # Check if session exists
    session = get_dashboard_session(username, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Get customizations from request body
    customizations = request.get("customizations", {})

    # Update the customizations
    updated = update_chart_customizations(username, session_id, customizations)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update customizations",
        )

    return {
        "success": True,
        "message": "Customizations updated successfully",
        "session_id": session_id,
    }
