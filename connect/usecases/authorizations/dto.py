from dataclasses import dataclass


@dataclass
class CreateAuthorizationDTO:
    user_email: str
    org_uuid: str
    role: int


@dataclass
class CreateProjectAuthorizationDTO:
    user_email: str
    project_uuid: str
    created_by_email: str
    role: int


@dataclass
class UpdateAuthorizationDTO:
    org_uuid: str
    role: int
    request_user: str = None
    id: int = None
    user_email: str = None


@dataclass
class DeleteAuthorizationDTO:
    org_uuid: str
    request_user: str = None
    id: int = None
    user_email: str = None


@dataclass
class DeleteProjectAuthorizationDTO:
    user_email: str
    project_uuid: str
