import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, Lock } from 'lucide-react';
import axios from 'axios';

export function DebugLogin() {
    const [loading, setLoading] = useState(false);

    const handleLogin = async () => {
        setLoading(true);
        try {
            // Using default credentials from backend/setup_admin_user.py
            const formData = new FormData();
            formData.append('username', 'admin');
            formData.append('password', 'PassWord@1234');

            const response = await axios.post('/api/auth/token', formData);

            if (response.data.access_token) {
                localStorage.setItem('token', response.data.access_token);
                // Force reload to apply token to interceptors
                window.location.reload();
            }
        } catch (error) {
            console.error("Login failed", error);
            alert("Dev login failed. Make sure backend is running and 'admin' user exists.");
        } finally {
            setLoading(false);
        }
    };

    // If we have a token, don't show the button (or show logout)
    if (localStorage.getItem('token')) {
        return null;
    }

    return (
        <Button onClick={handleLogin} disabled={loading} variant="destructive" size="sm">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lock className="mr-2 h-4 w-4" />}
            Dev Login (admin)
        </Button>
    );
}
