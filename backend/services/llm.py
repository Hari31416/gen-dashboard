from litellm import acompletion, completion
from typing import List, Any, AsyncGenerator, Dict, Optional, Union, Tuple
import os
import time
from utilities import create_simple_logger
from env import NUM_RETRIES, LLM_MODEL

logger = create_simple_logger(__name__)


class LLMCallError(Exception):
    """Custom exception for LLM call errors."""

    pass


async def atext_completion(
    messages: List[Dict[str, str]],
    **kwargs,
) -> Union[str, Tuple[str, Dict[str, int]]]:
    """
    Call an LLM via LiteLLM.

    - Retries: handled by LiteLLM's internal retry config if set globally.
    - Timeout: per-call via request_timeout (seconds).
    - Logs: start/end with timing, selected params, token usage if available.
    - Token limit warning: logs a warning if finish_reason indicates max token exhaustion.
    """
    # Extract return_usage before it gets consumed
    return_usage = kwargs.pop("return_usage", False)

    params = {
        "model": kwargs.get("model", LLM_MODEL),
        "messages": messages,
        "temperature": kwargs.get("temperature"),
        "max_tokens": kwargs.get("max_tokens"),
        "num_retries": NUM_RETRIES,
    }

    params.update({k: v for k, v in kwargs.items() if v is not None})

    # Log minimal, non-sensitive info
    _log_params = {
        "model": params.get("model"),
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_tokens"),
    }
    logger.info(f"LLM call start: {_log_params}")

    start_ts = time.time()

    try:
        resp = await acompletion(**params)
    except Exception as e:
        elapsed = round(time.time() - start_ts, 3)
        logger.error(f"LLM call error after {elapsed}s: {e}")
        raise LLMCallError(f"LLM call failed: {e}") from e

    elapsed = round(time.time() - start_ts, 3)

    text = ""
    try:
        text = resp.choices[0].message["content"]
    except Exception:
        logger.warning(
            "Could not extract text from resp.choices[0].message['content'], trying alternatives."
        )
        if hasattr(resp, "choices") and len(resp.choices) > 0:
            choice0 = resp.choices
            text = (
                getattr(choice0, "text", None)
                or getattr(choice0, "message", {}).get("content", "")
                or str(resp)
            )
        else:
            text = str(resp)

    # Token usage and finish reason (if provided by provider/adapter)
    usage = getattr(resp, "usage", None) or {}
    prompt_tokens = getattr(usage, "prompt_tokens", None) or usage.get(
        "prompt_tokens", 0
    )
    completion_tokens = getattr(usage, "completion_tokens", None) or usage.get(
        "completion_tokens", 0
    )
    total_tokens = getattr(usage, "total_tokens", None) or usage.get("total_tokens", 0)

    usage_dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

    # Some providers return finish_reason on the choice
    finish_reason = None
    try:
        finish_reason = resp.choices[0].finish_reason
    except Exception:
        # Some adapters may place it elsewhere or omit it
        finish_reason = None

    # Log and handle finish reasons
    if finish_reason:
        if finish_reason.lower() == "stop":
            model = params.get("model", "unknown")
            logger.info(
                f"LLM call end: model={model} elapsed={elapsed:.3f}s "
                f"usage(prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}) "
                f"finish_reason={finish_reason}"
            )
        elif str(finish_reason).lower() == "content_filter":
            logger.error("LLM response was blocked by content filter.")
            raise LLMCallError("LLM response was blocked by content filter.")
        elif str(finish_reason).lower() in {"length", "max_tokens"}:
            max_tokens = params.get("max_tokens", "unknown")
            token_exhausted_message = f"LLM hit max token limit (max_tokens={max_tokens}). Response may be incomplete."
            logger.warning(token_exhausted_message)

    # Return based on return_usage flag
    if return_usage:
        return text, usage_dict

    return text


def text_completion(
    messages: List[Dict[str, str]],
    **kwargs,
) -> Union[str, Tuple[str, Dict[str, int]]]:
    """
    Call an LLM via LiteLLM.

    - Retries: handled by LiteLLM's internal retry config if set globally.
    - Timeout: per-call via request_timeout (seconds).
    - Logs: start/end with timing, selected params, token usage if available.
    - Token limit warning: logs a warning if finish_reason indicates max token exhaustion.
    """
    # Extract return_usage before it gets consumed
    return_usage = kwargs.pop("return_usage", False)

    params = {
        "model": kwargs.get("model", LLM_MODEL),
        "messages": messages,
        "temperature": kwargs.get("temperature"),
        "max_tokens": kwargs.get("max_tokens"),
        "num_retries": NUM_RETRIES,
    }

    params.update({k: v for k, v in kwargs.items() if v is not None})

    # Log minimal, non-sensitive info
    _log_params = {
        "model": params.get("model"),
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_tokens"),
    }
    logger.info(f"LLM call start: {_log_params}")

    start_ts = time.time()

    try:
        resp = completion(**params)
    except Exception as e:
        elapsed = round(time.time() - start_ts, 3)
        logger.error(f"LLM call error after {elapsed}s: {e}")
        raise LLMCallError(f"LLM call failed: {e}") from e

    elapsed = round(time.time() - start_ts, 3)

    text = ""
    try:
        text = resp.choices[0].message["content"]
    except Exception:
        logger.warning(
            "Could not extract text from resp.choices[0].message['content'], trying alternatives."
        )
        if hasattr(resp, "choices") and len(resp.choices) > 0:
            choice0 = resp.choices
            text = (
                getattr(choice0, "text", None)
                or getattr(choice0, "message", {}).get("content", "")
                or str(resp)
            )
        else:
            text = str(resp)

    # Token usage and finish reason (if provided by provider/adapter)
    usage = getattr(resp, "usage", None) or {}
    prompt_tokens = getattr(usage, "prompt_tokens", None) or usage.get(
        "prompt_tokens", 0
    )
    completion_tokens = getattr(usage, "completion_tokens", None) or usage.get(
        "completion_tokens", 0
    )
    total_tokens = getattr(usage, "total_tokens", None) or usage.get("total_tokens", 0)

    usage_dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

    # Some providers return finish_reason on the choice
    finish_reason = None
    try:
        finish_reason = resp.choices[0].finish_reason
    except Exception:
        # Some adapters may place it elsewhere or omit it
        finish_reason = None

    # Log and handle finish reasons
    if finish_reason:
        if finish_reason.lower() == "stop":
            model = params.get("model", "unknown")
            logger.info(
                f"LLM call end: model={model} elapsed={elapsed:.3f}s "
                f"usage(prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}) "
                f"finish_reason={finish_reason}"
            )
        elif str(finish_reason).lower() == "content_filter":
            logger.error("LLM response was blocked by content filter.")
            raise LLMCallError("LLM response was blocked by content filter.")
        elif str(finish_reason).lower() in {"length", "max_tokens"}:
            max_tokens = params.get("max_tokens", "unknown")
            token_exhausted_message = f"LLM hit max token limit (max_tokens={max_tokens}). Response may be incomplete."
            logger.warning(token_exhausted_message)

    # Return based on return_usage flag
    if return_usage:
        return text, usage_dict

    return text


async def atext_completion_stream(
    messages: List[Dict[str, Any]], **kwargs: Dict
) -> AsyncGenerator[str, None]:
    """Async generator yielding incremental completion chunks without duplicates."""
    if "stream" not in kwargs:
        kwargs["stream"] = True
    kwargs["stream"] = True
    if "model" not in kwargs:
        kwargs["model"] = LLM_MODEL
    if "num_retries" not in kwargs:
        kwargs["num_retries"] = NUM_RETRIES
    try:
        response_stream = await acompletion(
            messages=messages,
            **kwargs,
        )
    except Exception as e:
        print(f"Error during async streaming completion: {e}")
        raise e

    assembled = ""
    async for chunk in response_stream:
        try:
            choice = (
                chunk["choices"][0] if isinstance(chunk, dict) else chunk.choices[0]
            )
        except Exception:
            continue

        delta = None
        if isinstance(choice, dict):
            delta = choice.get("delta") or choice.get("message")
        else:
            delta = getattr(choice, "delta", None) or getattr(choice, "message", None)

        token = ""
        if delta is not None:
            if isinstance(delta, dict):
                token = delta.get("content") or ""
            else:
                token = getattr(delta, "content", "") or ""

        if not token:
            continue

        if token.startswith(assembled):
            new_part = token[len(assembled) :]
        else:
            new_part = token
        if new_part:
            assembled += new_part
            yield new_part
