import axios from 'axios';
import type {
    DashboardGenerateRequest,
    DashboardRefineRequest,
    DashboardRefreshRequest,
    DashboardResponse,
    DashboardFilterRequest,
    LayoutConfig
} from '@/types/dashboard';

const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const authApi = {
    login: async (username: string, password: string): Promise<{ access_token: string; token_type: string }> => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        const response = await api.post('/auth/token', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
    getMe: async (): Promise<any> => {
        const response = await api.get('/auth/me');
        return response.data;
    }
};

export const dashboardApi = {
    generate: async (request: DashboardGenerateRequest): Promise<DashboardResponse> => {
        const response = await api.post<DashboardResponse>('/dashboard/generate', request);
        return response.data;
    },
    refine: async (request: DashboardRefineRequest): Promise<DashboardResponse> => {
        const response = await api.post<DashboardResponse>('/dashboard/refine', request);
        return response.data;
    },
    refresh: async (request: DashboardRefreshRequest): Promise<DashboardResponse> => {
        const response = await api.post<DashboardResponse>('/dashboard/refresh', request);
        return response.data;
    },
    filter: async (request: DashboardFilterRequest): Promise<DashboardResponse> => {
        const response = await api.post<DashboardResponse>('/dashboard/filter', request);
        return response.data;
    },
    updateLayout: async (sessionId: string, layoutConfig: LayoutConfig): Promise<{ success: boolean; message: string; session_id: string }> => {
        const response = await api.patch(`/dashboard/sessions/${sessionId}/layout`, {
            layout_config: layoutConfig
        });
        return response.data;
    },
    deleteChart: async (sessionId: string, chartId: string): Promise<DashboardResponse> => {
        const response = await api.delete(`/dashboard/${sessionId}/chart/${chartId}`);
        return response.data;
    },
    updateChartCustomizations: async (
        sessionId: string,
        customizations: Record<string, unknown>
    ): Promise<{ success: boolean; message: string; session_id: string }> => {
        const response = await api.patch(`/dashboard/sessions/${sessionId}/customizations`, {
            customizations
        });
        return response.data;
    },
};

import type {
    DatabaseConnection,
    DatabaseConnectionRequest,
    DatabaseConnectionValidateRequest,
    ValidationResponse
} from '@/types/database';

export const databaseApi = {
    list: async (): Promise<{ connections: DatabaseConnection[], count: number }> => {
        const response = await api.get<{ connections: DatabaseConnection[], count: number }>('/database/connections');
        return response.data;
    },
    create: async (request: DatabaseConnectionRequest): Promise<{ message: string, connection: DatabaseConnection }> => {
        const response = await api.post('/database/connect', request);
        return response.data;
    },
    validate: async (request: DatabaseConnectionValidateRequest): Promise<ValidationResponse> => {
        const response = await api.post('/database/validate', request);
        return response.data;
    },
    delete: async (connection_name: string): Promise<{ message: string }> => {
        const response = await api.delete(`/database/connections/${connection_name}`);
        return response.data;
    }
};

export const sessionsApi = {
    list: async (limit = 20, skip = 0): Promise<{ sessions: any[], count: number }> => {
        const response = await api.get(`/dashboard/sessions?limit=${limit}&skip=${skip}`);
        return response.data;
    },
    get: async (session_id: string): Promise<any> => {
        const response = await api.get(`/dashboard/sessions/${session_id}`);
        return response.data;
    },
    delete: async (session_id: string): Promise<{ message: string }> => {
        const response = await api.delete(`/dashboard/sessions/${session_id}`);
        return response.data;
    }
};
