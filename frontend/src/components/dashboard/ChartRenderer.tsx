import React, { useEffect, useRef } from 'react';
import embed from 'vega-embed';
import type { ComposedDashboardSpec } from '@/types/dashboard';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

interface ChartRendererProps {
    dashboard?: ComposedDashboardSpec;
    isLoading: boolean;
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({ dashboard, isLoading }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (dashboard && containerRef.current) {
            // Clean up previous view if needed? embed handles it.
            embed(containerRef.current, dashboard.vega_lite_spec, {
                mode: 'vega-lite',
                actions: true,
                theme: 'quartz' // using a vega theme, or 'vox', 'fivethirtyeight'
            }).catch(console.error);
        }
    }, [dashboard]);

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

    if (!dashboard) {
        return (
            <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground bg-muted/10 rounded-xl border-2 border-dashed border-muted m-4">
                <p className="font-medium mb-1">No dashboard generated yet</p>
                <p className="text-sm">Enter a prompt above to start analyzing your data.</p>
            </div>
        );
    }

    return (
        <Card className="w-full shadow-lg border-muted/40">
            <CardHeader className="bg-muted/5 border-b border-muted/20">
                <CardTitle className="text-2xl text-primary">{dashboard.title}</CardTitle>
                {dashboard.description && <CardDescription className="text-base">{dashboard.description}</CardDescription>}
            </CardHeader>
            <CardContent className="p-6 bg-card">
                <div ref={containerRef} className="w-full flex justify-center overflow-x-auto min-h-[400px]" />
            </CardContent>
        </Card>
    );
};
