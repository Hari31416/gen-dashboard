# Environment Variables

This reference lists configuration settings used across frontend and backend environments.

---

## 1. Backend Settings (`backend/.env`)

| Variable Name | Purpose | Example Value | Default Value | Required |
| :--- | :--- | :--- | :--- | :--- |
| `PORT` | API server listen port | `8000` | `8000` | No |
| `ENVIRONMENT` | Operational environment mode | `development` | `development` | No |
| `SECRET_KEY` | Symmetric key signing JWT profiles | `change-me-123` | None | Yes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration duration | `1440` | `1440` | No |
| `MONGODB_URI` | Connection URI to persistent session store | `mongodb://localhost:27017/` | `mongodb://localhost:27017/` | No |
| `MONGODB_DB_NAME` | Active MongoDB storage collection space | `ai_dashboard` | `ai_dashboard` | No |
| `OPENAI_API_KEY` | Upstream OpenAI model invocation key | `sk-proj-...` | None | Yes |
| `GEMINI_API_KEY` | Upstream Google Gemini invocation key | `AIzaSy...` | None | Optional |

---

## 2. Frontend Settings (`frontend/.env`)

| Variable Name | Purpose | Example Value | Default Value | Required |
| :--- | :--- | :--- | :--- | :--- |
| `VITE_API_URL` | Base REST path pointing to API Server gateway | `http://localhost:8000` | `/` | No |
