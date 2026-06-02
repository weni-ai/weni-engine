from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class CreateVtexProjectDTO:
    user_email: str
    vtex_account: str
    language: str
    organization_name: str
    project_name: str


@dataclass(frozen=True)
class SendDataExportEmailDTO:
    user_email: str
    file_url: str
    start_date: date
    end_date: date
    template: str
    status: str
    language: Optional[str] = None
