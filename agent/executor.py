import subprocess
import shlex

MAX_OUTPUT = 65536  # 64KB


def execute(command_text: str, timeout: int = 60) -> dict:
    """
    Run command_text in a subprocess shell.
    Returns {'exit_code': int, 'stdout': str, 'stderr': str}.
    Never raises — all errors are captured into stderr.
    """
    try:
        result = subprocess.run(
            command_text,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:MAX_OUTPUT],
            "stderr": result.stderr[:MAX_OUTPUT],
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds.",
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution error: {e}",
        }
