import subprocess
import sys

from dataclasses import dataclass
from typing import Any, Dict, Optional

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
            raise RuntimeError(f"Error executing git command: {e}")


class CoverageService:
    """Service for coverage operations."""

    BASE_URL = "https://api.codecov.io/api/v2/gh/weni-ai/repos/weni-engine/commits/"

    @staticmethod
    def get_local_misses() -> int:
        """Get number of missed lines from local coverage report."""
        output = subprocess.check_output(
            [sys.executable, "-m", "coverage", "report", "-m"],
            text=True,
        )
        for line in output.splitlines():
            if line.startswith("TOTAL"):
                return int(line.split()[2])
        raise RuntimeError("TOTAL line not found in coverage report")

    @classmethod
    def get_main_coverage(cls, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Get coverage data from Codecov API for the main branch.

        Returns None when the data is unavailable (e.g. the main commit has not
        been uploaded to Codecov yet). Callers must treat None as 'no baseline'
        and skip the comparison instead of failing the build.
        """
        response = requests.get(f"{cls.BASE_URL}{commit_hash}")

        if response.status_code != 200:
            print(
                f"Codecov returned HTTP {response.status_code} for main commit "
                f"{commit_hash}: no coverage report available yet."
            )
            return None

        try:
            return response.json()
        except ValueError:
            print(
                f"Could not parse the Codecov response for main commit {commit_hash}."
            )
            return None


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

        main_misses = (main_coverage or {}).get("totals", {}).get("misses")

        if main_misses is None:
            print(
                f"[Main]: no baseline coverage data found for commit {main_commit}. "
                "This is expected until main is uploaded to Codecov at least once. "
                "Skipping comparison (not a failure)."
            )
            exit(0)

        coverage_data = CoverageData(
            local_misses=local_misses, main_misses=int(main_misses)
        )
        CoverageComparator.compare_coverage(coverage_data)

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
