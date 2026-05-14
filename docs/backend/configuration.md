# Configuration Management

The backend manages runtime configuration and external API authentication using environment variables. Settings are loaded centrally to provide clean access across application services.

---

## 1. Environment Loading

At server startup, `backend/app.py` invokes environment loaders to parse configuration files into active scope:

```python
from dotenv import load_dotenv

# Loads variables from local .env files into active system environment
load_dotenv()
```

---

## 2. Configuration Parameters (`.env.example`)

The application expects specific environment properties to establish connections and interface with model providers:

```ini
# --- Core API Configuration ---
PORT=8000
ENVIRONMENT=development

# --- Security Authentication Keys ---
# Used to cryptographically sign JWT payload structures
SECRET_KEY="your-super-secret-key-change-in-production"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# --- Backing Storage Connectivity ---
# Connection string pointing to the persistent storage backing catalog
MONGODB_URI="mongodb://localhost:27017/"
MONGODB_DB_NAME="ai_dashboard"

# --- Model Provider Authentication ---
# Primary keys used to invoke upstream LLM generation pipelines
OPENAI_API_KEY="sk-proj-..."
GEMINI_API_KEY="AIzaSy..."
```

---

## 3. Configuration Defaults & Fallbacks

To simplify local development setups, configuration parsing modules apply sensible operational defaults if optional variables are missing:
- **`ACCESS_TOKEN_EXPIRE_MINUTES`**: Defaults to 1440 minutes (24 hours) if unspecified.
- **`ENVIRONMENT`**: Defaults to `development` mode, enabling detailed stack traces.
