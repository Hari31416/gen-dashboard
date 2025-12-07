import React, { useState } from 'react';
import { dashboardApi, sessionsApi } from '@/api/client';
import type { ComposedDashboardSpec } from '@/types/dashboard';
import { PromptInput } from './PromptInput';
import { ChartRenderer } from './ChartRenderer';
import { DatabaseSelector } from './DatabaseSelector';
import { DebugLogin } from './DebugLogin';
import { SavedDashboards } from './SavedDashboards';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from "@/components/ui/sheet";
import { RefreshCw, History } from 'lucide-react';

export const DashboardView: React.FC = () => {
    const [dashboard, setDashboard] = useState<ComposedDashboardSpec | undefined>(undefined);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [selectedConnection, setSelectedConnection] = useState<string>('');
    const [historyOpen, setHistoryOpen] = useState(false);

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
                    layout_type: session.dashboard_spec.layout_type || 'vconcat',
                    chart_count: session.dashboard_spec.chart_count || 0,
                    sql_queries: session.dashboard_spec.sql_queries || [],
                    generated_at: session.dashboard_spec.generated_at || new Date().toISOString(),
                });
                setSessionId(session_id);
                setSelectedConnection(session.connection_name || '');
            }
        } catch (err: any) {
            setError(err.message || "Failed to load dashboard");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-8 max-w-6xl mx-auto p-4 md:p-8 min-h-screen">
            <header className="flex flex-col gap-4 text-center py-8">
                <div className="relative inline-block w-full max-w-4xl mx-auto">
                    <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-400 pb-2">
                        AI Analytics Dashboard
                    </h1>
                    <div className="absolute top-0 right-0 flex gap-2">
                        <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
                            <SheetTrigger asChild>
                                <Button variant="outline" size="sm" className="hidden sm:flex text-foreground">
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
                                    onSelect={(id) => {
                                        handleLoadSession(id);
                                        setHistoryOpen(false);
                                    }}
                                />
                            </SheetContent>
                        </Sheet>
                        <DebugLogin />
                    </div>
                </div>
                <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                    Transform your data into actionable insights with natural language.
                </p>
                <div className="flex justify-center mt-4">
                    <DatabaseSelector value={selectedConnection} onValueChange={setSelectedConnection} />
                </div>
            </header>

            <section className="sticky top-4 z-50">
                <PromptInput onSubmit={handleGenerate} isLoading={isLoading} />
                {error && (
                    <div className="mt-4 p-4 text-sm text-destructive bg-destructive/10 rounded-lg max-w-3xl mx-auto animate-in slide-in-from-top-2 border border-destructive/20">
                        Error: {error}
                    </div>
                )}
            </section>

            <main className="flex-1 w-full">
                {sessionId && !isLoading && !error && (
                    <div className="flex justify-end mb-4">
                        <Button variant="outline" size="sm" onClick={handleRefresh} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Refresh Data
                        </Button>
                    </div>
                )}

                <ChartRenderer dashboard={dashboard} isLoading={isLoading} />
            </main>
        </div>
    );
};
