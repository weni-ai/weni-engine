import os

import subprocess

from typing import Optional


class LogStyle:
    """ANSI color codes for terminal output formatting."""

    OK = "\033[92m"
    HEADER = "\033[95m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    WHITE = "\033[0m"


def log(output: str, log_style: str) -> None:
    """Print formatted log message.

    Args:
        output: Message to display
        log_style: ANSI color code for styling
    """
    print(f"{LogStyle.WHITE}└─ {log_style}{output}\n")


def execute(cmd: str, cmd_output: bool = False) -> Optional[str]:
    """Execute shell command and handle output.

    Args:
        cmd: Command to execute
        cmd_output: Whether to return command output

    Returns:
        Command output if cmd_output is True, None otherwise

    Raises:
        SystemExit: If command execution fails
    """
    print(f"{LogStyle.HEADER}Running - {LogStyle.BOLD}{cmd}")

    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        log("Success", LogStyle.OK)

        if cmd_output:
            print(f"{LogStyle.OK}\nCommand output: \n\n{output}")
            return output

    except subprocess.CalledProcessError as e:
        error_output = e.stdout.replace("\n", "\n ").strip()
        print(f"{LogStyle.FAIL}{error_output}")
        log("Fail", LogStyle.FAIL)
        exit(1)


def main() -> None:
    """Main execution function."""
    if not os.getcwd().endswith("weni-engine"):
        raise RuntimeError("This command must be executed in weni-engine")

    log("Make any missing migrations", LogStyle.BOLD)

    execute("python manage.py makemigrations")
    execute("flake8 connect/")
    execute("coverage run manage.py test --verbosity=2 --noinput")
    execute("coverage report -m", cmd_output=True)


if __name__ == "__main__":
    main()
