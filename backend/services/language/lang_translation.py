from env import (
    BHASHINI_API_KEY,
    BHASHINI_ENDPOINT_URL,
    BHASHINI_TRANSLATION_SERVICE_ID,
)
from utilities import create_simple_logger

import requests
import json

logger = create_simple_logger(__name__)


def translate_text(text: str, source: str, destination: str) -> str:
    if source == destination:
        logger.info(
            "Source and destination languages are the same. No translation needed."
        )
        return text

    logger.info(f"Text sent for translation, Query Text: {text}")
    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source,
                        "targetLanguage": destination,
                    },
                    "serviceId": BHASHINI_TRANSLATION_SERVICE_ID,
                },
            }
        ],
        "inputData": {"input": [{"source": text}]},
    }
    headers = {
        "Authorization": BHASHINI_API_KEY,
        "Content-Type": "application/json",
    }

    response = requests.request(
        "POST", BHASHINI_ENDPOINT_URL, headers=headers, data=json.dumps(payload)
    )
    response.raise_for_status()
    translated_text = response.json()["pipelineResponse"][0]["output"][0]["target"]

    if (
        translated_text is None
        or translated_text == ""
        or len(translated_text)
        < min(3, len(text) // 2)  # avoid cases like single char translation
    ):
        error_message = (
            f"Translated text (translated_text={translated_text}) is too short or empty"
        )
        logger.error(error_message)
        raise ValueError(error_message)

    logger.info(f"Translation completed, Translated Text: {translated_text}")

    return translated_text
