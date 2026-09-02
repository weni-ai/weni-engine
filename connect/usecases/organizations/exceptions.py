class OrganizationDoesNotExist(BaseException):
    pass


class SSOConfigLockoutError(Exception):
    """Raised when enabling an SSO policy would lock the acting admin out."""
    pass


class SSOPolicyValidationError(Exception):
    """Raised when a resulting organization SSO policy violates invariants I1–I4."""
    pass
