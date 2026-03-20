import os

from dotenv import load_dotenv

load_dotenv()

# ===== APPLICATION CONFIGURATION =====
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "citizen")

# ===== MONGODB CONFIGURATION =====
MONGO_USER = os.getenv("MONGO_USER", "admin")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "secret")
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_URI = os.getenv(
    "MONGO_URI", f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}"
)

# Backend URL for client-side data fetching (Vega charts)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "warning").upper()

# ===== LLM & AI MODEL CONFIGURATION =====
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia_nim/openai/gpt-oss-120b")
NUM_RETRIES = os.getenv("NUM_RETRIES", "0")
try:
    NUM_RETRIES = int(NUM_RETRIES)
except ValueError:
    print(f"Invalid NUM_RETRIES value: {NUM_RETRIES}. Defaulting to 0.")
    NUM_RETRIES = 0

# ===== BHASHINI TRANSLATION SERVICE =====
BHASHINI_ENDPOINT_URL = os.getenv("BHASHINI_ENDPOINT_URL")
BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY")
BHASHINI_LANG_DETECTION_SERVICE_ID = os.getenv("BHASHINI_LANG_DETECTION_SERVICE_ID")
BHASHINI_TRANSLATION_SERVICE_ID = os.getenv("BHASHINI_TRANSLATION_SERVICE_ID")

# ===== VISUALIZATION CONFIGURATION =====
MATPLOTLIB_COLOR_MODE = os.getenv("MATPLOTLIB_COLOR_MODE", "light").lower()
PLOTLY_COLOR_MODE = os.getenv("PLOTLY_COLOR_MODE", "light").lower()

# ===== DATABASE ENCRYPTION =====
DB_PASSWORD_ENCRYPTION_KEY = os.getenv("DB_PASSWORD_ENCRYPTION_KEY", None)
if DB_PASSWORD_ENCRYPTION_KEY is None:
    print(
        "Warning: DB_PASSWORD_ENCRYPTION_KEY is not set. A new key will be generated at runtime."
    )
