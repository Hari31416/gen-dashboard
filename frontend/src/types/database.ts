export interface DatabaseConnectionRequest {
    host: string;
    port: number;
    username: string;
    password: string;
    database_name: string;
    connection_name: string;
    db_type: string;
    db_description?: string;
}

export interface DatabaseConnectionValidateRequest {
    host: string;
    port: number;
    username: string;
    password: string;
    database_name: string;
    db_type: string;
}

export interface DatabaseConnection {
    connection_name: string;
    host: string;
    port: number;
    username: string;
    database_name: string;
    db_type: string;
    fetched_at?: string;
    db_description?: string;
}

export interface ValidationResponse {
    valid: boolean;
    message: string;
    database_name?: string;
    error?: string;
}
