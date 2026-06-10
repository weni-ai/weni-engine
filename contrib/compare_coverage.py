import subprocess

from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass
class CoverageData:
    """Data class to store coverage information."""

    local_misses: int
    main_misses: int


class GitService:
    """Service for git operations."""

    @staticmethod
    def get_main_commit() -> str:
        """Get the last commit hash from main branch."""
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "origin/main"])
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error executing git command: {e}")


class CoverageService:
    """Service for coverage operations."""

    BASE_URL = "https://api.codecov.io/api/v2/gh/weni-ai/repos/weni-engine/commits/"

    @staticmethod
    def get_local_misses() -> int:
        """Get number of missed lines from local coverage report."""
        output = (
            subprocess.check_output(
                "coverage report -m | awk '/^TOTAL/ {print $3}'", shell=True
            )
            .decode("utf-8")
            .replace("\n", "\n ")
            .strip()
        )
        return int(output)

    @classmethod
    def get_main_coverage(cls, commit_hash: str) -> Dict[str, Any]:
        """Get coverage data from Codecov API for main branch."""
        response = requests.get(f"{cls.BASE_URL}{commit_hash}")

        if response.status_code != 200:
            raise Exception("Failed to fetch coverage data from Codecov API")

        try:
            return response.json()
        except ValueError as e:
            raise Exception(f"Error parsing JSON response from Codecov API: {e}")


class CoverageComparator:
    """Class to compare local and main branch coverage."""

    @staticmethod
    def compare_coverage(coverage_data: CoverageData) -> None:
        """Compare local and main coverage and fail when it regresses."""
        print(f"[Local]: lines without tests: {coverage_data.local_misses}")
        print(f"[Main]: lines without tests: {coverage_data.main_misses}")

        if coverage_data.local_misses > coverage_data.main_misses:
            print(
                f"Number of test lines decreased by {coverage_data.local_misses - coverage_data.main_misses}"
            )
            exit(1)

        print(
            f"Number of test lines increased by {coverage_data.main_misses - coverage_data.local_misses}"
        )
        exit(0)


def main() -> None:
    """Main execution function."""
    try:
        main_commit = GitService.get_main_commit()
        coverage_service = CoverageService()
        local_misses = coverage_service.get_local_misses()

        main_coverage = coverage_service.get_main_coverage(main_commit)

        if "totals" not in main_coverage:
            raise Exception("Invalid JSON response from Codecov API")

        main_misses = main_coverage["totals"].get("misses")

        if main_misses is None:
            raise Exception("Missing 'misses' value in JSON response from Codecov API")

        coverage_data = CoverageData(local_misses=local_misses, main_misses=main_misses)
        CoverageComparator.compare_coverage(coverage_data)

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
