"""
Dashboard Routes

API endpoints for dashboard generation, refinement, and refresh.
All endpoints require authentication.
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from routes.auth import get_current_active_user, User
from langchain_agents.dashboard.models import (
    DashboardGenerateRequest,
    DashboardRefineRequest,
    DashboardRefreshRequest,
    DashboardResponse,
    LayoutUpdateRequest,
)
from langchain_agents.dashboard.graph import (
    run_dashboard_generation,
    run_dashboard_refresh,
)
from services.dashboard.session_service import (
    save_dashboard_session,
    get_dashboard_session,
    update_dashboard_session,
    update_dashboard_layout,
    list_dashboard_sessions,
    delete_dashboard_session,
)
from utilities import create_simple_logger

logger = create_simple_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# =============================================================================
# Chart Data Endpoint (URL-based data loading)
# =============================================================================

@router.get("/{session_id}/chart/{chart_id}/data")
async def get_chart_data(
    session_id: str,
    chart_id: str,
):
    """
    Get fresh data for a specific chart by executing its stored SQL query.
    
    NOTE: This endpoint does not require auth token because Vega can't pass
    headers with data fetches. The session_id (UUID) acts as an access token
    since it's only returned to authenticated users during dashboard generation.
    
    Returns:
        JSON array of data records
    """
    # Find the session across all users (session_id is globally unique UUID)
    # This is a simplified approach - in production you might want to store
    # session ownership differently
    from pymongo import MongoClient
    from env import MONGO_URI
    
    client = MongoClient(MONGO_URI)
    
    # Search for session across all user databases
    session = None
    connection_name = None
    username = None
    
    for db_name in client.list_database_names():
        if db_name.endswith("_dashboard"):
            db = client[db_name]
            if "sessions" in db.list_collection_names():
                found = db.sessions.find_one({"session_id": session_id})
                if found:
                    session = found
                    connection_name = found.get("connection_name")
                    username = db_name.replace("_dashboard", "")
                    break
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
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
    
    # Execute the query
    from services.database.db_connection_service import run_query_and_return_df, build_connection_string
    from services.database.db_config_models import get_db_config
    
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
    
    logger.info(f"Dashboard generation request from {username}: {request.user_prompt[:100]}...")
    
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
        
        # Build response
        from langchain_agents.dashboard.models import ComposedDashboardSpec, LayoutConfig, ChartLayoutPosition
        
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


@router.post("/refine", response_model=DashboardResponse)
async def refine_dashboard(
    request: DashboardRefineRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Refine an existing dashboard based on user feedback.
    
    Smart Refine Strategy:
    1. If `new_feedback` is present -> Run full LLM pipeline (Strategy -> Layout)
    2. If ONLY `filter_state` is present -> 
       a. Retrieve previous SQL queries
       b. Inject WHERE clauses (using subqueries)
       c. Re-run SQL only (via refresh logic)
       d. Update dashboard spec with new data
       e. Return fast result (~1s)
    
    Requires a valid session_id from a previous generation.
    """
    username = current_user.username
    session_id = request.session_id
    
    logger.info(f"Dashboard refinement request from {username}, session: {session_id}")
    
    # Get existing session
    session = get_dashboard_session(username, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    try:
        # 1. Full Refinement (LLM) if text feedback is provided
        if request.new_feedback:
            # Full refinement with LLM
            logger.info("Executing full LLM refinement based on text feedback")
            result = await run_dashboard_generation(
                user_prompt=f"{session['user_prompt']}\n\nRefinement: {request.new_feedback}",
                username=username,
                connection_name=session["connection_name"],
                session_id=session_id,
                max_charts=session.get("dashboard_spec", {}).get("chart_count", 5),
                theme=session.get("dashboard_spec", {}).get("theme", "default"),
            )
            
            if result.get("error"):
                return DashboardResponse(
                    success=False,
                    session_id=session_id,
                    dashboard=None,
                    error=result.get("error"),
                )
            
            dashboard_spec = result.get("dashboard_spec")
            
            # Update session
            update_dashboard_session(
                username=username,
                session_id=session_id,
                dashboard_spec=dashboard_spec,
                refinement_feedback=request.new_feedback,
            )
            
        # 2. Fast Filter Refresh (Data-only) if only filters are provided
        elif request.filter_state is not None:
            logger.info(f"Executing fast filter refresh with state: {request.filter_state}")
            
            from langchain_agents.dashboard.filter_utils import apply_filters_to_sql
            
            # Get original queries from session (preferred) or reconstruct from prompt
            # We need the original BASE queries without previous filters to stack correctly?
            # Actually, standard flow is: Base Query -> Apply Filter
            # If we refined before, we might be filtering a filtered query. 
            # For simplicity: We assume sql_queries in session are the "latest" base to work from.
            # Ideally, we should store "base_sql_queries" separately from "current_sql_queries".
            # BUT: refine() modifies the session. 
            
            # Strategy:
            # If we have tracked sql_queries in session, use them.
            # We will apply the NEW filters to these queries.
            # NOTE: If the stored queries ALREADY have filters, adding more wraps them again.
            # This is safe (nested subqueries), but can get deep. 
            # Ideally we'd persist 'base_queries' separately, but for now we'll wrap what we have.
            
            current_queries = session.get("sql_queries", [])
            if not current_queries:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No SQL queries found to filter. Try generating a new dashboard.",
                )
            
            # Apply filters to each query
            filtered_queries = []
            for q in current_queries:
                # q is {chart_id: "...", sql_query: "..."}
                # Handle both dict formats just in case
                chart_id = q.get("chart_id")
                original_sql = q.get("sql_query")
                
                if chart_id and original_sql:
                    new_sql = apply_filters_to_sql(original_sql, request.filter_state)
                    filtered_queries.append({
                        "chart_id": chart_id,
                        "sql_query": new_sql
                    })
            
            # Run the refresh logic with these NEW queries
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
                
            # Construct updated dashboard spec
            # Start with existing spec to preserve layout/titles/viz
            existing_spec = session.get("dashboard_spec", {})
            chart_data_results = result.get("chart_data_results", [])
            data_map = {r["chart_id"]: r["data"] for r in chart_data_results if not r.get("error")}
            
            # Update data in individual_specs
            individual_specs = existing_spec.get("individual_specs", [])
            updated_specs = []
            for spec in individual_specs:
                new_spec = spec.copy() # Shallow copy
                chart_id = new_spec.get("chart_id")
                if chart_id in data_map:
                    # deeply update data.values
                    new_spec["data"] = {"values": data_map[chart_id]}
                updated_specs.append(new_spec)
            
            # Update Vega-Lite spec if it exists (for legacy/concat)
            vega_lite_spec = existing_spec.get("vega_lite_spec", {})
            # (Simplification: assuming mostly individual_specs are used effectively by frontend now)
            
            # Create new ComposedDashboardSpec
            from langchain_agents.dashboard.models import ComposedDashboardSpec, LayoutConfig, ChartLayoutPosition
            
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
                vega_lite_spec=vega_lite_spec, # We aren't updating this deeply for now, relying on individual_specs
                individual_specs=updated_specs,
                layout_config=layout_config,
                layout_type=existing_spec.get("layout_type", "grid"),
                chart_count=existing_spec.get("chart_count", 0),
                sql_queries=current_queries, # KEEP ORIGINAL QUERIES so we don't permanently bake in filters?
                                             # OR should we update to filtered?
                                             # User feedback: "Drill down". Usually implies temporary view.
                                             # If we save filtered_queries, next drill down adds MORE wrappers.
                                             # DECISION: We do NOT save `filtered_queries` to session["sql_queries"].
                                             # We return the filtered dashboard, but session keeps base.
                                             # However, we DO update the dashboard_spec in session so reload shows state?
                                             # Complex. Let's return the filtered view but NOT persist it as the "base" 
                                             # for future refinements if possible.
                                             # ACTUALLY, for drill-down to work recursively (drill 1 -> drill 2), 
                                             # we normally pass the *accumulated* filter state from frontend.
                                             # Frontend sends {region: US, category: A}.
                                             # So we always apply to the *Base* queries?
                                             # YES. Frontend maintains full filter state.
                                             # So we should apply request.filter_state to session.sql_queries.
                                             # And we should NOT save the result back to session.sql_queries.
            )
            
            # We DO NOT call update_dashboard_session here to persist the filtered SQL as the new truth.
            # But we might want to persist the *View* state? 
            # For this MVP, let's keep it simple: We return the filtered view. 
            # Client has the filter state.
            
        else:
            # No refinement specified
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either new_feedback or filter_state must be provided",
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
        data_map = {r["chart_id"]: r["data"] for r in chart_data_results if not r.get("error")}
        
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
        
        from langchain_agents.dashboard.models import ComposedDashboardSpec, LayoutConfig, ChartLayoutPosition
        
        # Build layout_config if present
        layout_config_obj = None
        if layout_config:
            layout_config_obj = LayoutConfig(
                cols=layout_config.get("cols", 12),
                row_height=layout_config.get("row_height", 100),
                layout=[ChartLayoutPosition(**pos) for pos in layout_config.get("layout", [])],
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
        charts = (vega_spec.get("vconcat") or 
                 vega_spec.get("hconcat") or 
                 vega_spec.get("concat") or [])
        
        if charts:
            for i, chart in enumerate(charts):
                chart_copy = {**chart}
                chart_copy["chart_id"] = f"chart_{i+1}"
                chart_copy["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"
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
                layout_positions.append({
                    "i": spec["chart_id"],
                    "x": (i % 2) * 6,
                    "y": (i // 2) * 3,
                    "w": 6 if num_charts > 1 else 12,
                    "h": 3,
                    "minW": 3,
                    "minH": 2,
                })
            
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
