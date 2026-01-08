"""
Code execution tool for LangGraph agents.

This module wraps the existing LocalPythonExecutor to provide
code execution capabilities as a LangChain tool.
"""

from typing import Any, Dict, List, Optional, Type

import pandas as pd
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from services.local_python_interpreter import BASE_PYTHON_TOOLS, LocalPythonExecutor
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


class CodeExecutionInput(BaseModel):
    """Input schema for code execution tool."""

    code: str = Field(description="Python code to execute")


class CodeExecutionTool(BaseTool):
    """
    A tool for executing Python code in a sandboxed environment.

    This wraps the existing LocalPythonExecutor to provide:
    - Safe code execution with restricted imports
    - State persistence across executions
    - Captured output from print statements
    """

    name: str = "execute_python_code"
    description: str = """Execute Python code in a sandboxed environment. 
    The code has access to pandas (as pd), numpy, json, and other common libraries.
    Use print() to output results. The output will be returned.
    Variables persist across executions.
    """
    args_schema: Type[BaseModel] = CodeExecutionInput

    # Configuration
    executor: Optional[Any] = None  # LocalPythonExecutor instance
    additional_imports: List[str] = Field(
        default_factory=lambda: [
            "pandas",
            "numpy",
            "json",
            "io",
            "re",
            "datetime",
        ]
    )

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.executor is None:
            self._initialize_executor()

    def _initialize_executor(self):
        """Initialize the code executor with default settings."""
        additional_functions = BASE_PYTHON_TOOLS.copy()
        additional_functions.update(
            {
                "globals": globals,
                "locals": locals,
                "pd": pd,
            }
        )

        self.executor = LocalPythonExecutor(
            additional_authorized_imports=self.additional_imports,
            additional_functions=additional_functions,
            static_tools=additional_functions,
        )
        logger.debug("Initialized CodeExecutionTool executor")

    def send_variables(self, variables: Dict[str, Any]) -> None:
        """
        Send variables to the executor state.

        Args:
            variables: Dict of variable names to values to add to executor state.
        """
        if self.executor is None:
            self._initialize_executor()
        self.executor.send_variables(variables)

    def get_state(self) -> Dict[str, Any]:
        """Get the current executor state."""
        if self.executor is None:
            return {}
        return self.executor.state

    def clear_state(self) -> None:
        """Clear the executor state and reinitialize."""
        self._initialize_executor()

    def _run(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute Python code and return the output."""
        if self.executor is None:
            self._initialize_executor()

        try:
            logger.debug(f"Executing code:\n{code[:500]}...")
            result = self.executor(code)

            output = result.logs
            if not output:
                output = "(Code executed successfully with no output.)"

            logger.debug(f"Execution output: {output[:500]}...")
            return output

        except Exception as e:
            error_msg = f"Execution Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def _arun(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Async execution - delegates to sync for now."""
        return self._run(code, run_manager)


def create_code_execution_tool(
    additional_imports: Optional[List[str]] = None,
    initial_variables: Optional[Dict[str, Any]] = None,
) -> CodeExecutionTool:
    """
    Factory function to create a CodeExecutionTool.

    Args:
        additional_imports: Additional modules to authorize for import.
        initial_variables: Variables to pre-load into the executor state.

    Returns:
        A configured CodeExecutionTool instance.
    """
    default_imports = [
        "pandas",
        "numpy",
        "json",
        "io",
        "re",
        "datetime",
        "plotly",
        "plotly.graph_objects",
        "plotly.express",
        "scipy",
        "scipy.stats",
        "base64",
    ]

    if additional_imports:
        default_imports = list(set(default_imports + additional_imports))

    tool = CodeExecutionTool(additional_imports=default_imports)

    if initial_variables:
        tool.send_variables(initial_variables)

    return tool


class AnalyzerCodeExecutionTool(CodeExecutionTool):
    """
    Specialized code execution tool for the Analyzer agents.

    This adds visualization-specific imports and helpers.
    """

    name: str = "execute_analysis_code"
    description: str = """Execute Python code for data analysis and visualization.
    Has access to pandas (pd), numpy, plotly, json, base64, and other analysis libraries.
    
    Key variables available:
    - df: The dataframe from the database query
    - data: The processed/aggregated data (set this in Stage 1)
    - image: Base64 encoded visualization (set this in Stage 2)
    
    Use print() to output results.
    """

    def __init__(self, **kwargs):
        # Override additional imports for analysis
        kwargs.setdefault(
            "additional_imports",
            [
                "pandas",
                "numpy",
                "plotly",
                "plotly.graph_objects",
                "plotly.express",
                "json",
                "base64",
                "io",
                "re",
                "scipy",
                "scipy.stats",
                "datetime",
            ],
        )
        super().__init__(**kwargs)


def create_analyzer_code_tool(
    df: Optional[pd.DataFrame] = None,
) -> AnalyzerCodeExecutionTool:
    """
    Create a code execution tool pre-configured for data analysis.

    Args:
        df: Optional DataFrame to pre-load as 'df' variable.

    Returns:
        Configured AnalyzerCodeExecutionTool.
    """
    tool = AnalyzerCodeExecutionTool()

    # Pre-load common variables
    initial_vars = {"pd": pd}

    if df is not None:
        initial_vars["df"] = df
        initial_vars["final_df"] = df  # Alias for ReAct TTS agent compatibility

    tool.send_variables(initial_vars)

    return tool
