"""
Pydantic Models for Dashboard Generation Pipeline.

This module defines all data models used across the dashboard generation agents:
- ChartGoal: Output of Strategy Agent
- ChartDataResult: Output of Data Agent  
- SingleVizSpec: Output of Viz Spec Agent
- ComposedDashboardSpec: Output of Layout Agent
- API Request/Response models
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ChartType(str, Enum):
    """Supported chart types for Vega-Lite visualization."""
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "arc"
    SCATTER = "point"
    KPI = "text"
    HEATMAP = "rect"


class AggregationType(str, Enum):
    """Supported aggregation functions."""
    SUM = "sum"
    COUNT = "count"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    DISTINCT = "distinct"
    NONE = "none"


class ChartGoal(BaseModel):
    """
    Output schema for Strategy Agent.
    Describes a single chart objective within the dashboard.
    """
    chart_id: str = Field(..., description="Unique identifier for this chart")
    chart_type: ChartType = Field(..., description="Type of visualization")
    title: str = Field(..., description="Chart title")
    description: str = Field(..., description="What this chart shows")
    
    # Data requirements
    x_field: Optional[str] = Field(None, description="Field for X axis")
    y_field: Optional[str] = Field(None, description="Field for Y axis (value)")
    color_field: Optional[str] = Field(None, description="Field for color encoding")
    aggregation: AggregationType = Field(default=AggregationType.NONE, description="Aggregation to apply")
    
    # Filters
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Any filters to apply")
    
    # Tables to use
    tables: List[str] = Field(..., description="Tables needed for this chart")
    
    # Priority for layout
    priority: int = Field(default=1, description="Display priority (1=highest)")


class StrategyAgentOutput(BaseModel):
    """Complete output from Strategy Agent."""
    chart_goals: List[ChartGoal] = Field(..., description="List of 3-5 chart objectives")
    reasoning: str = Field(..., description="Explanation of the strategy")


class ChartDataResult(BaseModel):
    """
    Output schema for Data Agent.
    Contains the fetched data and SQL for a single chart.
    """
    chart_id: str = Field(..., description="Chart ID this data is for")
    sql_query: str = Field(..., description="SQL query executed")
    data: List[Dict[str, Any]] = Field(..., description="Raw data as list of dicts")
    columns: List[str] = Field(..., description="Column names in order")
    row_count: int = Field(..., description="Number of rows fetched")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: Optional[float] = Field(None, description="Query execution time")


class DataAgentOutput(BaseModel):
    """Complete output from Data Agent."""
    chart_data_results: List[ChartDataResult] = Field(..., description="Data for all charts")
    total_execution_time_ms: float = Field(..., description="Total time for all queries")


class VegaLiteEncoding(BaseModel):
    """Vega-Lite encoding specification."""
    field: str = Field(..., description="Data field name")
    type: str = Field(..., description="Data type: quantitative, nominal, ordinal, temporal")
    aggregate: Optional[str] = Field(None, description="Aggregation function")
    title: Optional[str] = Field(None, description="Axis/legend title")
    format: Optional[str] = Field(None, description="Format string")


class SingleVizSpec(BaseModel):
    """
    Output schema for Viz Spec Agent.
    A single Vega-Lite chart specification.
    """
    chart_id: str = Field(..., description="Chart ID this spec is for")
    
    # Core Vega-Lite spec structure
    mark: Dict[str, Any] = Field(..., description="Vega-Lite mark specification")
    encoding: Dict[str, Any] = Field(..., description="Vega-Lite encoding channels")
    
    # Embedded data
    data: Dict[str, Any] = Field(..., description="Vega-Lite data object with values")
    
    # Optional properties
    title: Optional[str] = Field(None, description="Chart title")
    width: Optional[int] = Field(None, description="Chart width")
    height: Optional[int] = Field(None, description="Chart height")
    
    # Selection for interactivity
    selection: Optional[Dict[str, Any]] = Field(None, description="Vega-Lite selection definitions")
    
    # Additional properties
    config: Optional[Dict[str, Any]] = Field(None, description="Chart configuration")
    
    def to_vega_lite_dict(self) -> Dict[str, Any]:
        """Convert to a complete Vega-Lite specification dict."""
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "mark": self.mark,
            "encoding": self.encoding,
            "data": self.data,
        }
        if self.title:
            spec["title"] = self.title
        if self.width:
            spec["width"] = self.width
        if self.height:
            spec["height"] = self.height
        if self.selection:
            spec["selection"] = self.selection
        if self.config:
            spec["config"] = self.config
        return spec


class VizSpecAgentOutput(BaseModel):
    """Complete output from Viz Spec Agent."""
    viz_specs: List[SingleVizSpec] = Field(..., description="Vega-Lite specs for all charts")


class LayoutType(str, Enum):
    """Layout arrangement options."""
    HCONCAT = "hconcat"
    VCONCAT = "vconcat"
    GRID = "grid"
    SINGLE = "single"


class ChartLayoutPosition(BaseModel):
    """
    Position and size of a chart in the react-grid-layout.
    
    Uses react-grid-layout coordinate system:
    - i: unique chart identifier
    - x, y: grid position (column, row)
    - w, h: width and height in grid units
    """
    i: str = Field(..., description="Unique chart identifier (chart_id)")
    x: int = Field(0, ge=0, description="Column position (0-indexed)")
    y: int = Field(0, ge=0, description="Row position (0-indexed)")
    w: int = Field(1, ge=1, le=12, description="Width in grid units (1-12)")
    h: int = Field(1, ge=1, description="Height in grid units")
    minW: Optional[int] = Field(1, description="Minimum width")
    minH: Optional[int] = Field(1, description="Minimum height")
    static: bool = Field(False, description="If true, item cannot be dragged/resized")


class LayoutConfig(BaseModel):
    """
    Complete layout configuration for a dashboard.
    Compatible with react-grid-layout format.
    """
    cols: int = Field(12, ge=1, le=24, description="Total grid columns (default 12 for react-grid-layout)")
    row_height: int = Field(100, description="Height of each row in pixels")
    layout: List[ChartLayoutPosition] = Field(default_factory=list, description="Position of each chart")
    custom: bool = Field(False, description="Whether user has customized this layout")
    
    class Config:
        json_schema_extra = {
            "example": {
                "cols": 12,
                "row_height": 100,
                "layout": [
                    {"i": "chart_1", "x": 0, "y": 0, "w": 4, "h": 2},
                    {"i": "chart_2", "x": 4, "y": 0, "w": 4, "h": 2},
                    {"i": "chart_3", "x": 8, "y": 0, "w": 4, "h": 2},
                ],
                "custom": False
            }
        }


class ComposedDashboardSpec(BaseModel):
    """
    Output schema for Layout Agent.
    The final composed Vega-Lite dashboard specification.
    """
    # Dashboard metadata
    title: str = Field(..., description="Dashboard title")
    description: Optional[str] = Field(None, description="Dashboard description")
    
    # Full Vega-Lite specification (for backward compatibility)
    vega_lite_spec: Dict[str, Any] = Field(default_factory=dict, description="Complete Vega-Lite JSON")
    
    # NEW: Individual chart specs for flexible layout
    individual_specs: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Individual Vega-Lite specs for each chart"
    )
    
    # NEW: Grid layout configuration
    layout_config: Optional[LayoutConfig] = Field(
        None, 
        description="react-grid-layout compatible layout configuration"
    )
    
    # Layout info
    layout_type: LayoutType = Field(default=LayoutType.GRID, description="Layout arrangement used")
    chart_count: int = Field(..., description="Number of charts in dashboard")
    
    # Metadata for refresh/refine
    sql_queries: List[Dict[str, str]] = Field(default_factory=list, description="SQL queries by chart_id for refresh")
    
    # Timestamps
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_json(self) -> Dict[str, Any]:
        """Return the full specification as JSON-serializable dict."""
        result = {
            "title": self.title,
            "description": self.description,
            "vega_lite_spec": self.vega_lite_spec,
            "individual_specs": self.individual_specs,
            "layout_type": self.layout_type.value,
            "chart_count": self.chart_count,
            "sql_queries": self.sql_queries,
            "generated_at": self.generated_at.isoformat(),
        }
        if self.layout_config:
            result["layout_config"] = self.layout_config.model_dump()
        return result


# =============================================================================
# API Request/Response Models
# =============================================================================

class DashboardGenerateRequest(BaseModel):
    """Request model for /api/dashboard/generate endpoint."""
    user_prompt: str = Field(..., description="Natural language request for dashboard")
    connection_name: str = Field(..., description="Database connection to use")
    
    # Optional configuration
    max_charts: int = Field(default=5, ge=1, le=10, description="Maximum charts to generate")
    theme: Optional[str] = Field(default="default", description="Dashboard theme")


class DashboardRefineRequest(BaseModel):
    """Request model for /api/dashboard/refine endpoint."""
    session_id: str = Field(..., description="Session ID from previous generation")
    
    # Refinement options (at least one required)
    new_feedback: Optional[str] = Field(None, description="Text feedback for refinement")
    filter_state: Optional[Dict[str, Any]] = Field(None, description="New filter values")
    
    # Specific chart to refine
    target_chart_id: Optional[str] = Field(None, description="Specific chart to modify")


class DashboardRefreshRequest(BaseModel):
    """Request model for /api/dashboard/refresh endpoint."""
    session_id: str = Field(..., description="Session ID to refresh data for")


class DashboardResponse(BaseModel):
    """Response model for dashboard endpoints."""
    success: bool = Field(..., description="Whether the operation succeeded")
    session_id: str = Field(..., description="Session ID for future operations")
    
    # Dashboard data
    dashboard: Optional[ComposedDashboardSpec] = Field(None, description="Generated dashboard")
    
    # Error info
    error: Optional[str] = Field(None, description="Error message if failed")
    
    # Timing
    generation_time_ms: Optional[float] = Field(None, description="Total generation time")


class LayoutUpdateRequest(BaseModel):
    """Request model for updating dashboard layout."""
    layout_config: LayoutConfig = Field(..., description="New layout configuration")
