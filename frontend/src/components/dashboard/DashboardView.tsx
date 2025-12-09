import React, { useState } from 'react';
import { dashboardApi, sessionsApi } from '@/api/client';
import type { ComposedDashboardSpec } from '@/types/dashboard';
import { PromptInput } from './PromptInput';
import { ChartRenderer } from './ChartRenderer';
import { DatabaseSelector } from './DatabaseSelector';
import { DebugLogin } from './DebugLogin';
import { SavedDashboards } from './SavedDashboards';
import { ClarificationDialog } from './ClarificationDialog';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from "@/components/ui/sheet";
import { History } from 'lucide-react';
import { FilterPanel } from './FilterPanel';

export const DashboardView: React.FC = () => {
    const [dashboard, setDashboard] = useState<ComposedDashboardSpec | undefined>(undefined);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedConnection, setSelectedConnection] = useState<string>('');
    const [historyOpen, setHistoryOpen] = useState(false);
    const [filterState, setFilterState] = useState<Record<string, any>>({});
    // Clarification dialog state
    const [clarificationOpen, setClarificationOpen] = useState(false);
    const [clarificationQuestion, setClarificationQuestion] = useState('');

    const handleGenerate = async (prompt: string) => {
        setIsLoading(true);
        setError(null);
        try {
            // Use selected connection
            const response = await dashboardApi.generate({
                user_prompt: prompt,
                connection_name: selectedConnection || "default_connection"
            });

            if (response.success && response.dashboard) {
                setDashboard(response.dashboard);
                setSessionId(response.session_id);
            } else {
                setError(response.error || "Failed to generate dashboard");
            }
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    const handleRefresh = async () => {
        if (!sessionId) return;
        setIsLoading(true);
        try {
            const response = await dashboardApi.refresh({ session_id: sessionId });
            if (response.success && response.dashboard) {
                setDashboard(response.dashboard);
            }
        } catch (err: any) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleFilterChange = async (newFilters: Record<string, any>) => {
        setFilterState(newFilters);

        if (!sessionId) return;

        setIsLoading(true);
        try {
            // Use the dedicated filter endpoint for fast filter-only updates
            const response = await dashboardApi.filter({
                session_id: sessionId,
                filter_state: newFilters,
            });

            if (response.success && response.dashboard) {
                setDashboard(response.dashboard);
            } else {
                setError(response.error || "Failed to update filters");
            }
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    // Handle refine with clarification support
    const handleRefine = async (feedback: string) => {
        if (!sessionId) return;

        setIsLoading(true);
        setError(null);
        try {
            const response = await dashboardApi.refine({
                session_id: sessionId,
                new_feedback: feedback,
            });

            // Check if clarification is needed
            if (response.requires_clarification && response.clarification_question) {
                setClarificationQuestion(response.clarification_question);
                setClarificationOpen(true);
                return;
            }

            if (response.success && response.dashboard) {
                setDashboard(response.dashboard);
            } else {
                setError(response.error || "Failed to refine dashboard");
            }
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    const handleClarificationSubmit = (clarifiedFeedback: string) => {
        setClarificationOpen(false);
        handleRefine(clarifiedFeedback);
    };

    const handleRemoveFilter = (key: string) => {
        const newFilters = { ...filterState };
        delete newFilters[key];
        handleFilterChange(newFilters);
    };

    const handleClearFilters = () => {
        handleFilterChange({});
    };

    const handleLoadSession = async (session_id: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const session = await sessionsApi.get(session_id);
            if (session && session.dashboard_spec) {
                setDashboard({
                    title: session.dashboard_spec.title || 'Dashboard',
                    description: session.dashboard_spec.description,
                    vega_lite_spec: session.dashboard_spec.vega_lite_spec || {},
                    individual_specs: session.dashboard_spec.individual_specs || [],
                    layout_config: session.dashboard_spec.layout_config || undefined,
                    layout_type: session.dashboard_spec.layout_type || 'grid',
                    chart_count: session.dashboard_spec.chart_count || 0,
                    sql_queries: session.dashboard_spec.sql_queries || [],
                    generated_at: session.dashboard_spec.generated_at || new Date().toISOString(),
                });
                setSessionId(session_id);
                setSelectedConnection(session.connection_name || '');
                // Note: If we stored filters in session, we would load them here
                // setFilterState(session.filters || {});
            }
        } catch (err: any) {
            setError(err.message || "Failed to load dashboard");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 max-w-[95%] w-full mx-auto p-4 min-h-screen">
            <header className="flex items-center justify-between py-4 border-b border-border/40 mb-6 bg-muted/40 px-6 -mx-4 rounded-b-xl shadow-sm">
                <div className="flex flex-col gap-1">
                    <h1 className="text-2xl font-bold tracking-tight text-primary">
                        Generative Dashboard
                    </h1>
                </div>

                <div className="flex items-center gap-3">
                    <DatabaseSelector value={selectedConnection} onValueChange={setSelectedConnection} />

                    <div className="h-6 w-px bg-border/60 mx-1" />

                    <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
                        <SheetTrigger asChild>
                            <Button variant="default" size="sm" className="shadow-sm hover:shadow-md transition-all">
                                <History className="mr-2 h-4 w-4" />
                                History
                            </Button>
                        </SheetTrigger>
                        <SheetContent>
                            <SheetHeader className="mb-6">
                                <SheetTitle>Dashboard History</SheetTitle>
                                <SheetDescription>
                                    View and restore your past dashboard generations.
                                </SheetDescription>
                            </SheetHeader>
                            <SavedDashboards
                                className="h-[calc(100vh-10rem)]"
                                onSelect={(id) => {
                                    handleLoadSession(id);
                                    setHistoryOpen(false);
                                }}
                            />
                        </SheetContent>
                    </Sheet>
                    <DebugLogin />
                </div>
            </header>

            <section className="space-y-4">
                <PromptInput onSubmit={sessionId ? handleRefine : handleGenerate} isLoading={isLoading} />

                {Object.keys(filterState).length > 0 && (
                    <div className="max-w-3xl mx-auto animate-in fade-in slide-in-from-top-1">
                        <FilterPanel
                            filters={filterState}
                            onRemoveFilter={handleRemoveFilter}
                            onClearAll={handleClearFilters}
                        />
                    </div>
                )}

                {error && (
                    <div className="p-4 text-sm text-destructive bg-destructive/10 rounded-lg max-w-3xl mx-auto animate-in slide-in-from-top-2 border border-destructive/20">
                        Error: {error}
                    </div>
                )}
            </section>

            <main className="flex-1 w-full">
                <ChartRenderer
                    dashboard={dashboard}
                    isLoading={isLoading}
                    sessionId={sessionId}
                    onRefresh={handleRefresh}
                    onFilterChange={(newFilters) => {
                        // Merge with existing filters
                        handleFilterChange({ ...filterState, ...newFilters });
                    }}
                />
            </main>

            <ClarificationDialog
                isOpen={clarificationOpen}
                question={clarificationQuestion}
                onSubmit={handleClarificationSubmit}
                onClose={() => setClarificationOpen(false)}
            />
        </div>
    );
};
