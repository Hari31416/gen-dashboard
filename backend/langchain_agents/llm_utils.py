"""
LLM utilities for LangGraph agents.

This module provides LLM initialization and utilities that wrap
the existing litellm-based services/llm.py functionality to work
with LangChain/LangGraph.
"""

from typing import List, Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from services.llm import atext_completion, text_completion, LLMCallError
from env import LLM_MODEL
from utilities import create_simple_logger
import asyncio
import time

logger = create_simple_logger(__name__)


class LiteLLMChat(BaseChatModel):
    """
    Custom LangChain chat model that wraps our existing LiteLLM-based implementation.

    This allows us to use the existing services/llm.py infrastructure while
    getting the benefits of LangChain's abstractions.
    """

    model_name: str = LLM_MODEL
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    @property
    def _llm_type(self) -> str:
        return "litellm-custom"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _convert_messages_to_dict(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, str]]:
        """Convert LangChain messages to dict format for our LLM service."""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            else:
                # Default to user for unknown types
                result.append({"role": "user", "content": str(msg.content)})
        return result

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation using the existing text_completion."""
        dict_messages = self._convert_messages_to_dict(messages)

        try:
            start_time = time.time()
            response, usage = text_completion(
                messages=dict_messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                return_usage=True,
                **kwargs,
            )
            execution_time = time.time() - start_time

            message = AIMessage(
                content=response,
                response_metadata={
                    "token_usage": usage,
                    "execution_time": execution_time
                }
            )
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        except LLMCallError as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronous generation using the existing atext_completion."""
        dict_messages = self._convert_messages_to_dict(messages)

        try:
            start_time = time.time()
            response, usage = await atext_completion(
                messages=dict_messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                return_usage=True,
                **kwargs,
            )
            execution_time = time.time() - start_time

            message = AIMessage(
                content=response,
                response_metadata={
                    "token_usage": usage,
                    "execution_time": execution_time
                }
            )
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        except LLMCallError as e:
            logger.error(f"Async LLM call failed: {e}")
            raise


def get_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> LiteLLMChat:
    """
    Get an LLM instance for use with LangChain/LangGraph.

    Args:
        model_name: The model to use. Defaults to LLM_MODEL from env.
        temperature: Sampling temperature. Defaults to 0.7.
        max_tokens: Maximum tokens in response. Defaults to None (model default).

    Returns:
        A LiteLLMChat instance that can be used with LangChain.
    """
    return LiteLLMChat(
        model_name=model_name or LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def convert_dict_to_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    """
    Convert dict-format messages to LangChain message objects.

    Args:
        messages: List of dicts with 'role' and 'content' keys.

    Returns:
        List of LangChain message objects.
    """
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))

    return result


def convert_messages_to_dict(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """
    Convert LangChain message objects to dict format.

    Args:
        messages: List of LangChain message objects.

    Returns:
        List of dicts with 'role' and 'content' keys.
    """
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
        else:
            result.append({"role": "user", "content": str(msg.content)})
    return result
