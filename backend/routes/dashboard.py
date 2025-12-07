"""
Dashboard Routes

API endpoints for dashboard generation, refinement, and refresh.
All endpoints require authentication.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

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
    
    This can:
    - Update chart types, layouts, or styling
    - Apply new filters
    - Regenerate specific charts
    
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
        # Determine what kind of refinement is needed
        if request.new_feedback:
            # Full refinement with LLM
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
            
        elif request.filter_state:
            # For filter changes, we could re-run Data Agent only
            # For now, do a full regeneration with filter context
            filter_desc = ", ".join([f"{k}={v}" for k, v in request.filter_state.items()])
            
            result = await run_dashboard_generation(
                user_prompt=f"{session['user_prompt']}\n\nFilter: {filter_desc}",
                username=username,
                connection_name=session["connection_name"],
                session_id=session_id,
            )
            
            if result.get("error"):
                return DashboardResponse(
                    success=False,
                    session_id=session_id,
                    dashboard=None,
                    error=result.get("error"),
                )
            
            dashboard_spec = result.get("dashboard_spec")
            
            update_dashboard_session(
                username=username,
                session_id=session_id,
                dashboard_spec=dashboard_spec,
            )
        else:
            # No refinement specified
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either new_feedback or filter_state must be provided",
            )
        
        from langchain_agents.dashboard.models import ComposedDashboardSpec
        
        return DashboardResponse(
            success=True,
            session_id=session_id,
            dashboard=ComposedDashboardSpec(
                title=dashboard_spec.get("title", "Dashboard"),
                description=dashboard_spec.get("description"),
                vega_lite_spec=dashboard_spec.get("vega_lite_spec", {}),
                layout_type=dashboard_spec.get("layout_type", "vconcat"),
                chart_count=dashboard_spec.get("chart_count", 0),
                sql_queries=dashboard_spec.get("sql_queries", []),
            ),
            error=None,
            generation_time_ms=result.get("total_time_ms"),
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
