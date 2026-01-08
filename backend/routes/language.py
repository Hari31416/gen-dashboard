from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import BaseModel
from services.language import detect_language, translate_text
from utilities import create_simple_logger

logger = create_simple_logger(__name__)
router = APIRouter(prefix="/language", tags=["language services"])


class LangugateDetectionRequest(BaseModel):
    query: str


class LanguageTranslationRequest(BaseModel):
    text: str
    source: str
    destination: str


@router.post("/detect")
async def detect_language_endpoint(request: LangugateDetectionRequest):
    try:
        lang = detect_language(request.query)
        logger.info(f"Detected language: {lang}")
        return JSONResponse(content={"language": lang})
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return JSONResponse(content={"Error detecting language"}, status_code=500)


@router.post("/translate")
async def translate_language_endpoint(request: LanguageTranslationRequest):
    try:
        translated_text = translate_text(
            request.text, request.source, request.destination
        )
        logger.info(f"Translated text: {translated_text}")
        return JSONResponse(content={"translated_text": translated_text})
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        return JSONResponse(content={"Error translating text"}, status_code=500)
