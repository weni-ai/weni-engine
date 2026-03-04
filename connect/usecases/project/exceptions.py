from rest_framework.exceptions import NotFound


class ProjectNotFoundError(NotFound):
    default_detail = "Project not found."
