from dataclasses import dataclass
from typing import List, Dict


@dataclass
class KeycloakUserDTO:
    email: str = ""
    username: str = ""
    enabled: bool = True
    first_name: str = ""
    last_name: str = ""
    credentials: List[Dict] = None
    company_name: str = ""

    def __post_init__(self):
        self.username = self.email
