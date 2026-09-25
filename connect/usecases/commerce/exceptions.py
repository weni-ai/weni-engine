class ProjectAlreadyHasVtexAccountError(Exception):
    """Raised when linking a vtex_account to a project that already has one."""


class VtexAccountAlreadyLinkedError(Exception):
    """Raised when the vtex_account is already linked to another project."""


class ProjectAuthorizationMissingError(Exception):
    """Raised when VTEX project create would return without ProjectAuthorization."""
