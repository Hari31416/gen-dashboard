import { useState, useEffect } from 'react';
import { sessionsApi } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { History, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SavedSession {
    session_id: string;
    user_prompt: string;
    connection_name: string;
    dashboard_spec?: {
        title?: string;
        chart_count?: number;
    };
    created_at: string;
}

interface SavedDashboardsProps {
    onSelect: (session_id: string) => void;
    className?: string;
}

export function SavedDashboards({ onSelect, className }: SavedDashboardsProps) {
    const [sessions, setSessions] = useState<SavedSession[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchSessions = async () => {
        setLoading(true);
        try {
            const result = await sessionsApi.list(20);
            setSessions(result.sessions || []);
        } catch (err) {
            console.error("Failed to fetch sessions", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    const handleDelete = async (session_id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await sessionsApi.delete(session_id);
            setSessions(prev => prev.filter(s => s.session_id !== session_id));
        } catch (err) {
            console.error("Failed to delete session", err);
        }
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateStr;
        }
    };

    if (loading) {
        return (
            <div className={cn("space-y-4", className)}>
                {[1, 2, 3].map(i => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                ))}
            </div>
        );
    }

    if (sessions.length === 0) {
        return (
            <div className="text-center text-muted-foreground py-8">
                <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No saved dashboards yet.</p>
            </div>
        );
    }

    return (
        <div className={cn("space-y-3 h-full overflow-y-auto pr-2 -mr-2", className)}>
            {sessions.map((session) => (
                <div
                    key={session.session_id}
                    className="group flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted cursor-pointer transition-colors border border-transparent hover:border-border"
                    onClick={() => onSelect(session.session_id)}
                >
                    <div className="flex-1 min-w-0 pr-3">
                        <p className="font-medium text-sm truncate">
                            {session.dashboard_spec?.title || session.user_prompt.slice(0, 50)}
                        </p>
                        <p className="text-xs text-muted-foreground truncate flex items-center gap-2 mt-1">
                            <span>{formatDate(session.created_at)}</span>
                            <span className="w-1 h-1 rounded-full bg-muted-foreground/50" />
                            <span>{session.connection_name}</span>
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8 hover:bg-destructive/10 hover:text-destructive"
                        onClick={(e) => handleDelete(session.session_id, e)}
                    >
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
            ))}
        </div>
    );
}
