from rest_framework.exceptions import NotFound, ValidationError


class ProjectNotFoundError(NotFound):
    default_detail = "Project not found."


class OrganizationNotFoundError(NotFound):
    default_detail = "Organization not found."


class SameOrganizationMigrationError(ValidationError):
    default_detail = "Destination organization must differ from the current one."


class ProjectMigrationNotFoundError(NotFound):
    default_detail = "Project migration not found."


class ProjectMigrationRepublishError(ValidationError):
    default_detail = "Only migrations with PUBLISH_FAILED status can be republished."
