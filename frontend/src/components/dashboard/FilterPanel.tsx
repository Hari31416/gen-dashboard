import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, Filter, Plus } from 'lucide-react';
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';

interface FilterPanelProps {
    filters: Record<string, any>;
    onRemoveFilter: (key: string) => void;
    onClearAll: () => void;
    className?: string;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
    filters,
    onRemoveFilter,
    onClearAll,
    className
}) => {
    const hasFilters = Object.keys(filters).length > 0;

    if (!hasFilters) return null;

    return (
        <Card className={`w-full border-muted/40 shadow-sm ${className}`}>
            <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
                <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-primary" />
                    <CardTitle className="text-sm font-medium">Active Filters</CardTitle>
                </div>
                {hasFilters && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onClearAll}
                        className="h-8 px-2 text-xs text-muted-foreground hover:text-destructive"
                    >
                        Clear All
                    </Button>
                )}
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0">
                <div className="flex flex-wrap gap-2">
                    {Object.entries(filters).map(([key, value]) => (
                        <Badge
                            key={key}
                            variant="secondary"
                            className="flex items-center gap-1.5 py-1 px-2.5 text-sm font-normal border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors"
                        >
                            <span className="font-medium text-foreground/80">{key}:</span>
                            <span className="text-foreground font-semibold">
                                {String(value)}
                            </span>
                            <button
                                onClick={() => onRemoveFilter(key)}
                                className="ml-1 rounded-full p-0.5 hover:bg-black/10 transition-colors"
                                aria-label={`Remove filter ${key}`}
                            >
                                <X className="h-3 w-3 text-muted-foreground" />
                            </button>
                        </Badge>
                    ))}
                    
                    {/* Placeholder for "Add Filter" functionality */}
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-7 border-dashed text-xs text-muted-foreground gap-1"
                        disabled
                    >
                        <Plus className="h-3 w-3" />
                        Add Filter
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
};
