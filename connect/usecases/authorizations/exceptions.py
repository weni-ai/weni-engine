from rest_framework.exceptions import NotFound, ValidationError


class UserHasNoPermissionToManageProject(Exception):
    pass


class UserNotFoundError(NotFound):
    default_detail = "User not found."


class ProjectAuthorizationNotFoundError(NotFound):
    default_detail = "Project authorization not found."


class MultipleProjectsForVtexAccountError(ValidationError):
    default_detail = "Multiple projects found for this VTEX account."
