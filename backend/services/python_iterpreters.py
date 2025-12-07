from rich.console import Console
from rich.traceback import Traceback
from rich.theme import Theme
from rich.syntax import Syntax
from rich.panel import Panel
from datetime import datetime

try:
    from e2b_code_interpreter import Sandbox  # type: ignore
except ImportError:

    class Sandbox:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Optional dependency 'e2b-code-interpreter' not installed. "
                "Install it with: pip install e2b-code-interpreter"
            )


from typing import Optional, Dict, Any, Callable

from .local_python_interpreter import (
    evaluate_python_code,
    BASE_PYTHON_TOOLS,
    BASE_BUILTIN_MODULES,
    DEFAULT_MAX_LEN_OUTPUT,
    InterpreterError,
    find_spec,
)

custom_theme = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "bold red",
        "header": "magenta",
        "bold": "bold",
        "dim": "dim",
    }
)
console = Console(theme=custom_theme)


def _format_timestamp():
    return datetime.now().strftime("%H:%M:%S")


def trim_output(output: Any, max_length=500) -> str:
    """Trim the output to a maximum length."""
    if isinstance(output, str):
        return f"{output[:max_length]}..." if len(output) > max_length else output
    elif isinstance(output, (int, float)):
        return output
    elif isinstance(output, list):
        return [
            f"{str(item)[:max_length]}..." if len(str(item)) > max_length else item
            for item in output
        ]
    elif isinstance(output, dict):
        return {
            k: (
                (v[:max_length] + "...")
                if isinstance(v, str) and len(v) > max_length
                else v
            )
            for k, v in output.items()
        }
    else:
        # For other types, convert to string and trim
        output = str(output)
        if len(output) > max_length:
            return f"{output[:max_length]}..."
        else:
            return output


def show_output_and_logs(
    output: Any, logs: str, execution_count: int, show_logs: bool = True
) -> str:
    """Format the output and logs for display."""
    if output is None:
        return f"Out[{execution_count}]: <no output>"
    else:
        prefix = f"Out[{execution_count}]:"
        output = trim_output(output)
        formatted_output = f"{prefix} {output}"
        console.print(formatted_output, style="success")

    if show_logs and logs:
        if len(logs) > 1:
            console.print(f"Log[{execution_count}]: {len(logs)} logs", style="info")
            for i, line in enumerate(logs, start=1):
                prefix = f"[{execution_count}] Log {i}:"
                console.print(prefix, style="bold", end=" ")
                console.print(line, style="success")
        elif logs:
            console.print(f"Log[{execution_count}]:", style="bold", end=" ")
            console.print(logs[0], style="success")


class E2BPythonInterpreter:
    """A simple Python interpreter for executing code in a sandboxed environment."""

    def __init__(
        self,
        sandbox: Optional[Sandbox] = None,
        template: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        **kwargs: Dict,
    ):
        self.sandbox = (
            sandbox
            if sandbox
            else Sandbox(template=template, sandbox_id=sandbox_id, **kwargs)
        )
        self.template = template
        self.sandbox_id = sandbox_id
        self.sandbox_kwargs = kwargs

    def _prepare_sandbox(self) -> None:
        """Prepare the sandbox for running code."""
        if self.sandbox is None:
            console.print(
                "No sandbox instance provided. Creating a new sandbox.", style="warning"
            )
            self.sandbox = Sandbox(
                template=self.template,
                sandbox_id=self.sandbox_id,
                **self.sandbox_kwargs,
            )

        if not self.sandbox.is_running():
            console.print(
                "The sandbox was not running. Restarting the sandbox.", style="warning"
            )
            self.sandbox = Sandbox(
                template=self.template,
                sandbox_id=self.sandbox_id,
                **self.sandbox_kwargs,
            )

    def run_code(self, code, show_code=True, show_logs=True) -> list[str] | None:
        """Execute Python code inside the e2b Sandbox with pretty, IPython-like output.

        Args:
            code (str): Python source code to execute.
            sandbox (Sandbox|None): Optional existing sandbox instance.
            show_code (bool): Echo the code block before execution.
        Returns:
            list[str] | [] | None: Captured stdout lines, empty list if none, or None on error.
        """
        self._prepare_sandbox()

        if show_code:
            header = f"In  [ ]  { _format_timestamp() }"
            console.print(header, style="bold")
            console.print(
                Panel.fit(
                    Syntax(code, "python", theme="monokai", line_numbers=False),
                    title="Code",
                    border_style="header",
                )
            )

        res = self.sandbox.run_code(code)
        exception = res.error

        if exception:
            name = exception.name
            value = exception.value
            traceback = exception.traceback
            console.print(f"Out [ ]:", style="error")
            formatted_exception = f"{name}: {value}\n{traceback}"
            console.print(formatted_exception, style="error", justify="left")
            return None

        output = res.results
        output = [results.text for results in output if results.text is not None]
        stdouts = res.logs.stdout
        stdouts = [line.rstrip() for line in stdouts if line.strip() != ""]
        execution_count = res.execution_count

        show_output_and_logs(
            output=output,
            logs=stdouts,
            execution_count=execution_count,
            show_logs=show_logs,
        )

        return output

    def show_files(self):
        """Display the files in the sandbox."""
        files = self.sandbox.list_files()
        if not files:
            console.print("No files in the sandbox.", style="warning")
            return

        console.print("Files in the sandbox:", style="header")
        for file in files:
            console.print(f"- {file}", style="info")

    def kill(self):
        """Terminate the sandbox."""
        if self.sandbox.is_running():
            self.sandbox.kill()
            console.print("Sandbox terminated.", style="success")
        else:
            console.print("Sandbox was not running.", style="warning")

    def __del__(self):
        self.kill()

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the context manager."""
        self.kill()
        if exc_type is not None:
            console.print(f"An exception occurred: {exc_value}", style="error")
        return False

    def __repr__(self):
        return f"E2BPythonInterpreter(sandbox={self.sandbox})"


class LocalPythonExecutor:
    """
    Executor of Python code in a local environment.

    This executor evaluates Python code with restricted access to imports and built-in functions,
    making it suitable for running untrusted code. It maintains state between executions,
    allows for custom tools and functions to be made available to the code, and captures
    print outputs separately from return values.

    Args:
        additional_authorized_imports (`list[str]`):
            Additional authorized imports for the executor.
        max_print_outputs_length (`int`, defaults to `DEFAULT_MAX_LEN_OUTPUT=50_000`):
            Maximum length of the print outputs.
        additional_functions (`dict[str, Callable]`, *optional*):
            Additional Python functions to be added to the executor.
    """

    def __init__(
        self,
        additional_authorized_imports: list[str] = [],
        max_print_outputs_length: int | None = None,
        additional_functions: dict[str, Callable] | None = BASE_PYTHON_TOOLS,
        addition_variables: dict[str, Any] | None = None,
    ):
        self.custom_tools = additional_functions
        self.state = {"__name__": "__main__"}
        if addition_variables:
            self.state.update(addition_variables)

        self.max_print_outputs_length = max_print_outputs_length
        if max_print_outputs_length is None:
            self.max_print_outputs_length = DEFAULT_MAX_LEN_OUTPUT
        self.additional_authorized_imports = additional_authorized_imports
        self.authorized_imports = list(
            set(BASE_BUILTIN_MODULES) | set(self.additional_authorized_imports)
        )
        self._check_authorized_imports_are_installed()
        self.static_tools = BASE_PYTHON_TOOLS.copy()
        # Local execution counter for display purposes
        self._execution_count = 1

    def _check_authorized_imports_are_installed(self):
        """
        Check that all authorized imports are installed on the system.

        Handles wildcard imports ("*") and partial star-pattern imports (e.g., "os.*").

        Raises:
            InterpreterError: If any of the authorized modules are not installed.
        """
        missing_modules = [
            base_module
            for imp in self.authorized_imports
            if imp != "*" and find_spec(base_module := imp.split(".")[0]) is None
        ]
        if missing_modules:
            raise InterpreterError(
                f"Non-installed authorized modules: {', '.join(missing_modules)}. "
                f"Please install these modules or remove them from the authorized imports list."
            )

    def run_code(
        self,
        code_action: str,
        show_code: bool = True,
        show_logs: bool = False,
    ) -> tuple[str, int, str] | None:
        """Execute code locally with rich-formatted output similar to E2BPythonInterpreter.

        Args:
            code_action: The python code string to execute.
            show_code: Whether to echo the code before execution.
            show_logs: Whether to display captured print outputs.
        Returns:
            - final_answer (str): The output of the code execution, or None if there was an error.
            - logs (str): Captured print outputs during execution.
            - error_message (str): Error message if an error occurred, otherwise None.
        """
        if show_code:
            header = f"In  [ ]  { _format_timestamp() }"
            console.print(header, style="bold")
            console.print(
                Panel.fit(
                    Syntax(code_action, "python", theme="monokai", line_numbers=False),
                    title="Code",
                    border_style="header",
                )
            )

        try:
            output, is_final_answer = evaluate_python_code(
                code_action,
                static_tools=self.static_tools,
                custom_tools=self.custom_tools,
                state=self.state,
                authorized_imports=self.authorized_imports,
                max_print_outputs_length=self.max_print_outputs_length,
            )
            logs = self.state.get("_print_outputs", "").logs
        except InterpreterError as e:
            console.print(f"Out [ ]:", style="error")  # match sandbox spacing
            try:
                console.print(
                    Traceback.from_exception(type(e), e, e.__traceback__),
                    style="error",
                )
            except Exception:
                console.print(str(e), style="error")
            logs = self.state.get("_print_outputs", "").logs
            return None, logs, str(e)

        # Display results (only stdout/logs, mirroring E2B sandbox behavior)
        exec_id = self._execution_count
        self._execution_count += 1
        logs = self.state.get("_print_outputs", "").logs
        show_output_and_logs(
            output=output,
            logs=logs,
            execution_count=exec_id,
            show_logs=show_logs,
        )

        return output, logs, None

    def send_variables(self, variables: dict[str, Any]):
        self.state.update(variables)
