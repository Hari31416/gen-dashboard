from env import (
    BHASHINI_API_KEY,
    BHASHINI_ENDPOINT_URL,
    BHASHINI_LANG_DETECTION_SERVICE_ID,
)
from utilities import create_simple_logger

import requests
import json

logger = create_simple_logger(__name__)


def detect_language(query: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": BHASHINI_API_KEY,
    }
    message = {
        "pipelineTasks": [
            {
                "taskType": "txt-lang-detection",
                "config": {"serviceId": BHASHINI_LANG_DETECTION_SERVICE_ID},
            }
        ],  # text translation
        "inputData": {"input": [{"source": query}]},
    }
    response = requests.post(
        BHASHINI_ENDPOINT_URL, headers=headers, json=message
    ).json()
    language = response["pipelineResponse"][0]["output"][0]["langPrediction"][0][
        "langCode"
    ]
    if not language:
        logger.warning(
            f"Language detection failed, for query: {query}. Using default 'en'."
        )
        language = "en"

    if language == "unknown":
        logger.warning(
            f"Language detection returned 'unknown' for query: {query}. Using default 'en'."
        )
        language = "en"

    return language
