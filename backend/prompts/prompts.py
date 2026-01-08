import os

from utilities import create_simple_logger

logger = create_simple_logger(__name__)
FILE_DIR = os.path.dirname(os.path.abspath(__file__))

FILE_PATH_MAPPING = {
    "react_tts_system_prompt": "REACT_TTS_SYSTEM.txt",
    "strategy_agent_system_prompt": "STRATEGY_AGENT_SYSTEM.txt",
    "data_agent_system_prompt": "DATA_AGENT_SYSTEM.txt",
    "viz_spec_agent_system_prompt": "VIZ_SPEC_AGENT_SYSTEM.txt",
    "layout_agent_system_prompt": "LAYOUT_AGENT_SYSTEM.txt",
}


def load_prompt_template(file_key: str) -> str:
    file_name = FILE_PATH_MAPPING.get(file_key)
    if not file_name:
        logger.error(f"File key '{file_key}' not found in mapping.")
        raise ValueError(f"File key '{file_key}' not found in mapping.")

    file_path = os.path.join(FILE_DIR, file_name)
    try:
        with open(file_path, "r") as file:
            content = file.read()
            logger.debug(f"Successfully loaded prompt template from {file_path}")
            return content
    except FileNotFoundError:
        logger.error(f"Prompt template file '{file_path}' not found.")
        return ""
    except Exception as e:
        logger.error(f"Error loading prompt template from '{file_path}': {e}")
        return ""


prompt_map = {key: load_prompt_template(key) for key in FILE_PATH_MAPPING.keys()}
