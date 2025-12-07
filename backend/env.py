from dotenv import load_dotenv
import os

load_dotenv()


DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "citizen")


MONGO_USER = os.getenv("MONGO_USER", "admin")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "secret")
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_URI = os.getenv(
    "MONGO_URI", f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}"
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "warning").upper()
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia_nim/openai/gpt-oss-120b")
QUERY_SUGGESTION_GENERATION_MODEL = os.getenv(
    "QUERY_SUGGESTION_GENERATION_MODEL", LLM_MODEL
)
REPORT_GENERATION_MODEL = os.getenv("REPORT_GENERATION_MODEL", LLM_MODEL)
TITLE_GENERATION_MODEL = os.getenv(
    "TITLE_GENERATION_MODEL", QUERY_SUGGESTION_GENERATION_MODEL
)
NUM_RETRIES = os.getenv("NUM_RETRIES", "0")
try:
    NUM_RETRIES = int(NUM_RETRIES)
except ValueError:
    print(f"Invalid NUM_RETRIES value: {NUM_RETRIES}. Defaulting to 0.")
    NUM_RETRIES = 0


BHASHINI_ENDPOINT_URL = os.getenv("BHASHINI_ENDPOINT_URL")
BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY")
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID")
BHASHINI_LANG_DETECTION_SERVICE_ID = os.getenv("BHASHINI_LANG_DETECTION_SERVICE_ID")
BHASHINI_TRANSLATION_SERVICE_ID = os.getenv("BHASHINI_TRANSLATION_SERVICE_ID")


USE_RAG_FOR_DATA_SELECTION = (
    os.getenv("USE_RAG_FOR_DATA_SELECTION", "false").lower() == "true"
)
MATPLOTLIB_COLOR_MODE = os.getenv("MATPLOTLIB_COLOR_MODE", "light").lower()
PLOTLY_COLOR_MODE = os.getenv("PLOTLY_COLOR_MODE", "light").lower()
DB_PASSWORD_ENCRYPTION_KEY = os.getenv("DB_PASSWORD_ENCRYPTION_KEY", None)
if DB_PASSWORD_ENCRYPTION_KEY is None:
    print(
        "Warning: DB_PASSWORD_ENCRYPTION_KEY is not set. A new key will be generated at runtime."
    )

MAX_ROWS_FETCH_DB_TABLE = int(
    os.getenv("MAX_ROWS_FETCH_DB_TABLE", 1_000_000)
)  # 1 million
try:
    MAX_ROWS_FETCH_DB_TABLE = int(MAX_ROWS_FETCH_DB_TABLE)
except ValueError:
    print(
        f"Invalid MAX_ROWS_FETCH_DB_TABLE value: {MAX_ROWS_FETCH_DB_TABLE}. Defaulting to 1,000,000."
    )
    MAX_ROWS_FETCH_DB_TABLE = 1_000_000

USE_SAFE_EXECUTOR = (
    os.getenv("USE_SAFE_EXECUTOR", "true").lower() == "true"
)  # Default to true

# Artifact Storage Configuration (S3/MinIO)
ARTIFACT_STORAGE_ENABLED = (
    os.getenv("ARTIFACT_STORAGE_ENABLED", "false").lower() == "true"
)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", None)  # For MinIO or custom S3
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", os.getenv("AWS_ACCESS_KEY_ID"))
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", os.getenv("AWS_SECRET_ACCESS_KEY"))
S3_REGION = os.getenv("S3_REGION", os.getenv("AWS_REGION", "us-east-1"))


USE_PANDOC_FOR_PDF_CONVERSION = (
    os.getenv("USE_PANDOC_FOR_PDF_CONVERSION", "false").lower() == "true"
)

MARIADB_USER = os.getenv("MARIADB_USER", "root")
MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "password")
MARIADB_HOST = os.getenv("MARIADB_HOST", "mariadb")
# If connecting to localhost, assume we are outside docker and need the exposed port 3307
# If connecting to mariadb (docker service), use internal port 3306
_default_port = "3307" if MARIADB_HOST in ["localhost", "127.0.0.1"] else "3306"
MARIADB_PORT = os.getenv("MARIADB_PORT", _default_port)
MARIADB_URI = os.getenv(
    "MARIADB_URI",
    f"mysql+pymysql://{MARIADB_USER}:{MARIADB_PASSWORD}@{MARIADB_HOST}:{MARIADB_PORT}",
)
