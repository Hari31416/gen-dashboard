import { useState, useEffect } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { databaseApi } from '@/api/client';
import type { DatabaseConnection } from '@/types/database';
import { PlusCircle, Database, RefreshCw } from 'lucide-react';
import { ConnectionDialog } from './ConnectionDialog';
import { cn } from '@/lib/utils';

interface DatabaseSelectorProps {
    value: string;
    onValueChange: (value: string) => void;
    className?: string;
}

export function DatabaseSelector({ value, onValueChange, className }: DatabaseSelectorProps) {
    const [connections, setConnections] = useState<DatabaseConnection[]>([]);
    const [loading, setLoading] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);

    const fetchConnections = async () => {
        setLoading(true);
        try {
            const result = await databaseApi.list();
            setConnections(result.connections);
            // If no value selected and connections exist, select the first one
            if (!value && result.connections.length > 0) {
                onValueChange(result.connections[0].connection_name);
            }
        } catch (err) {
            console.error("Failed to fetch connections", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConnections();
    }, []);

    return (
        <div className={cn("flex items-center gap-2", className)}>
            <div className="relative w-[240px]">
                <Select value={value} onValueChange={onValueChange}>
                    <SelectTrigger className="w-full">
                        <div className="flex items-center gap-2">
                            <Database className="h-4 w-4 text-muted-foreground" />
                            <SelectValue placeholder="Select Database" />
                        </div>
                    </SelectTrigger>
                    <SelectContent>
                        {connections.length === 0 ? (
                            <div className="p-2 text-sm text-muted-foreground text-center">No connections found</div>
                        ) : (
                            connections.map((conn) => (
                                <SelectItem key={conn.connection_name} value={conn.connection_name}>
                                    <span className="font-medium">{conn.connection_name}</span>
                                    <span className="ml-2 text-xs text-muted-foreground">({conn.db_type})</span>
                                </SelectItem>
                            ))
                        )}
                    </SelectContent>
                </Select>
            </div>

            <Button
                variant="outline"
                size="icon"
                onClick={() => setDialogOpen(true)}
                title="Add Connection"
            >
                <PlusCircle className="h-4 w-4" />
            </Button>

            <Button
                variant="ghost"
                size="icon"
                onClick={fetchConnections}
                disabled={loading}
                title="Refresh List"
            >
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>

            <ConnectionDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                onSuccess={fetchConnections}
            />
        </div>
    );
}
