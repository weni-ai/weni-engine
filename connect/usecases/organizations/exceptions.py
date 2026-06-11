class OrganizationDoesNotExist(BaseException):
    pass


class SSOConfigLockoutError(Exception):
    """Raised when enabling an SSO policy would lock the acting admin out."""
    pass
