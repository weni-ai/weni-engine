from dataclasses import dataclass


@dataclass
class KeycloakUserDTO:
    email: str = ""
    username: str = ""
    enabled: bool = True
    first_name: str = ""
    last_name: str = ""
    credentials: list[dict] = None

    def __post_init__(self):
        self.username = self.email
