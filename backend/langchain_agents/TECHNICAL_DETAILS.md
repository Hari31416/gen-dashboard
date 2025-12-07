# Technical Implementation Details

This document provides in-depth technical details of the LangChain/LangGraph unified agent system implementation.

## Table of Contents

1. [State Management](#state-management)
2. [LLM Integration](#llm-integration)
3. [Memory System](#memory-system)
4. [Agent Implementation](#agent-implementation)
5. [Graph Architecture](#graph-architecture)
6. [Tools System](#tools-system)
7. [Execution History Tracking](#execution-history-tracking)
8. [Error Handling](#error-handling)
9. [Streaming Implementation](#streaming-implementation)

---

## State Management

### Overview

LangGraph uses `TypedDict` classes to define state schemas. State flows through nodes, with each node returning a partial update that gets merged into the main state.

### State Definitions

#### TTSGraphState

```python
class TTSGraphState(TypedDict):
    # Input fields
    user_query: str                              # The user's natural language question
    username: str                                # Username for DB access control

    # DB Selection outputs
    selected_connection: Optional[str]           # Name of selected database connection
    db_selection_reasoning: Optional[str]        # Why this DB was selected

    # ReAct TTS outputs
    dataframe: Optional[Any]                     # Retrieved pandas DataFrame
    sql_query: Optional[str]                     # Final executed SQL query
    tts_iterations: Optional[int]                # Number of ReAct iterations used
    tts_execution_history: Optional[List[Dict[str, str]]]  # Full execution trace

    # Error handling
    error: Optional[str]                         # Error message if any
```

#### AnalyzerGraphState

```python
class AnalyzerGraphState(TypedDict):
    # Input from TTS
    user_query: str
    username: str
    dataframe: Optional[Any]                     # DataFrame from TTS
    sql_query: Optional[str]                     # SQL that produced the DataFrame
    tts_execution_history: Optional[List[Dict[str, str]]]

    # Stage 0 - Data Inspector outputs
    df_summary: Optional[str]                    # DataFrame structure summary
    inspection_code: Optional[str]               # Code executed for inspection
    inspection_output: Optional[str]             # Output from inspection

    # Stage 1 - Analyzer outputs
    analysis_data: Optional[Any]                 # The 'data' variable (DataFrame)
    analysis_code: Optional[str]                 # Aggregation code executed
    analysis_comments: Optional[str]             # LLM reasoning/comments

    # Stage 2 - Visualization outputs
    visualization_image: Optional[str]           # Base64-encoded image
    visualization_code: Optional[str]            # Plotly/matplotlib code

    # Stage 3 - Insights
    insights: Optional[str]                      # Natural language insights

    # Execution tracking
    analyzer_execution_history: Optional[List[Dict[str, Any]]]
    conversation_history: Optional[List[Dict[str, str]]]
    current_stage: Optional[int]                 # 0, 1, 2, 3

    error: Optional[str]
```

#### MainGraphState

```python
class MainGraphState(TypedDict):
    # Input
    user_query: str
    username: str
    session_id: str                              # For memory management

    # Memory - uses append reducer for accumulation
    conversation_history: Annotated[List[Dict[str, str]], append_messages]

    # Router outputs
    route_decision: Optional[Literal["followup", "new_question"]]
    route_reasoning: Optional[str]

    # Follow-up path
    followup_response: Optional[str]

    # TTS outputs (passed through)
    selected_connection: Optional[str]
    dataframe: Optional[Any]
    sql_query: Optional[str]
    tts_execution_history: Optional[List[Dict[str, str]]]

    # Analyzer outputs (passed through)
    analysis_data: Optional[Any]
    visualization_image: Optional[str]
    insights: Optional[str]
    analyzer_execution_history: Optional[List[Dict[str, Any]]]

    # Final response
    final_response: Optional[str]
    final_image: Optional[str]
    final_data: Optional[Any]                    # JSON-serializable

    error: Optional[str]

    # Metadata - uses merge reducer
    metadata: Annotated[Dict[str, Any], merge_dicts]
```

### State Reducers

LangGraph supports custom reducers for state fields using `Annotated`:

```python
def append_messages(left: List, right: List) -> List:
    """Append new messages to existing list."""
    return (left or []) + (right or [])

def merge_dicts(left: Dict, right: Dict) -> Dict:
    """Merge dictionaries with right taking precedence."""
    return {**(left or {}), **(right or {})}

# Usage in state
conversation_history: Annotated[List[Dict[str, str]], append_messages]
metadata: Annotated[Dict[str, Any], merge_dicts]
```

**Why reducers matter**: Without reducers, returning `{"conversation_history": new_messages}` would overwrite the existing list. With `append_messages` reducer, the new messages are appended.

---

## LLM Integration

### The LiteLLM Wrapper

Since the existing codebase uses LiteLLM (not native LangChain models), we created a wrapper:

```python
# langchain_agents/llm_utils.py

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from services.llm import atext_completion, text_completion

class LiteLLMWrapper(BaseChatModel):
    """Wraps LiteLLM for LangChain compatibility."""

    model_name: str = "default"
    temperature: float = 0.7

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """Synchronous generation."""
        prompt = self._format_messages(messages)
        response = text_completion(prompt, temperature=self.temperature)

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=response))]
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResult:
        """Asynchronous generation."""
        prompt = self._format_messages(messages)
        response = await atext_completion(prompt, temperature=self.temperature)

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=response))]
        )

    def _format_messages(self, messages: List[BaseMessage]) -> str:
        """Convert LangChain messages to prompt string."""
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                formatted.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"Assistant: {msg.content}")
        return "\n\n".join(formatted)

    @property
    def _llm_type(self) -> str:
        return "litellm-wrapper"
```

### Usage

```python
from langchain_agents.llm_utils import get_llm

llm = get_llm(temperature=0.3)

# Async usage (preferred)
response = await llm.ainvoke(messages)
content = response.content

# Sync usage
response = llm.invoke(messages)
```

---

## Memory System

### Architecture

Memory is managed through MongoDB for persistence, with an in-memory fallback if MongoDB is unavailable. Conversation history is stored per session and username combination. The system uses the existing `get_mongo_connection` utility to ensure consistency with the rest of the application.

```python
# langchain_agents/agents/memory_agent.py

from services.database.mongo_database import get_mongo_connection
from env import DEFAULT_USERNAME

# Collection name for conversation history
CONVERSATION_HISTORY_COLLECTION = "conversation_history"

class MemoryAgent:
    """Manages conversation history persistence."""

    def __init__(self, use_mongodb: bool = True):
        self._use_mongodb = use_mongodb
        self._memory_store: Dict[str, List[Dict[str, str]]] = {}  # Fallback

        if use_mongodb:
            try:
                # Use existing get_mongo_connection utility
                self._mongo_client, self._db, _ = get_mongo_connection(
                    user_name=DEFAULT_USERNAME
                )
                self._collection = self._db[CONVERSATION_HISTORY_COLLECTION]

                # Create index for faster lookups
                self._collection.create_index(
                    [("session_id", 1), ("username", 1)], unique=True
                )
            except Exception as e:
                logger.error(f"MongoDB connection failed: {e}")
                self._use_mongodb = False  # Fallback to in-memory

    def get_conversation_history(
        self,
        session_id: str,
        username: str = "",
        max_turns: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Load conversation history for a session."""
        if self._use_mongodb and self._collection is not None:
            doc = self._collection.find_one({
                "session_id": session_id,
                "username": username or ""
            })
            history = doc.get("messages", []) if doc else []
        else:
            # Fallback to in-memory
            key = f"{username}:{session_id}" if username else session_id
            history = self._memory_store.get(key, [])

        # Limit turns if specified
        if max_turns and len(history) > max_turns * 2:
            history = history[-(max_turns * 2):]

        return history

    def add_to_history(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        username: str = "",
    ) -> None:
        """Add a conversation turn to history."""
        new_messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_response},
        ]

        if self._use_mongodb and self._collection is not None:
            self._collection.update_one(
                {"session_id": session_id, "username": username or ""},
                {
                    "$push": {"messages": {"$each": new_messages}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
                upsert=True
            )
        else:
            # Fallback to in-memory
            key = f"{username}:{session_id}" if username else session_id
            if key not in self._memory_store:
                self._memory_store[key] = []
            self._memory_store[key].extend(new_messages)
```

### MongoDB Document Schema

```json
{
    "_id": ObjectId("..."),
    "session_id": "session-abc-123",
    "username": "user@example.com",
    "messages": [
        {"role": "user", "content": "Show me sales by region"},
        {"role": "assistant", "content": "Here's the sales breakdown..."},
        {"role": "user", "content": "What about last month?"},
        {"role": "assistant", "content": "Last month's data shows..."}
    ],
    "created_at": ISODate("2025-11-25T10:00:00Z"),
    "updated_at": ISODate("2025-11-25T10:30:00Z")
}
```

### Graph Integration

Memory is loaded at the start and saved at the end of graph execution:

```python
def load_memory_node(state: MainGraphState) -> Dict[str, Any]:
    """Node that loads conversation history."""
    session_id = state.get("session_id", "default")
    username = state.get("username", "")

    # Load from MongoDB (or in-memory fallback)
    history = memory_agent.get_conversation_history(
        session_id, username=username, max_turns=10
    )

    return {
        "conversation_history": history,  # Uses append reducer
    }

def save_memory_node(state: MainGraphState) -> Dict[str, Any]:
    """Node that saves conversation history."""
    session_id = state.get("session_id", "default")
    username = state.get("username", "")
    user_query = state.get("user_query", "")

    # Determine the final response
    final_response = (
        state.get("final_response") or state.get("followup_response") or ""
    )

    # Add current interaction to MongoDB (or in-memory fallback)
    if user_query and final_response:
        memory_agent.add_to_history(
            session_id, user_query, final_response, username=username
        )

    return {}  # No state updates needed
```

### Fallback Behavior

The memory system has automatic fallback:

1. **Primary**: MongoDB persistence (if `MONGO_URI` is configured)
2. **Fallback**: In-memory dictionary (if MongoDB unavailable)

```python
# Check which storage is being used
if memory_agent.is_using_mongodb():
    print("Using MongoDB for persistence")
else:
    print("Using in-memory storage (data lost on restart)")
```

### Conversation History Format

```python
conversation_history = [
    {"role": "user", "content": "Show me sales by region"},
    {"role": "assistant", "content": "Here's the sales breakdown..."},
    {"role": "user", "content": "What about last month?"},
    {"role": "assistant", "content": "Last month's data shows..."},
]
```

---

## Agent Implementation

### Agent Node Pattern

Each agent follows this pattern:

```python
async def agent_node(state: StateType) -> Dict[str, Any]:
    """
    Agent node function.

    Args:
        state: Current graph state

    Returns:
        Partial state update dictionary
    """
    # 1. Extract needed data from state
    user_query = state.get("user_query", "")

    # 2. Build prompt/messages
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # 3. Call LLM
    llm = get_llm(temperature=0.3)
    response = await llm.ainvoke(messages)

    # 4. Process response (extract code, parse JSON, etc.)
    result = process_response(response.content)

    # 5. Return state updates
    return {
        "output_field": result,
        "execution_history": updated_history,
    }
```

### Router Agent

The router decides if a query is a follow-up or new question:

```python
async def router_agent_node(state: MainGraphState) -> Dict[str, Any]:
    user_query = state.get("user_query", "")
    history = state.get("conversation_history", [])

    # Build context from history
    history_context = "\n".join([
        f"{msg['role']}: {msg['content'][:200]}"
        for msg in history[-6:]  # Last 3 exchanges
    ])

    prompt = f"""Analyze if this is a follow-up question or a new question.

Conversation History:
{history_context}

Current Question: {user_query}

Respond with JSON: {{"decision": "followup" or "new_question", "reasoning": "..."}}
"""

    llm = get_llm(temperature=0.1)
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    # Parse response
    result = parse_json(response.content)

    return {
        "route_decision": result.get("decision", "new_question"),
        "route_reasoning": result.get("reasoning", ""),
    }

def route_decision(state: MainGraphState) -> Literal["followup", "new_question"]:
    """Conditional edge function."""
    return state.get("route_decision", "new_question")
```

### ReAct TTS Agent

Implements the ReAct (Reasoning + Acting) pattern:

```python
MAX_ITERATIONS = 10

async def react_tts_agent_node(state: TTSGraphState) -> Dict[str, Any]:
    user_query = state.get("user_query", "")
    connection = state.get("selected_connection")
    username = state.get("username")

    # Create database tools
    db_tools = DatabaseTools(username, connection)
    tools_dict = db_tools.get_tools_as_functions()

    # Create code executor with tools
    code_tool = create_tts_code_tool(tools_dict)

    execution_history = []
    messages = [
        SystemMessage(content=REACT_TTS_SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {user_query}"),
    ]

    llm = get_llm(temperature=0.3)

    for iteration in range(MAX_ITERATIONS):
        # Get LLM response
        response = await llm.ainvoke(messages)
        response_text = response.content

        # Check for final answer
        if "<FINAL_ANSWER>" in response_text:
            sql_query = extract_final_sql(response_text)
            break

        # Extract and execute code
        code_blocks = extract_code_blocks(response_text)

        for code in code_blocks:
            result = code_tool._run(code)
            execution_history.append({
                "iteration": iteration + 1,
                "thought": extract_thought(response_text),
                "code": code,
                "output": result,
            })

        # Add observation to messages
        messages.append(AIMessage(content=response_text))
        messages.append(HumanMessage(content=f"Observation:\n{result}"))

    # Execute final query
    df = run_query_and_return_df(connection_string, sql_query)

    return {
        "dataframe": df,
        "sql_query": sql_query,
        "tts_iterations": iteration + 1,
        "tts_execution_history": execution_history,
    }
```

### Analyzer Agent (Stage 1)

```python
async def analyzer_agent_node(state: AnalyzerGraphState) -> Dict[str, Any]:
    dataframe = state.get("dataframe")
    df_summary = state.get("df_summary", "")

    # Create code tool with df loaded
    code_tool = create_analyzer_code_tool(df=dataframe)

    messages = [
        SystemMessage(content=STAGE_1_PROMPT),
        HumanMessage(content=f"""
Question: {user_query}

DataFrame Summary: {df_summary}

Please analyze the data and store the result in the `data` variable.
"""),
    ]

    for step in range(MAX_STEPS):
        response = await llm.ainvoke(messages)

        # Execute code blocks
        code_blocks = extract_code_blocks(response.content)
        for code in code_blocks:
            result = code_tool._run(code)

        # Check if 'data' variable exists
        executor_state = code_tool.get_state()
        if "data" in executor_state:
            data = executor_state["data"]

            # Record in history
            history_entry = {
                "stage": 1,
                "stage_name": "Analyzer",
                "code": analysis_code,
                "output_shape": str(data.shape),
            }

            return {
                "analysis_data": data,
                "analysis_code": analysis_code,
                "analyzer_execution_history": existing_history + [history_entry],
                "current_stage": 2,
            }

        # Continue with observation
        messages.append(AIMessage(content=response.content))
        messages.append(HumanMessage(content=f"Observation:\n{result}"))
```

---

## Graph Architecture

### Graph Building Pattern

```python
from langgraph.graph import StateGraph, START, END

def create_graph() -> StateGraph:
    builder = StateGraph(StateType)

    # Add nodes
    builder.add_node("node_name", node_function)

    # Add edges
    builder.add_edge(START, "first_node")
    builder.add_edge("node_a", "node_b")

    # Conditional edges
    builder.add_conditional_edges(
        "router_node",
        routing_function,
        {
            "option_a": "node_a",
            "option_b": "node_b",
        }
    )

    builder.add_edge("final_node", END)

    return builder.compile()
```

### Subgraph Integration

Subgraphs are invoked within parent graph nodes:

```python
async def tts_subgraph_node(state: MainGraphState) -> Dict[str, Any]:
    """Runs the TTS subgraph."""

    # Create subgraph
    tts_graph = create_tts_graph()

    # Create subgraph state from main state
    tts_state: TTSGraphState = {
        "user_query": state.get("user_query"),
        "username": state.get("username"),
        # ... initialize other fields
    }

    # Run subgraph
    result = await tts_graph.ainvoke(tts_state)

    # Return results to merge into main state
    return {
        "dataframe": result.get("dataframe"),
        "sql_query": result.get("sql_query"),
        "tts_execution_history": result.get("tts_execution_history"),
    }
```

### Node Naming Convention

**Important**: LangGraph requires node names to not conflict with state keys.

```python
# ❌ Bad - "insights" conflicts with state key
builder.add_node("insights", insights_agent_node)

# ✅ Good - use suffix to avoid conflict
builder.add_node("insights_node", insights_agent_node)
builder.add_node("error_handler", error_handler_node)
```

---

## Tools System

### Code Execution Tool

Wraps the `LocalPythonExecutor` for safe code execution:

```python
# langchain_agents/tools/code_execution.py

from services.local_python_interpreter import LocalPythonExecutor

class CodeExecutionTool(BaseTool):
    name: str = "execute_python"
    description: str = "Execute Python code safely"

    executor: LocalPythonExecutor = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.executor = LocalPythonExecutor(
            additional_authorized_imports=[
                "pandas", "numpy", "datetime", "json", "re"
            ],
            additional_functions={},
        )

    def _run(self, code: str) -> str:
        """Execute code and return output."""
        try:
            result, output = self.executor(code)
            return output if output else str(result)
        except Exception as e:
            return f"Error: {str(e)}"

    def get_state(self) -> Dict[str, Any]:
        """Get current executor state (variables)."""
        return self.executor.state

    def send_variables(self, variables: Dict[str, Any]) -> None:
        """Inject variables into executor state."""
        self.executor.send_variables(variables)
```

### Database Tools

```python
# langchain_agents/tools/database_tools.py

class DatabaseTools:
    def __init__(self, username: str, connection_name: str):
        self.db_config = get_db_config(username, connection_name)
        self.connection_string = build_connection_string(**self.db_config)

    def get_db_schema(self) -> Dict[str, Any]:
        """Get high-level schema information."""
        return fetch_table_schemas(**self.db_config)

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed table information."""
        # ...

    def get_table_sample(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """Get sample rows from a table."""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return run_query_and_return_df(self.connection_string, query)

    def run_sql_query(self, sql: str, dry_run: bool = True) -> Union[Dict, pd.DataFrame]:
        """Run or validate SQL query."""
        if dry_run:
            return dry_run_sql_query(self.connection_string, sql)
        return run_query_and_return_df(self.connection_string, sql)

    def get_tools_as_functions(self) -> Dict[str, Callable]:
        """Get tools as callable functions for code executor."""
        return {
            "get_db_schema": self.get_db_schema,
            "get_table_info": self.get_table_info,
            "get_table_sample": self.get_table_sample,
            "run_sql_query": self.run_sql_query,
        }
```

---

## Execution History Tracking

### TTS Execution History

Tracks each iteration of the ReAct loop:

```python
tts_execution_history = [
    {
        "iteration": 1,
        "thought": "I need to understand the database schema first",
        "code": "schema = get_db_schema()\nprint(schema)",
        "output": "{'tables': [{'name': 'sales', ...}]}"
    },
    {
        "iteration": 2,
        "thought": "Now I'll check the columns in the sales table",
        "code": "info = get_table_info('sales')\nprint(info)",
        "output": "{'columns': ['id', 'region', 'amount', ...]}"
    },
    {
        "iteration": 3,
        "thought": "I can now write the final query",
        "code": "result = run_sql_query('SELECT region, SUM(amount)...')",
        "output": "<FINAL_ANSWER>SELECT region, SUM(amount)...</FINAL_ANSWER>"
    }
]
```

### Analyzer Execution History

Tracks each stage of the analyzer:

```python
analyzer_execution_history = [
    {
        "stage": 0,
        "stage_name": "Data Inspector",
        "code": "print(df.shape)\nprint(df.dtypes)",
        "output": "(1000, 5)\nid: int64\nregion: object...",
        "summary": "DataFrame Shape: (1000, 5)..."
    },
    {
        "stage": 1,
        "stage_name": "Analyzer",
        "code": "data = df.groupby('region')['amount'].sum().reset_index()",
        "comments": "Aggregating sales by region",
        "output_shape": "(5, 2)",
        "output_columns": ["region", "amount"]
    },
    {
        "stage": 2,
        "stage_name": "Visualization",
        "code": "fig = px.bar(data, x='region', y='amount')...",
        "output": "Generated image with length: 45678",
        "image_generated": True
    },
    {
        "stage": 3,
        "stage_name": "Insights",
        "output": "The Western region leads with 35% of total sales...",
        "insights_length": 256
    }
]
```

---

## Error Handling

### Error Handler Nodes

Each graph has dedicated error handler nodes:

```python
def error_handler_node(state: StateType) -> Dict[str, Any]:
    """Handle errors gracefully."""
    error = state.get("error", "Unknown error")
    logger.error(f"Graph error: {error}")

    return {
        "final_response": f"An error occurred: {error}",
        "error": error,
    }
```

### Conditional Routing on Errors

```python
def route_after_tts(state: MainGraphState) -> Literal["analyze", "error"]:
    """Route based on TTS success."""
    if state.get("dataframe") is not None:
        return "analyze"
    if state.get("error"):
        return "error"
    return "error"

builder.add_conditional_edges(
    "tts_subgraph",
    route_after_tts,
    {
        "analyze": "analyzer_subgraph",
        "error": "error_handler",
    }
)
```

### Graceful Degradation

The analyzer continues to insights even if visualization fails:

```python
def route_after_visualization(state) -> Literal["continue", "handle_error"]:
    # Continue to insights even on visualization failure
    return "continue"

builder.add_conditional_edges(
    "visualization_node",
    route_after_visualization,
    {
        "continue": "insights_node",
        "handle_error": "insights_node",  # Still try insights
    }
)
```

---

## Streaming Implementation

### Stream Mode

LangGraph supports streaming with `stream_mode="updates"`:

```python
async def run_query_streaming(
    user_query: str,
    username: str,
    session_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream query results."""

    graph = create_main_graph()
    initial_state = create_initial_main_state(user_query, username, session_id)

    async for chunk in graph.astream(
        initial_state,
        stream_mode="updates",
        subgraphs=True  # Include subgraph updates
    ):
        # Handle tuple format (with namespace) or dict format
        if isinstance(chunk, tuple):
            namespace, updates = chunk
            yield {
                "namespace": namespace,
                "updates": updates,
            }
        else:
            yield {
                "namespace": (),
                "updates": chunk,
            }
```

### Streaming Output Format

```python
# Each yielded chunk looks like:
{
    "namespace": ("tts_subgraph",),  # Subgraph path
    "updates": {
        "db_selector": {           # Node name
            "selected_connection": "sales_db",
            "db_selection_reasoning": "..."
        }
    }
}
```

### Client-Side Handling

```python
async for update in run_query_streaming(query, user, session):
    namespace = "/".join(update["namespace"]) or "main"

    for node_name, node_output in update["updates"].items():
        print(f"[{namespace}:{node_name}]")

        # Handle specific outputs
        if "dataframe" in node_output:
            print(f"  Got DataFrame: {node_output['dataframe'].shape}")
        if "visualization_image" in node_output:
            print(f"  Got image: {len(node_output['visualization_image'])} bytes")
        if "insights" in node_output:
            print(f"  Insights: {node_output['insights'][:100]}...")
```

---

## Configuration

### Environment Variables

```python
# env.py
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
USE_SAFE_EXECUTOR = os.getenv("USE_SAFE_EXECUTOR", "true").lower() == "true"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "gen_bi")
```

### Agent Configuration

```python
class AgentConfig(TypedDict, total=False):
    max_iterations: int      # Max ReAct iterations (default: 10)
    temperature: float       # LLM temperature (default: 0.3)
    skip_stages: List[int]   # Stages to skip (e.g., [2] to skip viz)
    skip_visualization: bool # Skip visualization stage
    skip_insights: bool      # Skip insights generation
```

---

## File Reference

| File                             | Purpose                                  |
| -------------------------------- | ---------------------------------------- |
| `state.py`                       | State TypedDict definitions and creators |
| `llm_utils.py`                   | LiteLLM wrapper for LangChain            |
| `agents/memory_agent.py`         | MongoDB-based memory management          |
| `agents/router_agent.py`         | Follow-up vs new question routing        |
| `agents/followup_agent.py`       | Follow-up question handling              |
| `agents/db_selector_agent.py`    | Database connection selection            |
| `agents/react_tts_agent.py`      | ReAct Text-to-SQL agent                  |
| `agents/data_inspector_agent.py` | Stage 0 - DataFrame inspection           |
| `agents/analyzer_agent.py`       | Stage 1 - Data aggregation               |
| `agents/visualization_agent.py`  | Stage 2 - Chart generation               |
| `agents/insights_agent.py`       | Stage 3 - Insights generation            |
| `graphs/tts_graph.py`            | TTS subgraph definition                  |
| `graphs/analyzer_graph.py`       | Analyzer subgraph definition             |
| `graphs/main_graph.py`           | Main orchestration graph                 |
| `tools/code_execution.py`        | Safe Python execution tool               |
| `tools/database_tools.py`        | Database query tools                     |
