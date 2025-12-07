"""
ReAct TTS Agent for Text-to-SQL generation.

This agent uses the ReAct framework to:
1. Understand the user query
2. Inspect database schema and data
3. Generate and execute SQL queries
4. Return a pandas DataFrame with the results
"""

from typing import Dict, Any, Optional, List
import re
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_agents.llm_utils import get_llm
from langchain_agents.state import TTSGraphState
from langchain_agents.tools.database_tools import DatabaseTools
from langchain_agents.tools.code_execution import CodeExecutionTool
from services.local_python_interpreter import BASE_PYTHON_TOOLS

from services.database.db_config_models import (
    get_db_config,
    get_db_info,
    get_db_relationships,
)
from prompts import prompt_map
from utilities import create_simple_logger
from env import LLM_MODEL

logger = create_simple_logger(__name__)

MAX_REACT_ITERATIONS = 5


def convert_table_info(table_info: Dict) -> str:
    """Uses the following format:
    - Table Name (Table Description)
    - Columns:
        - Column Name (Data Type) [Column Description]

    """
    table_name = table_info["table_name"]
    table_description = table_info.get("table_description", "")
    columns = table_info["columns"]
    md_output = f"- {table_name}"
    if table_description:
        md_output += f" ({table_description.strip()})"
    md_output += "\n- Columns:\n"
    for column in columns:
        column_name = column["column_name"]
        data_type = column["data_type"]
        column_description = column.get("column_description", "")
        md_output += f"    - {column_name} ({data_type})"
        if column_description:
            md_output += f"[{column_description.strip()}]"
        md_output += "\n"
    return md_output.strip()


def convert_relationship_info(relationship: Dict) -> str:
    """Uses the following format:
    - Table1.ColumnA -> Table2.ColumnB (Join Type) [Relationship Description]
    """
    relationship_description = relationship.get("relationship_description", "")
    from_table = relationship["table_name"]
    to_table = relationship["related_table_name"]
    from_column = relationship["primary_key"]
    to_column = relationship["foreign_key"]
    relationship_type = relationship.get("relationship_type", "")
    md_output = f"- {from_table}.{from_column} -> {to_table}.{to_column}"
    if relationship_type:
        md_output += f" ({relationship_type})"
    if relationship_description:
        md_output += f" [{relationship_description.strip()}]"
    return md_output.strip()


def convert_tables_info(
    db_info: Dict, max_tables_to_consider: int = 50, tables: Optional[List[str]] = None
) -> str:
    if len(db_info["tables"]) > max_tables_to_consider:
        logger.info(
            f"Truncating tables from {len(db_info['tables'])} to {max_tables_to_consider} for SQL generation."
        )
        db_info["tables"] = db_info["tables"][:max_tables_to_consider]
    md_output = "## Tables\n\n"
    for table in db_info["tables"]:
        if tables and table["table_name"] not in tables:
            continue
        md_output += convert_table_info(table) + "\n\n"
    return md_output.strip()


def convert_relationships(
    relationships: Dict, max_relationships_to_consider: int = 100
) -> str:
    if relationships is None:
        return "## Relationships\n\nNo relationships available.\n"

    if relationships["relationships"] is None:
        return "## Relationships\n\nNo relationships available.\n"

    if len(relationships["relationships"]) == 0:
        return "## Relationships\n\nNo relationships available.\n"

    md_output = "## Relationships\n\n"
    if len(relationships["relationships"]) > max_relationships_to_consider:
        logger.info(
            f"Truncating relationships from {len(relationships['relationships'])} to {max_relationships_to_consider} for SQL generation."
        )
        relationships["relationships"] = relationships["relationships"][
            :max_relationships_to_consider
        ]
    for idx, relationship in enumerate(relationships["relationships"]):
        md_output += convert_relationship_info(relationship) + "\n\n"
    return md_output.strip()


def parse_sql_response(response: str) -> str:
    code_block_pattern = r"```sql(.*?)```"
    match = re.search(code_block_pattern, response, re.DOTALL)
    if match:
        sql_query = match.group(1).strip()
        return sql_query
    else:
        return response.strip()


def create_db_schema_input(
    db_info: Dict,
    relationships: Dict,
    user_query: str,
    max_tables_to_consider: int = 50,
    max_relationships_to_consider: int = 100,
) -> str:
    db_description = db_info.get("db_description", "")
    db_schema = convert_tables_info(db_info, max_tables_to_consider)
    db_relationships = convert_relationships(
        relationships, max_relationships_to_consider
    )
    dialect = db_info.get("db_type", "mysql").upper()

    prompt = f"""
Now generate the SQL query for the following input:
```
## Dialect
{dialect}

## Database Description
{db_description}

## Tables
{db_schema}

## Relationships
{db_relationships}

## User Question
{user_query}
```
"""
    return prompt.strip()


def check_for_sql_safety(sql_query: str) -> bool:
    """Returns True if the SQL query is safe, False otherwise."""
    unsafe_patterns = [
        r"\bDROP\s+TABLE\b",
        r"\bDELETE\s+FROM\b",
        r"\bTRUNCATE\s+TABLE\b",
        r"\bALTER\s+TABLE\b",
        r"\bUPDATE\s+\w+\s+SET\b(?!.*\bWHERE\b)",
    ]
    for pattern in unsafe_patterns:
        if re.search(pattern, sql_query, re.IGNORECASE):
            return False
    return True


async def react_tts_agent_node(state: TTSGraphState) -> Dict[str, Any]:
    """
    ReAct TTS agent node that generates SQL and retrieves data.

    This mirrors the logic from services/agents/react_tts_agent.py
    but as a LangGraph node.

    Args:
        state: The TTS graph state.

    Returns:
        Updated state with dataframe, sql_query, and execution history.
    """
    user_query = state.get("user_query", "")
    username = state.get("username", "")
    connection_name = state.get("selected_connection")
    table_name = state.get("table_name")
    if table_name:
        logger.info(f"User has specified table: {table_name}")

    if not connection_name:
        return {
            "error": "No database connection selected.",
            "dataframe": None,
            "sql_query": None,
        }

    logger.info(f"ReAct TTS processing query for connection: {connection_name}")

    try:
        # Initialize database tools
        db_tools = DatabaseTools(username, connection_name)

        # Get database config and info
        db_config = get_db_config(username, connection_name)

        if not db_config:
            return {
                "error": f"Database configuration not found for {connection_name}",
                "dataframe": None,
                "sql_query": None,
            }

        # Gather DB Context
        db_info = get_db_info(username, connection_name)
        db_description = db_config.get("db_description", "No description provided.")

        # Format context
        formatted_tables = convert_tables_info(
            db_info, tables=[table_name] if table_name else None
        )

        relationships = get_db_relationships(username, connection_name)
        formatted_relationships = convert_relationships(relationships)

        # Get system prompt
        system_prompt = prompt_map["react_tts_system_prompt"]
        # Initial context
        context = f"""User Query: {user_query}

Database Description: {db_description}

Available Tables:
{formatted_tables}

Relationships:
{formatted_relationships}
""".strip()

        # Initialize executor for code execution
        additional_imports = ["pandas", "numpy", "json", "io", "re", "datetime"]
        base_tools = BASE_PYTHON_TOOLS.copy()
        base_tools.update({"pd": pd})

        # Add database tools
        base_tools.update(db_tools.get_tools_as_functions())

        code_tool = CodeExecutionTool(additional_imports=additional_imports)
        code_tool.send_variables(base_tools)

        # Initialize conversation
        if table_name:
            context += f"\n\nUser has mentioned that they want to use the **table: {table_name}**. Please prioritize this table in your analysis. You should just use this table for SQL query generation. Use other tables only if necessary."
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context),
        ]

        execution_history: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

        llm = get_llm()
        final_sql = None

        # Track token usage
        total_tokens = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        total_execution_time = 0

        for iteration in range(MAX_REACT_ITERATIONS):
            logger.info(f"ReAct Iteration {iteration + 1}/{MAX_REACT_ITERATIONS}")

            # 1. Get LLM Response (Thought + Action)
            response = await llm.ainvoke(messages)

            # Accumulate usage
            if response.response_metadata:
                generation_info = response.response_metadata
                usage = generation_info.get("token_usage", {})
                total_tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
                total_tokens["completion_tokens"] += usage.get("completion_tokens", 0)
                total_tokens["total_tokens"] += usage.get("total_tokens", 0)
                total_execution_time += generation_info.get("execution_time", 0)

            response_text = response.content
            logger.debug(f"Agent Response: {response_text[:500]}...")

            # Add to history
            messages.append(response)
            execution_history.append({"role": "assistant", "content": response_text})

            # 2. Extract Python Code
            code_match = re.search(r"```python\n(.*?)\n```", response_text, re.DOTALL)

            if not code_match:
                # Check if we're at max iterations
                if iteration == MAX_REACT_ITERATIONS - 1:
                    logger.warning("Max iterations reached without SQL generation")
                    break

                # Prompt to continue
                msg = "Please continue. Write python code to proceed. If you are done, assign result to `final_data` and SQL to `final_sql`."
                messages.append(HumanMessage(content=msg))
                execution_history.append({"role": "user", "content": msg})
                continue

            code = code_match.group(1)

            # 3. Execute Code (Observation)
            try:
                result = code_tool._run(code)

                observation = result
                if not observation:
                    observation = (
                        "(No output from code execution. Did you forget to print?)"
                    )

                logger.info(f"Observation: {observation[:200]}...")

                obs_msg = f"Observation:\n{observation}"
                messages.append(HumanMessage(content=obs_msg))
                execution_history.append({"role": "user", "content": obs_msg})

                # 4. Check for Termination Condition
                executor_state = code_tool.get_state()

                if "final_data" in executor_state:
                    final_data = executor_state["final_data"]

                    if isinstance(final_data, (pd.DataFrame, pd.Series)):
                        logger.info(
                            "Found final_data DataFrame in state. Agent finished."
                        )
                        if isinstance(final_data, pd.Series):
                            logger.info("Converting final_data Series to DataFrame")
                            final_data = final_data.to_frame()

                        # Get SQL too
                        final_sql = executor_state.get("final_sql", "")
                        if not final_sql:
                            logger.warning(
                                "final_sql variable not found, but final_data exists."
                            )
                        return {
                            "dataframe": final_data,
                            "sql_query": final_sql,
                            "tts_iterations": iteration + 1,
                            "tts_execution_history": execution_history,
                        }
                    else:
                        logger.warning(
                            f"final_data found but is not a DataFrame: {type(final_data)}"
                        )
                        warn_msg = f"Warning: `final_data` is not a pandas DataFrame (it is {type(final_data)}). Please ensure `final_data` is a DataFrame."
                        messages.append(HumanMessage(content=warn_msg))
                        execution_history.append({"role": "user", "content": warn_msg})

            except Exception as e:
                error_msg = f"Execution Error: {str(e)}"
                logger.error(error_msg)
                messages.append(HumanMessage(content=error_msg))
                execution_history.append({"role": "user", "content": error_msg})

        # Max iterations reached without final_data
        return {
            "error": "Failed to generate final_data after maximum iterations.",
            "dataframe": None,
            "sql_query": None,
            "tts_iterations": MAX_REACT_ITERATIONS,
            "tts_execution_history": execution_history,
        }

    except Exception as e:
        logger.exception(f"ReAct TTS Agent failed: {e}")
        return {
            "error": str(e),
            "dataframe": None,
            "sql_query": None,
        }
    finally:
        # Ensure we log usage even if there's an exception outside the loop (though less likely to have usage)
        pass


def format_tts_execution_history(history: List[Dict[str, str]]) -> str:
    """
    Format the execution history from ReActTTSAgent into a readable string
    for context injection into analyzer agents.
    """
    history_text = "Previous analysis steps (Data Inspection):\n"

    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "")

        if role == "assistant":
            if "```python" in content:
                history_text += f"Agent Code:\n{content}\n"
        elif role == "user" and "Observation:" in content:
            history_text += f"{content}\n"

    return f"Here is the history of the data inspection done so far. You can use this context to skip initial inspection if needed:\n{history_text}"
