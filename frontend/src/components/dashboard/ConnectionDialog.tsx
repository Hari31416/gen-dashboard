import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { databaseApi } from '@/api/client';
import { Loader2 } from 'lucide-react';
import type { DatabaseConnectionRequest } from '@/types/database';

interface ConnectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess: () => void;
}

export function ConnectionDialog({ open, onOpenChange, onSuccess }: ConnectionDialogProps) {
    const [loading, setLoading] = useState(false);
    const [testing, setTesting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [testResult, setTestResult] = useState<{ valid: boolean; message: string } | null>(null);

    const [formData, setFormData] = useState<DatabaseConnectionRequest>({
        connection_name: '',
        db_type: 'mysql',
        host: 'localhost',
        port: 3306,
        username: 'root',
        password: '',
        database_name: '',
        db_description: ''
    });

    const handleChange = (field: keyof DatabaseConnectionRequest, value: string | number) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        setError(null);
        setTestResult(null);
    };

    const handleTest = async () => {
        setTesting(true);
        setError(null);
        setTestResult(null);
        try {
            const result = await databaseApi.validate({
                host: formData.host,
                port: formData.port,
                username: formData.username,
                password: formData.password,
                database_name: formData.database_name,
                db_type: formData.db_type
            });
            setTestResult({ valid: result.valid, message: result.message || 'Connection successful' });
        } catch (err: any) {
            setTestResult({ valid: false, message: err.response?.data?.detail || 'Connection failed' });
        } finally {
            setTesting(false);
        }
    };

    const handleSave = async () => {
        setLoading(true);
        setError(null);
        try {
            await databaseApi.create(formData);
            onSuccess();
            onOpenChange(false);
            // Reset form
            setFormData({
                connection_name: '',
                db_type: 'mysql',
                host: 'localhost',
                port: 3306,
                username: 'root',
                password: '',
                database_name: '',
                db_description: ''
            });
            setTestResult(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save connection');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Add Database Connection</DialogTitle>
                    <DialogDescription>
                        Enter your database credentials. We support MySQL, PostgreSQL, and SQLite.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="name" className="text-right">Name</Label>
                        <Input
                            id="name"
                            value={formData.connection_name}
                            onChange={(e) => handleChange('connection_name', e.target.value)}
                            placeholder="my-prod-db"
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="type" className="text-right">Type</Label>
                        <div className="col-span-3">
                            <Select
                                value={formData.db_type}
                                onValueChange={(val) => handleChange('db_type', val)}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select DB Type" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="mysql">MySQL</SelectItem>
                                    <SelectItem value="postgresql">PostgreSQL</SelectItem>
                                    <SelectItem value="sqlite">SQLite</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="host" className="text-right">Host</Label>
                        <Input
                            id="host"
                            value={formData.host}
                            onChange={(e) => handleChange('host', e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="port" className="text-right">Port</Label>
                        <Input
                            id="port"
                            type="number"
                            value={formData.port}
                            onChange={(e) => handleChange('port', parseInt(e.target.value))}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="user" className="text-right">User</Label>
                        <Input
                            id="user"
                            value={formData.username}
                            onChange={(e) => handleChange('username', e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="password" className="text-right">Password</Label>
                        <Input
                            id="password"
                            type="password"
                            value={formData.password}
                            onChange={(e) => handleChange('password', e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="dbname" className="text-right">DB Name</Label>
                        <Input
                            id="dbname"
                            value={formData.database_name}
                            onChange={(e) => handleChange('database_name', e.target.value)}
                            className="col-span-3"
                        />
                    </div>
                    <div className="grid grid-cols-4 gap-4">
                        <Label htmlFor="desc" className="text-right pt-2">Description</Label>
                        <Input
                            id="desc"
                            value={formData.db_description || ''}
                            onChange={(e) => handleChange('db_description', e.target.value)}
                            placeholder="E.g. Sales data 2024 (Optional)"
                            className="col-span-3"
                        />
                    </div>

                    {error && (
                        <div className="text-sm text-red-500 text-right">{error}</div>
                    )}
                    {testResult && (
                        <div className={`text-sm text-right ${testResult.valid ? 'text-green-500' : 'text-red-500'}`}>
                            {testResult.message}
                        </div>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={handleTest} disabled={testing || loading}>
                        {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Test Connection
                    </Button>
                    <Button onClick={handleSave} disabled={loading || testing}>
                        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Save Connection
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
