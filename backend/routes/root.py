from routes.auth import get_current_active_user, User
from services.agents.csv_agent import get_csv_agent_answer
from env import (
    MONGO_URI,
    QUERY_SUGGESTION_GENERATION_MODEL,
    ARTIFACT_STORAGE_ENABLED,
    S3_ENDPOINT_URL,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
    LLM_MODEL,
)
from utilities import create_simple_logger
from services.language import process_incoming_text, process_outgoing_text
from services.agents.query_suggestion import get_query_suggestions_from_llm
from services.artifact_storage import ArtifactStorageService
from pydantic_models.artifact_models import DataContext
from services.usage_service import check_user_token_limit
from services.artifact_utils import (
    prepare_artifact_data,
    format_langchain_execution_code,
    build_data_context,
    decode_base64_html,
)

from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Union
import time
import pandas as pd
import uuid
from services.usage_service import log_query_usage


logger = create_simple_logger(__name__)
router = APIRouter(prefix="", tags=["root"])


# Initialize artifact storage service if enabled
artifact_service = None
if ARTIFACT_STORAGE_ENABLED:
    try:
        artifact_service = ArtifactStorageService(
            endpoint_url=S3_ENDPOINT_URL,
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
        )
        logger.info("Artifact storage service initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize artifact storage: {e}")
        artifact_service = None


@router.get("/")
async def root():
    return JSONResponse(
        content={"message": "Welcome to the Generative Business Intelligence"}
    )


@router.get("/health")
async def health():
    return JSONResponse(
        content={"message": "Welcome to the Generative Business Intelligence"}
    )


def make_json_compliant(data):
    """
    Recursively process data to ensure JSON compliance by replacing NaN and Inf values.

    Args:
        data: The data to be processed (can be dict, list, or primitive types)
    Returns:
        JSON-compliant data with NaN and Inf replaced by None
    """
    if isinstance(data, dict):
        return {k: make_json_compliant(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_compliant(item) for item in data]
    elif isinstance(data, float):
        if pd.isna(data) or data == float("inf") or data == float("-inf"):
            return None
        else:
            return data
    else:
        return data


class QueryRequest(BaseModel):
    query: str = Field(..., description="User query text")
    username: str = Field(default="citizen", description="Username")
    file_name: Optional[str] = Field(None, description="Specific CSV file to query")
    connection_name: Optional[str] = Field(None, description="Database connection name")
    table_name: Optional[str] = Field(None, description="Specific table to query")
    language: str = Field(default="en", description="Query language")
    conversation_id: Optional[str] = Field(
        None, description="Conversation ID for  multi-turn"
    )
    parent_turn_id: Optional[str] = Field(
        None, description="Parent turn ID for context"
    )
    skip_stages: Optional[List[int]] = None


class LangChainQueryRequest(BaseModel):
    """Request model for LangChain agent queries."""

    query: str = Field(..., description="User query text")
    username: str = Field(default="citizen", description="Username")
    connection_name: Optional[str] = Field(
        None, description="Database connection name (optional)"
    )
    file_name: Optional[str] = Field(
        None, description="Specific CSV file to query (optional)"
    )
    table_name: Optional[str] = Field(
        None, description="Specific table to query (optional)"
    )
    language: str = Field(default="en", description="Query language")
    conversation_id: Optional[str] = Field(
        None, description="Conversation ID for  multi-turn"
    )
    parent_turn_id: Optional[str] = Field(
        None, description="Parent turn ID for context"
    )
    skip_stages: Optional[List[int]] = None


async def _save_query_artifacts(
    username: str,
    query: str,
    csv_agent_answer: dict,
    file_name: Optional[str],
    connection_name: Optional[str],
    table_name: Optional[str],
    runtime_seconds: float,
    language: str = "en",
    conversation_id: Optional[str] = None,
    parent_turn_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Save query artifacts to S3 storage.
    Supports both legacy single-query and multi-turn conversation modes.

    Args:
        username: Username
        query: Original query text
        csv_agent_answer: Response from CSV agent
        file_name: CSV file name if used
        connection_name: Database connection name if used
        table_name: Database table name if used
        runtime_seconds: Query execution time
        language: Query/response language
        conversation_id: Conversation ID (if multi-turn)
        parent_turn_id: Parent turn ID (if multi-turn)

    Returns:
        Dict with artifact info or None if saving failed
    """
    if not artifact_service:
        return None

    try:
        # Use artifact_utils to prepare artifact data

        artifact_data = prepare_artifact_data(
            username=username,
            csv_agent_answer=csv_agent_answer,
            file_name=file_name,
            connection_name=connection_name,
            table_name=table_name,
        )

        # Save artifacts using unified method (always creates conversation)
        # save_query_artifacts now auto-creates conversation if not provided
        artifact_result = await artifact_service.save_query_artifacts(
            username=username,
            query=query,
            code=artifact_data["code"],
            plot_html=artifact_data["plot_html"],
            insight=artifact_data["insight"],
            json_data=artifact_data["json_data"],
            plotly_fig_json=artifact_data["plotly_fig_json"],
            data_context=artifact_data["data_context"],
            runtime_seconds=runtime_seconds,
            model_used=LLM_MODEL,
            language=language,
            conversation_id=conversation_id,
            parent_turn_id=parent_turn_id,
        )

        if artifact_result.get("success"):
            logger.info(
                f"Saved turn artifacts for turn_id={artifact_result.get('turn_id')}, "
                f"conversation_id={artifact_result.get('conversation_id')}"
            )
            return {
                "turn_id": artifact_result.get("turn_id"),
                "conversation_id": artifact_result.get("conversation_id"),
                "s3_path": artifact_result.get("s3_path"),
            }
        else:
            logger.warning(f"Failed to save artifacts: {artifact_result.get('error')}")
            return None

    except Exception as e:
        logger.error(f"Error saving artifacts: {e}", exc_info=True)
        return None


async def _get_presigned_url(response: dict, username: str, artifact_info: dict):
    artifact_data = await artifact_service.get_artifact_with_urls(
        username=username,
        query_hash=artifact_info["turn_id"],
        version="latest",
        expiration=3600,
    )
    logger.info(f"Artifact data retrieved: {artifact_data is not None}")
    if artifact_data:
        logger.info(
            f"Artifact presigned_urls keys: {list(artifact_data.get('presigned_urls', {}).keys())}"
        )

    presigned_urls = {}
    # Replace base64 image with presigned URL
    if response.get("image") and artifact_info.get("turn_id"):
        try:
            if artifact_data and artifact_data.get("presigned_urls", {}).get("plot"):
                presigned_urls["plot"] = artifact_data["presigned_urls"]["plot"]
                logger.info("Added plot presigned URL")
        except Exception as e:
            logger.warning(f"Failed to get presigned URL for plot: {e}")

    # Get plotly_fig_json presigned URL
    if artifact_info.get("turn_id"):
        try:
            if artifact_data and artifact_data.get("presigned_urls", {}).get(
                "plotly_fig_json"
            ):
                presigned_urls["plotly_fig_json"] = artifact_data["presigned_urls"][
                    "plotly_fig_json"
                ]
                logger.info("Added plotly_fig_json presigned URL")
        except Exception as e:
            logger.warning(f"Failed to get presigned URL for plotly_fig_json: {e}")

    # get code presigned urls
    logger.info(
        f"Checking for code: codes_generated exists={response.get('codes_generated') is not None}, turn_id={artifact_info.get('turn_id')}"
    )
    if response.get("codes_generated") and artifact_info.get("turn_id"):
        try:
            if artifact_data and artifact_data.get("presigned_urls", {}).get("code"):
                presigned_urls["code"] = artifact_data["presigned_urls"]["code"]
                logger.info(f"Added code presigned URL: {presigned_urls['code']}")
            else:
                logger.warning("Code presigned URL not found in artifact_data")
        except Exception as e:
            logger.warning(f"Failed to get presigned URL for code: {e}")
    else:
        logger.info("Skipping code URL - codes_generated not present or no turn_id")

    logger.info(f"Final presigned_urls: {list(presigned_urls.keys())}")

    response["_artifact_info"] = artifact_info
    response["conversation_id"] = artifact_info.get("conversation_id")
    response["turn_id"] = artifact_info.get("turn_id")
    response["presigned_url"] = presigned_urls

    return response


@router.post("/query")
async def query(
    request: QueryRequest, current_user: User = Depends(get_current_active_user)
):
    start_time = time.time()

    if not request.user_name:
        request.user_name = current_user.username
        logger.info(f"Using authenticated username: {current_user.username}")
    # Check token limit before processing query
    is_within_limit, usage_info = check_user_token_limit(request.user_name)
    if not is_within_limit:
        if "error" in usage_info:
            error_msg = f"Token limit check failed: {usage_info['error']}"
        else:
            error_msg = (
                f"Token usage limit exceeded. You have used {usage_info.get('tokens_used', 0):,} tokens "
                f"out of your allocated {usage_info.get('token_limit', 0):,} tokens "
                f"({usage_info.get('percentage_used', 0)}% used). "
                "Please contact your administrator to increase your limit."
            )
        logger.warning(
            f"Token limit exceeded for user {request.user_name}: {usage_info}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    file_name = request.file_name
    connection_name = request.connection_name
    table_name = request.table_name

    if file_name and file_name in ["", "null", "none", None, "all"]:
        file_name = None

    if connection_name and connection_name in ["", "null", "none", None, "all"]:
        connection_name = None

    if table_name and table_name in ["", "null", "none", None, "all"]:
        table_name = None

    if file_name and connection_name:
        error_msg = (
            "Cannot provide both file_name and connection_name in the same query."
        )
        logger.error(error_msg)
        return JSONResponse(content={"error": error_msg}, status_code=400)

    translated_query = process_incoming_text(
        request.query, source_language=request.language
    )
    try:
        start_time = time.time()
        username = current_user.username
        query_text = translated_query
        file_name = file_name
        connection_name = connection_name
        table_name = table_name
        language = request.language
        conversation_id = request.conversation_id
        parent_turn_id = request.parent_turn_id
        skip_stages = request.skip_stages or []

        # Process incoming text (translation if needed)
        query = await process_incoming_text(query_text, source_language=language)

        logger.info(f"Query received: {query[:100]}...")

        # Get answer from CSV agent
        csv_agent_answer = await get_csv_agent_answer(
            query,
            username,
            MONGO_URI,
            filter_using_llm=True,
            file_name=file_name,
            connection_name=connection_name,
            table_name=table_name,
            skip_stages=skip_stages,
        )

        if "error" in csv_agent_answer:
            logger.warning(f"CSV agent returned error: {csv_agent_answer['error']}")
            return JSONResponse(
                content=csv_agent_answer,
                status_code=500,
            )

        # Process outgoing insights (translation if needed)
        insights = csv_agent_answer.get("insights", "")
        insights_translated = await process_outgoing_text(
            insights, target_language=language
        )
        csv_agent_answer["insights"] = insights_translated

        runtime_seconds = time.time() - start_time

        # Save artifacts
        artifact_info = await _save_query_artifacts(
            username=username,
            query=query,
            csv_agent_answer=csv_agent_answer,
            file_name=file_name,
            connection_name=connection_name,
            table_name=table_name,
            runtime_seconds=runtime_seconds,
            language=language,
            conversation_id=conversation_id,
            parent_turn_id=parent_turn_id,
        )

        # Add artifact info and conversation_id to response
        if artifact_info:
            csv_agent_answer = await _get_presigned_url(
                csv_agent_answer, username, artifact_info
            )
        elif conversation_id:
            # If artifacts not saved but conversation_id was provided
            csv_agent_answer["conversation_id"] = conversation_id

        return JSONResponse(content=make_json_compliant(csv_agent_answer))

    except Exception as e:
        logger.exception("Query processing failed")
        return JSONResponse(
            content={"error": f"Query processing failed: {str(e)}"},
            status_code=500,
        )


@router.post("/langchain_query")
async def langchain_query(
    request: LangChainQueryRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Query endpoint for LangChain-based agents with unified schema integration.

    This endpoint:
    - Uses LangGraph main graph for orchestration
    - Integrates with MemoryAgent for conversation history
    - Saves all artifacts to unified MongoDB schema (conversations + turns)
    - Uploads execution artifacts to S3/MinIO
    """
    logger.info(f"Found request for LangChain query: {request}")
    start_time = time.time()
    username = current_user.username
    query_text = request.query
    file_name = request.file_name
    connection_name = request.connection_name
    table_name = request.table_name
    session_id = request.conversation_id
    parent_turn_id = request.parent_turn_id
    language = request.language
    skip_stages = request.skip_stages or []

    logger.info(f"LangChain query received: {query_text[:100]}...")

    try:
        # Create or get session
        if not session_id:
            # Create new conversation
            if artifact_service:
                res = await artifact_service.create_conversation(username=username)
                session_id = res.get("conversation_id")
                logger.info(f"Created new session: {session_id}")
            else:
                session_id = f"session_{uuid.uuid4().hex[:12]}"
                logger.warning("No artifact service, using temporary session ID")

        # Process incoming text (translation if needed)
        query = await process_incoming_text(query_text, source_language=language)

        # Run LangChain main graph
        from langchain_agents import run_query

        result = await run_query(
            user_query=query,
            username=username,
            file_name=file_name,
            connection_name=connection_name,
            table_name=table_name,
            session_id=session_id,
            use_memory=True,
            skip_stages=skip_stages,
        )
        if result.get("error"):
            logger.warning(f"LangChain graph returned error: {result['error']}")
            translated_error = await process_outgoing_text(
                result["error"], target_language=language
            )
            result["error"] = translated_error
            return JSONResponse(
                content={
                    "error": result["error"],
                    "session_id": session_id,
                },
                status_code=result.get("status_code", 500),
            )

        # Extract results
        insights = result.get("insights", "")
        final_response = result.get("final_response", "")
        if not insights and final_response:
            file_name = "Previous Context"
            insights = final_response
        else:
            file_name_ = connection_name or result.get("selected_connection")
            file_name = f"Data from connection: {file_name_}"

        visualization_image = result.get("visualization_image")
        error = result.get("error")
        plotly_fig_json = result.get("plotly_fig_json")

        # Get execution history
        tts_execution_history = result.get("tts_execution_history", [])
        analyzer_execution_history = result.get("analyzer_execution_history", [])
        sql_query = result.get("sql_query")
        analysis_data = result.get("analysis_data")

        # Serialize analysis_data if it's a DataFrame
        serialized_data = None
        if analysis_data is not None:
            if isinstance(analysis_data, pd.DataFrame):
                # Convert DataFrame to serializable format
                serialized_data = {
                    "_type": "dataframe",
                    "data": analysis_data.to_dict(orient="records"),
                    "columns": list(analysis_data.columns),
                    "shape": list(analysis_data.shape),
                }
            else:
                serialized_data = analysis_data

        # Format execution histories into unified code string
        combined_code = format_langchain_execution_code(
            tts_execution_history=tts_execution_history,
            analyzer_execution_history=analyzer_execution_history,
            sql_query=sql_query,
        )

        # Save turn artifacts directly using artifact_service
        # This ensures proper S3 upload and MongoDB storage
        artifact_res = {}
        data_context = build_data_context(
            username=username,
            connection_name=connection_name or result.get("selected_connection"),
            sql_query=sql_query,
        )
        data_type = type(analysis_data).__name__
        if isinstance(analysis_data, pd.DataFrame):
            analysis_data = analysis_data.to_dict(orient="records")

        if visualization_image:
            plot_html = decode_base64_html(visualization_image)
        else:
            plot_html = None

        if artifact_service:
            try:
                artifact_res = await artifact_service.save_turn_artifacts(
                    username=username,
                    conversation_id=session_id,
                    query=query,
                    insight=insights,
                    plot_html=plot_html,
                    plotly_fig_json=plotly_fig_json,
                    code=combined_code,
                    analyzer_execution_history=analyzer_execution_history,
                    tts_execution_history=tts_execution_history,
                    sql_query=sql_query,
                    final_data=serialized_data,
                    runtime_seconds=time.time() - start_time,
                    model_used=LLM_MODEL,
                    language=language,
                    data_context=data_context,
                    parent_turn_id=parent_turn_id,
                    json_data=analysis_data,
                )
                logger.info(f"Saved turn artifacts for session {session_id}")
            except Exception as e:
                logger.error(f"Error saving turn artifacts: {e}", exc_info=True)

        runtime_seconds = time.time() - start_time

        # Process outgoing insights (translation if needed)
        insights_translated = await process_outgoing_text(
            insights, target_language=language
        )

        # Build response in same format as /query endpoint

        response = {
            "conversation_id": session_id,
            "image": visualization_image,
            "plotly_fig_json": result.get("plotly_fig_json"),
            "json": (
                analysis_data if analysis_data is not None else None
            ),  # Analysis data
            "insights": insights_translated,
            "debug_info": {
                "session_id": session_id,  # Also keep in debug_info for backward compatibility
                "runtime_seconds": runtime_seconds,
                "data_type": data_type,
                "file_name": file_name,
            },
            "codes_generated": {
                "sql_query": sql_query,
                "tts_execution_history": tts_execution_history,
                "analyzer_execution_history": analyzer_execution_history,
            },
        }

        if error:
            response["error"] = error

        response = await _get_presigned_url(response, username, artifact_res)

        logger.info(f"LangChain query completed in {runtime_seconds:.2f}s")
        return JSONResponse(content=make_json_compliant(response))

    except Exception as e:
        logger.exception("LangChain query failed")
        return JSONResponse(
            content={
                "error": f"LangChain query failed: {str(e)}",
                "session_id": session_id if "session_id" in locals() else None,
            },
            status_code=500,
        )
