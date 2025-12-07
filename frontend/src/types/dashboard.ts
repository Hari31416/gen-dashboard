export const ChartType = {
    BAR: "bar",
    LINE: "line",
    AREA: "area",
    PIE: "arc",
    SCATTER: "point",
    KPI: "text",
    HEATMAP: "rect"
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

export interface ComposedDashboardSpec {
    title: string;
    description?: string;
    vega_lite_spec: Record<string, any>;
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
}
