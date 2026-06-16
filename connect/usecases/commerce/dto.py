import uuid
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


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
    status: List[str]
    language: Optional[str] = None


@dataclass(frozen=True)
class SendContractAcceptanceEmailDTO:
    user_email: str
    acceptance_id: uuid.UUID
    subject: str
    body_html: str
    file_name: str
    file_base64: str
