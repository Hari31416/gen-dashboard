import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface EmptyStateProps {
    title: string;
    description: string;
    icon?: LucideIcon;
    action?: {
        label: string;
        onClick: () => void;
    };
    className?: string;
    children?: React.ReactNode;
}

export function EmptyState({
    title,
    description,
    icon: Icon,
    action,
    className,
    children
}: EmptyStateProps) {
    return (
        <div className={cn(
            "flex flex-col items-center justify-center h-full min-h-[300px] p-8 text-center animate-in fade-in zoom-in-95 duration-500",
            className
        )}>
            <div className="flex items-center justify-center w-20 h-20 mb-6 rounded-full bg-muted/30 ring-1 ring-border shadow-sm">
                {Icon && <Icon className="w-10 h-10 text-muted-foreground/60" />}
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2 tracking-tight">
                {title}
            </h3>
            <p className="text-base text-muted-foreground max-w-sm mb-6 leading-relaxed">
                {description}
            </p>
            {action && (
                <Button onClick={action.onClick} variant="default" className="shadow-sm">
                    {action.label}
                </Button>
            )}
            {children}
        </div>
    );
}
