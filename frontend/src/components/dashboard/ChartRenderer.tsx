/// <reference types="vite/client" />
import React, { useEffect, useRef, useState, useCallback } from 'react';
import embed from 'vega-embed';
import GridLayout, { type Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import type { ComposedDashboardSpec, LayoutConfig } from '@/types/dashboard';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { dashboardApi } from '@/api/client';
import { Move, Unlock, Save, RotateCcw, Download, Sparkles, Trash2, Code, FileText, BarChart3 } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { exportDashboardToPDF } from '@/lib/pdf-export';
import { EmptyState } from '@/components/ui/empty-state';

interface ChartRendererProps {
    dashboard?: ComposedDashboardSpec;
    isLoading: boolean;
    sessionId?: string | null;
    onLayoutChange?: (layout: LayoutConfig) => void;
    onFilterChange?: (filters: Record<string, any>) => void;
    onRefresh?: () => void;
    onRefine?: (chartId: string, feedback: string) => void;
    onDelete?: (chartId: string) => void;
}

// Debug mode from environment variable
const DEBUG_MODE = import.meta.env.VITE_DEBUG_MODE === 'true';

/**
 * Individual chart component that renders a single Vega-Lite spec
 * Uses ResizeObserver to re-render chart when container size changes
 */
interface IndividualChartProps {
    spec: Record<string, any>;
    chartId: string;
    onFilterChange?: (filters: Record<string, any>) => void;
}

const IndividualChart = ({ spec, chartId: _chartId, onFilterChange }: IndividualChartProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewRef = useRef<any>(null);
    const resizeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const { resolvedTheme } = useTheme();

    useEffect(() => {
        if (!spec || !containerRef.current) return;

        // Create a clean spec without our custom properties
        const cleanSpec = { ...spec };
        delete cleanSpec.chart_id;

        // Add selection for interactivity if not present
        // This ensures the chart captures click events even if the agent didn't explicity add selection
        if (!cleanSpec.selection && (typeof cleanSpec.mark === 'string' || (cleanSpec.mark && cleanSpec.mark.type !== 'arc'))) {
            cleanSpec.selection = {
                "select": {
                    "type": "point",
                    "on": "click",
                    "clear": "dblclick"
                }
            };
        }

        const renderChart = () => {
            if (!containerRef.current) return;

            // Finalize previous view before creating new one
            if (viewRef.current) {
                viewRef.current.finalize();
                viewRef.current = null;
            }

            // Get auth token from localStorage for Vega data fetching
            const token = localStorage.getItem('token');

            // Configure loader with auth headers for URL-based data loading
            const loaderOptions = token ? {
                loader: {
                    http: {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    }
                }
            } : {};

            // Configure view config to potentially override background
            const config = {
                background: 'transparent', // Ensure chart background is transparent
                view: { stroke: 'transparent' } // Remove view border if present
            };

            embed(containerRef.current, cleanSpec, {
                mode: 'vega-lite',
                actions: { export: true, source: false, compiled: false, editor: false },
                theme: resolvedTheme === 'dark' ? 'dark' : 'quartz',
                renderer: 'svg',
                config: config,
                ...loaderOptions,
            }).then((result: any) => {
                viewRef.current = result.view;

                // Add click listener if we have a callback
                if (onFilterChange) {
                    result.view.addEventListener('click', (_event: any, item: any) => {
                        if (item && item.datum) {
                            // Extract meaningful data points for filtering
                            const datum = item.datum;
                            const filters: Record<string, any> = {};

                            // Identify potential dimension fields from the spec's encoding
                            const dimensionFields = new Set<string>();
                            if (cleanSpec.encoding) {
                                Object.values(cleanSpec.encoding).forEach((enc: any) => {
                                    // Check for nominal, ordinal, or temporal types
                                    // Also include if no type is specified but it looks like a dimension (e.g., having 'field')
                                    if (enc.field && (
                                        enc.type === 'nominal' ||
                                        enc.type === 'ordinal' ||
                                        enc.type === 'temporal' ||
                                        !enc.type // fallback if type omitted but used as dimension
                                    )) {
                                        dimensionFields.add(enc.field);
                                    }
                                });
                            }

                            // Iterate through keys in datum
                            Object.keys(datum).forEach(key => {
                                // Only use keys that are:
                                // 1. Identified as dimensions in the encoding
                                // 2. NOT internal vega fields (starting with _)
                                // 3. NOT objects/arrays
                                if (!key.startsWith('_') &&
                                    key !== 'source' &&
                                    typeof datum[key] !== 'object' &&
                                    dimensionFields.has(key)) {
                                    filters[key] = datum[key];
                                }
                            });

                            if (Object.keys(filters).length > 0) {
                                console.log("Drill-down triggered:", filters);
                                onFilterChange(filters);
                            }
                        }
                    });
                }
            }).catch(console.error);
        };

        renderChart();

        // Set up ResizeObserver with debounced re-render
        const resizeObserver = new ResizeObserver(() => {
            // Debounce the resize to avoid too many re-renders
            if (resizeTimeoutRef.current) {
                clearTimeout(resizeTimeoutRef.current);
            }
            resizeTimeoutRef.current = setTimeout(() => {
                renderChart();
            }, 150);
        });

        resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
            if (resizeTimeoutRef.current) {
                clearTimeout(resizeTimeoutRef.current);
            }
            if (viewRef.current) {
                viewRef.current.finalize();
            }
        };
    }, [spec, onFilterChange]);

    return (
        <div
            ref={containerRef}
            className="w-full h-full overflow-hidden p-2"
            style={{ minHeight: '80px', minWidth: '100px' }}
        />
    );
};

/**
 * ChartRenderer with react-grid-layout for flexible dashboard layouts
 */
export const ChartRenderer: React.FC<ChartRendererProps> = ({
    dashboard,
    isLoading,
    sessionId,
    onLayoutChange,
    onFilterChange,
    onRefresh,
    onRefine,
    onDelete
}: ChartRendererProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cardRef = useRef<HTMLDivElement>(null);
    const [editMode, setEditMode] = useState(false);
    const [currentLayout, setCurrentLayout] = useState<Layout[]>([]);
    const [originalLayout, setOriginalLayout] = useState<Layout[]>([]);
    const [isSaving, setIsSaving] = useState(false);
    const [containerWidth, setContainerWidth] = useState(0);

    // Track refine input state locally
    const [refineInputs, setRefineInputs] = useState<Record<string, string>>({});
    const [openPopovers, setOpenPopovers] = useState<Record<string, boolean>>({});
    const [copiedStates, setCopiedStates] = useState<Record<string, boolean>>({});

    const handleRefineSubmit = (chartId: string) => {
        const feedback = refineInputs[chartId];
        if (feedback && onRefine) {
            onRefine(chartId, feedback);
            setRefineInputs((prev: Record<string, string>) => ({ ...prev, [chartId]: '' }));
            setOpenPopovers((prev: Record<string, boolean>) => ({ ...prev, [chartId]: false }));
        }
    };

    // Calculate container width for react-grid-layout using ResizeObserver
    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        const handleResize = (entries: ResizeObserverEntry[]) => {
            for (const entry of entries) {
                if (entry.contentRect.width > 0) {
                    setContainerWidth(Math.floor(entry.contentRect.width));
                }
            }
        };

        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(element);

        // Also do an initial measurement in case ResizeObserver doesn't fire immediately
        const initialWidth = element.getBoundingClientRect().width;
        if (initialWidth > 0) {
            // Subtract padding (p-4 = 32px total)
            setContainerWidth(Math.floor(initialWidth - 32));
        }

        return () => resizeObserver.disconnect();
    });

    // Initialize layout from dashboard (only when dashboard changes, not editMode)
    useEffect(() => {
        if (dashboard?.layout_config?.layout) {
            const layout = dashboard.layout_config.layout.map(pos => ({
                i: pos.i,
                x: pos.x,
                y: pos.y,
                w: pos.w,
                h: pos.h,
                minW: pos.minW || 2,
                minH: pos.minH || 2,
                static: false, // Will be updated by editMode effect
            }));
            setCurrentLayout(layout);
            setOriginalLayout(layout);
        }
    }, [dashboard?.layout_config]);

    // Update static property when editMode changes (without resetting positions)
    useEffect(() => {
        setCurrentLayout(prev => prev.map((item: Layout) => ({
            ...item,
            static: !editMode,
        })));
    }, [editMode]);

    // Handle layout change from react-grid-layout
    const handleLayoutChange = useCallback((newLayout: Layout[]) => {
        if (editMode) {
            setCurrentLayout(newLayout);
        }
    }, [editMode]);

    // Save layout to backend
    const handleSaveLayout = async () => {
        if (!sessionId || !dashboard?.layout_config) return;

        setIsSaving(true);
        try {
            const layoutConfig: LayoutConfig = {
                cols: dashboard.layout_config.cols || 12,
                row_height: dashboard.layout_config.row_height || 100,
                layout: currentLayout.map((l: Layout) => ({
                    i: l.i,
                    x: l.x,
                    y: l.y,
                    w: l.w,
                    h: l.h,
                    minW: l.minW,
                    minH: l.minH,
                })),
                custom: true,
            };

            await dashboardApi.updateLayout(sessionId, layoutConfig);
            setOriginalLayout(currentLayout);
            setEditMode(false);
            onLayoutChange?.(layoutConfig);
        } catch (error) {
            console.error('Failed to save layout:', error);
        } finally {
            setIsSaving(false);
        }
    };

    // Reset to original layout
    const handleResetLayout = () => {
        setCurrentLayout(originalLayout);
    };

    // Export dashboard to standalone HTML file with embedded data
    const handleExportHTML = useCallback(async () => {
        if (!dashboard) return;

        // Get the specs to export (either individual or composed)
        const specs = dashboard.individual_specs && dashboard.individual_specs.length > 0
            ? dashboard.individual_specs
            : [dashboard.vega_lite_spec];

        // Get layout positions - use currentLayout if available, otherwise from dashboard
        const layoutPositions = currentLayout.length > 0
            ? currentLayout
            : (dashboard.layout_config?.layout || []);

        // Calculate grid dimensions
        const gridCols = dashboard.layout_config?.cols || 12;
        const rowHeight = dashboard.layout_config?.row_height || 100;

        // Fetch data for each chart and embed inline
        const token = localStorage.getItem('token');
        const specsWithData = await Promise.all(specs.map(async (spec: Record<string, any>) => {
            const chartSpec = { ...spec };

            // If spec has URL-based data, fetch and embed it
            if (chartSpec.data && typeof chartSpec.data === 'object' && chartSpec.data.url) {
                try {
                    const response = await fetch(chartSpec.data.url, {
                        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                    });
                    if (response.ok) {
                        const data = await response.json();
                        // Replace URL with inline values
                        chartSpec.data = { values: data };
                    }
                } catch (error) {
                    console.error('Failed to fetch chart data for export:', error);
                    // Keep URL-based (will fail in exported file but at least shows something)
                }
            }

            return chartSpec;
        }));

        // Generate HTML content with CSS Grid matching the layout
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${dashboard.title || 'Dashboard'}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5; 
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .dashboard-header {
            text-align: center;
            margin-bottom: 24px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .dashboard-header h1 { 
            color: #333; 
            font-size: 28px;
            margin-bottom: 8px;
        }
        .dashboard-header p { 
            color: #666; 
            font-size: 16px;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(${gridCols}, 1fr);
            grid-auto-rows: ${rowHeight}px;
            gap: 12px;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .chart-title {
            font-size: 14px;
            font-weight: 500;
            color: #666;
            margin-bottom: 12px;
            flex-shrink: 0;
        }
        .chart-content {
            flex: 1;
            min-height: 0;
        }
        .generated-info {
            text-align: center;
            margin-top: 24px;
            font-size: 12px;
            color: #999;
        }
        ${specsWithData.map((spec: Record<string, any>, i: number) => {
            const chartId = spec.chart_id || `chart_${i + 1}`;
            const pos = layoutPositions.find((p: Layout) => p.i === chartId);
            if (pos) {
                return `.chart-${chartId} {
            grid-column: ${pos.x + 1} / span ${pos.w};
            grid-row: ${pos.y + 1} / span ${pos.h};
        }`;
            }
            return '';
        }).join('\n        ')}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>${dashboard.title || 'Dashboard'}</h1>
        ${dashboard.description ? `<p>${dashboard.description}</p>` : ''}
    </div>
    <div class="charts-grid">
        ${specsWithData.map((spec, i) => {
            const chartId = (spec as Record<string, any>).chart_id || `chart_${i + 1}`;
            const title = (spec as Record<string, any>).title || '';
            return `
        <div class="chart-container chart-${chartId}">
            ${title ? `<div class="chart-title">${title}</div>` : ''}
            <div class="chart-content" id="${chartId}"></div>
        </div>`;
        }).join('\n')}
    </div>
    <div class="generated-info">
        Generated on ${new Date().toLocaleString()}
    </div>
    <script>
        const specs = ${JSON.stringify(specsWithData.map(spec => {
            const cleanSpec = { ...spec } as Record<string, any>;
            delete cleanSpec.chart_id;
            // Keep container sizing - we'll handle it with JS
            delete cleanSpec.width;
            delete cleanSpec.height;
            delete cleanSpec.autosize;
            return cleanSpec;
        }), null, 2)};
        
        const chartIds = ${JSON.stringify(specsWithData.map((s, i) => (s as Record<string, any>).chart_id || `chart_${i + 1}`))};
        
        function renderCharts() {
            specs.forEach((spec, i) => {
                const container = document.getElementById(chartIds[i]);
                if (!container) return;
                
                // Get actual container dimensions
                const rect = container.getBoundingClientRect();
                const chartSpec = {
                    ...spec,
                    width: Math.max(rect.width - 20, 100),
                    height: Math.max(rect.height - 20, 100),
                    autosize: { type: 'fit', contains: 'padding' }
                };
                
                vegaEmbed('#' + chartIds[i], chartSpec, {
                    mode: 'vega-lite',
                    actions: { export: true, source: false, compiled: false, editor: false },
                    theme: 'quartz'
                }).catch(console.error);
            });
        }

        // Render on load and resize
        window.addEventListener('load', renderCharts);
        window.addEventListener('resize', () => {
            clearTimeout(window.resizeTimer);
            window.resizeTimer = setTimeout(renderCharts, 200);
        });
    </script>
</body>
</html>`;

        // Create and download HTML file
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${dashboard.title?.replace(/[^a-z0-9]/gi, '_') || 'dashboard'}.html`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }, [dashboard, currentLayout]);

    // Loading state
    if (isLoading) {
        return (
            <Card className="w-full h-[600px] border-none shadow-none bg-transparent">
                <CardHeader>
                    <Skeleton className="h-8 w-1/3 mb-2" />
                    <Skeleton className="h-4 w-1/2" />
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-[400px] w-full" />
                </CardContent>
            </Card>
        );
    }

    // Empty state
    if (!dashboard) {
        return (
            <EmptyState
                title="No dashboard generated yet"
                description="Enter a prompt above to start analyzing your data. Or see a dashboard from history."
                icon={BarChart3}
                className="h-[400px] border-2 border-dashed border-muted m-4 bg-muted/5 rounded-xl"
            />
        );
    }

    // Check if we have individual specs and layout (new flexible layout)
    const hasFlexibleLayout = dashboard.individual_specs &&
        dashboard.individual_specs.length > 0 &&
        dashboard.layout_config?.layout;

    // If no flexible layout, fall back to legacy rendering
    if (!hasFlexibleLayout) {
        return <LegacyChartRenderer dashboard={dashboard} />;
    }

    const { individual_specs, layout_config } = dashboard;
    const rowHeight = layout_config?.row_height || 100;
    const cols = layout_config?.cols || 12;

    return (
        <Card className="w-full shadow-lg border-muted/40" ref={cardRef}>
            <CardHeader className="bg-muted/5 border-b border-muted/20">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-2xl text-primary">{dashboard.title}</CardTitle>
                        {dashboard.description && (
                            <CardDescription className="text-base">{dashboard.description}</CardDescription>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {editMode ? (
                            <>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleResetLayout}
                                    className="gap-2"
                                >
                                    <RotateCcw className="h-4 w-4" /> Reset
                                </Button>
                                <Button
                                    variant="default"
                                    size="sm"
                                    onClick={handleSaveLayout}
                                    disabled={isSaving}
                                    className="gap-2"
                                >
                                    <Save className="h-4 w-4" />
                                    {isSaving ? 'Saving...' : 'Save Layout'}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                        setCurrentLayout(originalLayout);
                                        setEditMode(false);
                                    }}
                                >
                                    Cancel
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    variant="outline"
                                    size="sm"
                                        onClick={onRefresh}
                                        className="gap-2"
                                        disabled={isLoading}
                                    >
                                        <RotateCcw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                                        Refresh Data
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleExportHTML}
                                        className="gap-2"
                                    >
                                        <Code className="h-4 w-4" /> Export HTML
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                            if (cardRef.current && dashboard && individual_specs) {
                                                // Prepare chart data for Vega-based PDF export
                                                const charts = individual_specs.map((spec: Record<string, any>, index: number) => {
                                                    const chartId = spec.chart_id || `chart_${index + 1}`;
                                                    const layoutItem = currentLayout.find((l: Layout) => l.i === chartId);
                                                    return {
                                                        spec,
                                                        chartId,
                                                        title: spec.title as string | undefined,
                                                        layout: layoutItem ? {
                                                            x: layoutItem.x,
                                                            y: layoutItem.y,
                                                            w: layoutItem.w,
                                                            h: layoutItem.h,
                                                        } : { x: 0, y: index * 3, w: 6, h: 3 },
                                                    };
                                                });

                                                exportDashboardToPDF(cardRef.current, {
                                                    title: dashboard.title,
                                                    description: dashboard.description,
                                                    filename: dashboard.title
                                                }, {
                                                    title: dashboard.title,
                                                    description: dashboard.description,
                                                    charts,
                                                    gridCols: cols,
                                                    rowHeight,
                                                });
                                            }
                                        }}
                                        className="gap-2"
                                    >
                                        <FileText className="h-4 w-4" /> Export PDF
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setEditMode(true)}
                                        className="gap-2"
                                    >
                                        <Move className="h-4 w-4" /> Edit Layout
                                    </Button>
                            </>
                        )}
                    </div>
                </div>
                {editMode && (
                    <p className="text-sm text-muted-foreground mt-2 flex items-center gap-2">
                        <Unlock className="h-4 w-4" />
                        Drag charts to reposition, drag edges to resize
                    </p>
                )}
            </CardHeader>
            <CardContent className="p-4 bg-card overflow-hidden" ref={containerRef}>
                {containerWidth > 0 && (
                    <GridLayout
                        className="layout"
                        layout={currentLayout}
                        cols={cols}
                        rowHeight={rowHeight}
                        width={containerWidth - 2} // Small safety margin
                        onLayoutChange={handleLayoutChange}
                        isDraggable={editMode}
                        isResizable={editMode}
                        compactType="vertical"
                        preventCollision={false}
                        margin={[12, 12]}
                    >
                        {individual_specs!.map((spec: Record<string, any>, index: number) => {
                            const chartId = spec.chart_id || `chart_${index + 1}`;

                            // Find SQL for this chart
                            let chartSql = '';
                            if (dashboard?.sql_queries) {
                                const sqlEntry = dashboard.sql_queries.find(q => q[chartId]);
                                if (sqlEntry) {
                                    chartSql = sqlEntry[chartId];
                                }
                            }

                            return (
                                <div
                                    key={chartId}
                                    className={`bg-card rounded-lg border shadow-sm ${editMode ? 'cursor-move ring-2 ring-primary/20' : ''}`}
                                    style={{ overflow: 'hidden' }}
                                >
                                    <div className="p-2 h-full flex flex-col overflow-hidden">
                                        <div className="flex items-center justify-between px-2 mb-1 flex-shrink-0">
                                            {spec.title && (
                                                <h3 className="text-sm font-medium text-muted-foreground truncate" title={spec.title}>
                                                    {spec.title}
                                                </h3>
                                            )}

                                            <div className="flex items-center gap-1">
                                                {!editMode && onRefine && (
                                                    <Popover
                                                        open={openPopovers[chartId]}
                                                        onOpenChange={(open) => setOpenPopovers(prev => ({ ...prev, [chartId]: open }))}
                                                    >
                                                        <PopoverTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-6 w-6 text-muted-foreground hover:text-primary"
                                                                title="Refine this chart"
                                                            >
                                                                <Sparkles className="h-3.5 w-3.5" />
                                                            </Button>
                                                        </PopoverTrigger>
                                                        <PopoverContent className="w-80" align="end">
                                                            <div className="grid gap-4">
                                                                <div className="space-y-2">
                                                                    <h4 className="font-medium leading-none">Refine Chart</h4>
                                                                    <p className="text-sm text-muted-foreground">
                                                                        Describe how you want to modify this specific chart.
                                                                    </p>
                                                                </div>
                                                                <div className="grid gap-2">
                                                                    <Textarea
                                                                        id={`refine-${chartId}`}
                                                                        placeholder="e.g. Change to bar chart, change color to blue..."
                                                                        value={refineInputs[chartId] || ''}
                                                                        onChange={(e) => setRefineInputs(prev => ({ ...prev, [chartId]: e.target.value }))}
                                                                        className="col-span-3 min-h-[80px]"
                                                                        onKeyDown={(e) => {
                                                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                                                e.preventDefault();
                                                                                handleRefineSubmit(chartId);
                                                                            }
                                                                        }}
                                                                    />
                                                                </div>
                                                                <div className="flex justify-end">
                                                                    <Button size="sm" onClick={() => handleRefineSubmit(chartId)}>
                                                                        Apply
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        </PopoverContent>
                                                    </Popover>
                                                )}

                                                {!editMode && onDelete && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-destructive"
                                                        title="Delete this chart"
                                                        onClick={() => onDelete(chartId)}
                                                    >
                                                        <Trash2 className="h-3.5 w-3.5" />
                                                    </Button>
                                                )}

                                                {!editMode && chartSql && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                                                        title={copiedStates[chartId] ? "Copied!" : "Copy SQL"}
                                                        onClick={async () => {
                                                            try {
                                                                await navigator.clipboard.writeText(chartSql);
                                                                setCopiedStates(prev => ({ ...prev, [chartId]: true }));
                                                                setTimeout(() => {
                                                                    setCopiedStates(prev => ({ ...prev, [chartId]: false }));
                                                                }, 2000);
                                                            } catch (err) {
                                                                console.error('Failed to copy SQL:', err);
                                                            }
                                                        }}
                                                    >
                                                        {copiedStates[chartId] ? (
                                                            <Sparkles className="h-3.5 w-3.5 text-green-500" />
                                                        ) : (
                                                            <Code className="h-3.5 w-3.5" />
                                                        )}
                                                    </Button>
                                                )}

                                                {!editMode && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                                                        title="Download CSV"
                                                        onClick={async () => {
                                                            try {
                                                                // Fetch data
                                                                let data: any[] = [];
                                                                const chartSpec = { ...spec } as Record<string, any>;

                                                                if (chartSpec.data?.values) {
                                                                    data = chartSpec.data.values;
                                                                } else if (chartSpec.data?.url) {
                                                                    const token = localStorage.getItem('token');
                                                                    const response = await fetch(chartSpec.data.url, {
                                                                        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                                                                    });
                                                                    if (response.ok) {
                                                                        data = await response.json();
                                                                    }
                                                                }

                                                                if (!data || data.length === 0) {
                                                                    alert('No data available to download');
                                                                    return;
                                                                }

                                                                // Convert to CSV
                                                                const headers = Object.keys(data[0]);
                                                                const csvContent = [
                                                                    headers.join(','),
                                                                    ...data.map(row => headers.map(header => {
                                                                        const cell = row[header] === null || row[header] === undefined ? '' : row[header];
                                                                        return JSON.stringify(cell);
                                                                    }).join(','))
                                                                ].join('\\n');

                                                                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                                                                const url = URL.createObjectURL(blob);
                                                                const link = document.createElement('a');
                                                                link.href = url;
                                                                link.download = `${spec.title?.replace(/[^a-z0-9]/gi, '_') || chartId}.csv`;
                                                                document.body.appendChild(link);
                                                                link.click();
                                                                document.body.removeChild(link);
                                                                URL.revokeObjectURL(url);
                                                            } catch (err) {
                                                                console.error('Failed to download CSV:', err);
                                                            }
                                                        }}
                                                    >
                                                        <FileText className="h-3.5 w-3.5" />
                                                    </Button>
                                                )}

                                                {!editMode && DEBUG_MODE && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-blue-500"
                                                        title="Copy Vega JSON (Debug)"
                                                        onClick={async () => {
                                                            // Fetch data and create standalone Vega JSON
                                                            const chartSpec = { ...spec } as Record<string, any>;
                                                            if (chartSpec.data?.url) {
                                                                try {
                                                                    const token = localStorage.getItem('token');
                                                                    const response = await fetch(chartSpec.data.url, {
                                                                        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                                                                    });
                                                                    if (response.ok) {
                                                                        const data = await response.json();
                                                                        chartSpec.data = { values: data };
                                                                    }
                                                                } catch (e) {
                                                                    console.error('Failed to fetch data:', e);
                                                                }
                                                            }
                                                            delete chartSpec.chart_id;
                                                            const jsonStr = JSON.stringify(chartSpec, null, 2);
                                                            await navigator.clipboard.writeText(jsonStr);
                                                            alert('Vega JSON copied to clipboard!');
                                                        }}
                                                    >
                                                        <Code className="h-3.5 w-3.5" />
                                                    </Button>
                                                )}

                                                {!editMode && DEBUG_MODE && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-green-500"
                                                        title="Download Vega JSON (Debug)"
                                                        onClick={async () => {
                                                            // Fetch data and create standalone Vega JSON
                                                            const chartSpec = { ...spec } as Record<string, any>;
                                                            if (chartSpec.data?.url) {
                                                                try {
                                                                    const token = localStorage.getItem('token');
                                                                    const response = await fetch(chartSpec.data.url, {
                                                                        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                                                                    });
                                                                    if (response.ok) {
                                                                        const data = await response.json();
                                                                        chartSpec.data = { values: data };
                                                                    }
                                                                } catch (e) {
                                                                    console.error('Failed to fetch data:', e);
                                                                }
                                                            }
                                                            delete chartSpec.chart_id;
                                                            const blob = new Blob([JSON.stringify(chartSpec, null, 2)], { type: 'application/json' });
                                                            const url = URL.createObjectURL(blob);
                                                            const link = document.createElement('a');
                                                            link.href = url;
                                                            link.download = `${spec.title?.replace(/[^a-z0-9]/gi, '_') || chartId}.json`;
                                                            document.body.appendChild(link);
                                                            link.click();
                                                            document.body.removeChild(link);
                                                            URL.revokeObjectURL(url);
                                                        }}
                                                    >
                                                        <Download className="h-3.5 w-3.5" />
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
                                            <IndividualChart
                                                spec={spec}
                                                chartId={chartId}
                                                onFilterChange={editMode ? undefined : onFilterChange}
                                            />
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </GridLayout>
                )}
            </CardContent>
        </Card>
    );
};

/**
 * Legacy renderer for backward compatibility with old dashboard format
 */
const LegacyChartRenderer: React.FC<{ dashboard: ComposedDashboardSpec }> = ({ dashboard }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (dashboard && containerRef.current) {
            embed(containerRef.current, dashboard.vega_lite_spec, {
                mode: 'vega-lite',
                actions: true,
                theme: 'quartz'
            }).catch(console.error);
        }
    }, [dashboard]);

    // Export to HTML for legacy format
    const handleExportHTML = useCallback(() => {
        const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${dashboard.title || 'Dashboard'}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5; 
            padding: 20px;
            margin: 0;
        }
        .dashboard-header {
            text-align: center;
            margin-bottom: 24px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .dashboard-header h1 { color: #333; font-size: 28px; margin: 0 0 8px 0; }
        .dashboard-header p { color: #666; font-size: 16px; margin: 0; }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .generated-info {
            text-align: center;
            margin-top: 24px;
            font-size: 12px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>${dashboard.title || 'Dashboard'}</h1>
        ${dashboard.description ? `<p>${dashboard.description}</p>` : ''}
    </div>
    <div class="chart-container">
        <div id="chart"></div>
    </div>
    <div class="generated-info">Generated on ${new Date().toLocaleString()}</div>
    <script>
        const spec = ${JSON.stringify(dashboard.vega_lite_spec, null, 2)};
        vegaEmbed('#chart', spec, {
            mode: 'vega-lite',
            actions: { export: true, source: false, compiled: false, editor: false },
            theme: 'quartz'
        }).catch(console.error);
    </script>
</body>
</html>`;

        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${dashboard.title?.replace(/[^a-z0-9]/gi, '_') || 'dashboard'}.html`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }, [dashboard]);

    return (
        <Card className="w-full shadow-lg border-muted/40">
            <CardHeader className="bg-muted/5 border-b border-muted/20">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-2xl text-primary">{dashboard.title}</CardTitle>
                        {dashboard.description && <CardDescription className="text-base">{dashboard.description}</CardDescription>}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleExportHTML}
                        className="gap-2"
                    >
                        <Download className="h-4 w-4" /> Export HTML
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="p-6 bg-card">
                <div ref={containerRef} className="w-full flex justify-center overflow-x-auto min-h-[400px]" />
            </CardContent>
        </Card>
    );
};
