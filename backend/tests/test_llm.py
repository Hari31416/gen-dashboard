from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.llm import (
    LLMCallError,
    atext_completion,
    atext_completion_stream,
    text_completion,
)


@pytest.fixture
def mock_litellm_acompletion():
    with patch("services.llm.acompletion", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_litellm_completion():
    with patch("services.llm.completion") as mock:
        yield mock


@pytest.mark.asyncio
async def test_atext_completion_success(mock_litellm_acompletion):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = {"content": "Hello World"}
    mock_response.usage = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    mock_response.choices[0].finish_reason = "stop"

    mock_litellm_acompletion.return_value = mock_response

    messages = [{"role": "user", "content": "Hi"}]
    result = await atext_completion(messages)

    assert result == "Hello World"
    mock_litellm_acompletion.assert_called_once()

    # Check arguments
    call_kwargs = mock_litellm_acompletion.call_args[1]
    assert call_kwargs["messages"] == messages


@pytest.mark.asyncio
async def test_atext_completion_error(mock_litellm_acompletion):
    mock_litellm_acompletion.side_effect = Exception("API Error")

    with pytest.raises(LLMCallError, match="LLM call failed"):
        await atext_completion([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_atext_completion_return_usage(mock_litellm_acompletion):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = {"content": "Answer"}
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30

    mock_litellm_acompletion.return_value = mock_response

    text, usage = await atext_completion(
        [{"role": "user", "content": "Hi"}], return_usage=True
    )

    assert text == "Answer"
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 20
    assert usage["total_tokens"] == 30


@pytest.mark.asyncio
async def test_atext_completion_content_filter(mock_litellm_acompletion):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = {"content": "Bad content"}
    mock_response.choices[0].finish_reason = "content_filter"

    mock_litellm_acompletion.return_value = mock_response

    with pytest.raises(LLMCallError, match="blocked by content filter"):
        await atext_completion([{"role": "user", "content": "Hi"}])


def test_text_completion_success(mock_litellm_completion):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = {"content": "Sync Hello"}
    mock_response.usage = {
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": 10,
    }
    mock_response.choices[0].finish_reason = "stop"

    mock_litellm_completion.return_value = mock_response

    result = text_completion([{"role": "user", "content": "Hi"}])

    assert result == "Sync Hello"
    mock_litellm_completion.assert_called_once()


@pytest.mark.asyncio
async def test_atext_completion_stream_success(mock_litellm_acompletion):
    # Setup async generator mock
    async def async_gen():
        chunks = [
            {"choices": [{"delta": {"content": "H"}}]},
            {"choices": [{"delta": {"content": "e"}}]},
            {"choices": [{"delta": {"content": "llo"}}]},
        ]
        for chunk in chunks:
            yield chunk

    mock_litellm_acompletion.return_value = async_gen()

    messages = [{"role": "user", "content": "Hi"}]
    chunks = []
    async for chunk in atext_completion_stream(messages):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello"
