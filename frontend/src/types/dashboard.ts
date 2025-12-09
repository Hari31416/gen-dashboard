export const ChartType = {
    BAR: "bar",
    LINE: "line",
    AREA: "area",
    PIE: "arc",
    SCATTER: "point",
    KPI: "text",
    HEATMAP: "rect",
    MAP: "geoshape"
} as const;
export type ChartType = typeof ChartType[keyof typeof ChartType];

export const AggregationType = {
    SUM: "sum",
    COUNT: "count",
    AVERAGE: "average",
    MIN: "min",
    MAX: "max",
    DISTINCT: "distinct",
    NONE: "none"
} as const;
export type AggregationType = typeof AggregationType[keyof typeof AggregationType];

export interface ChartGoal {
    chart_id: string;
    chart_type: ChartType;
    title: string;
    description: string;
    x_field?: string;
    y_field?: string;
    color_field?: string;
    aggregation: AggregationType;
    filters?: Record<string, any>;
    tables: string[];
    priority: number;
    // Map-specific fields
    geography_level?: "country" | "state" | "district";
    geography_field?: string;
    target_state?: string;
}

export interface SingleVizSpec {
    chart_id: string;
    mark: Record<string, any>;
    encoding: Record<string, any>;
    data: Record<string, any>;
    title?: string;
    width?: number;
    height?: number;
    selection?: Record<string, any>;
    config?: Record<string, any>;
}

export const LayoutType = {
    HCONCAT: "hconcat",
    VCONCAT: "vconcat",
    GRID: "grid",
    SINGLE: "single"
} as const;
export type LayoutType = typeof LayoutType[keyof typeof LayoutType];

/**
 * Position and size of a chart in react-grid-layout.
 * Compatible with react-grid-layout's Layout type.
 */
export interface ChartLayoutPosition {
    i: string;        // Chart identifier (chart_id)
    x: number;        // Column position (0-11)
    y: number;        // Row position (0-based)
    w: number;        // Width in grid units (1-12)
    h: number;        // Height in row units
    minW?: number;    // Minimum width
    minH?: number;    // Minimum height
    static?: boolean; // If true, cannot be dragged/resized
}

/**
 * Complete layout configuration for a dashboard.
 * Compatible with react-grid-layout format.
 */
export interface LayoutConfig {
    cols: number;                      // Total grid columns (default 12)
    row_height: number;                // Height of each row in pixels
    layout: ChartLayoutPosition[];     // Position of each chart
    custom: boolean;                   // Whether user has customized this layout
}

export interface ComposedDashboardSpec {
    title: string;
    description?: string;
    vega_lite_spec: Record<string, any>;
    individual_specs?: Array<Record<string, any>>; // Individual chart specs for flexible layout
    layout_config?: LayoutConfig;                   // react-grid-layout compatible layout
    layout_type: LayoutType;
    chart_count: number;
    sql_queries: Array<Record<string, string>>; // List of {chart_id: sql}
    generated_at: string;
}

export interface DashboardGenerateRequest {
    user_prompt: string;
    connection_name: string;
    max_charts?: number;
    theme?: string;
}

export interface DashboardRefineRequest {
    session_id: string;
    new_feedback?: string;
    filter_state?: Record<string, any>;
    target_chart_id?: string;
}

export interface DashboardRefreshRequest {
    session_id: string;
}

export interface DashboardResponse {
    success: boolean;
    session_id: string;
    dashboard?: ComposedDashboardSpec;
    error?: string;
    generation_time_ms?: number;
    // Clarification fields (present when requires_clarification is true)
    requires_clarification?: boolean;
    clarification_question?: string;
    reasoning?: string;
}

// Filter request for the new /filter endpoint
export interface DashboardFilterRequest {
    session_id: string;
    filter_state: Record<string, any>;
}
