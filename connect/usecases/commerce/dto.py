from dataclasses import dataclass


@dataclass(frozen=True)
class CreateVtexProjectDTO:
    user_email: str
    vtex_account: str
    language: str
    organization_name: str
    project_name: str
