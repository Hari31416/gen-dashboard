from utilities import create_simple_logger

from .lang_detection import detect_language
from .lang_translation import translate_text

logger = create_simple_logger(__name__)


async def process_incoming_text(text: str, source_language: str = "en") -> str:
    if source_language == "en":
        return text
    try:
        translated_text = translate_text(text, source_language, "en")
        return translated_text
    except Exception as e:
        logger.error(f"Translation failed: {e}. Using original text.")
        return text


async def process_outgoing_text(text: str, target_language: str = "en") -> str:
    if target_language == "en":
        return text
    try:
        translated_text = translate_text(text, "en", target_language)
        return translated_text
    except Exception as e:
        logger.error(f"Translation failed: {e}. Using original text.")
        return text
