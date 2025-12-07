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


class ComposedDashboardSpec(BaseModel):
    """
    Output schema for Layout Agent.
    The final composed Vega-Lite dashboard specification.
    """
    # Dashboard metadata
    title: str = Field(..., description="Dashboard title")
    description: Optional[str] = Field(None, description="Dashboard description")
    
    # Full Vega-Lite specification
    vega_lite_spec: Dict[str, Any] = Field(..., description="Complete Vega-Lite JSON")
    
    # Layout info
    layout_type: LayoutType = Field(..., description="Layout arrangement used")
    chart_count: int = Field(..., description="Number of charts in dashboard")
    
    # Metadata for refresh/refine
    sql_queries: List[Dict[str, str]] = Field(..., description="SQL queries by chart_id for refresh")
    
    # Timestamps
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_json(self) -> Dict[str, Any]:
        """Return the full specification as JSON-serializable dict."""
        return {
            "title": self.title,
            "description": self.description,
            "vega_lite_spec": self.vega_lite_spec,
            "layout_type": self.layout_type.value,
            "chart_count": self.chart_count,
            "sql_queries": self.sql_queries,
            "generated_at": self.generated_at.isoformat(),
        }


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
