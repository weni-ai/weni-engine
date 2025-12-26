from connect.celery import app as celery_app
from connect.common.models import Project
from connect.usecases.project.eda_publisher import ProjectEDAPublisher


class UpdateProjectUseCase:
    def __init__(self):
        self.eda_publisher = ProjectEDAPublisher()

    def send_updated_project(self, project: Project, user_email: str):

        # Publish update event via EDA to notify Flows and Billing
        self.eda_publisher.publish_project_updated(
            project_uuid=project.uuid,
            user_email=user_email,
            description=project.description,
            language=project.language,
        )
