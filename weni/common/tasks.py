from datetime import timedelta

import requests
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from grpc._channel import _InactiveRpcError

from weni import utils
from weni.authentication.models import User
from weni.celery import app
from weni.common.models import Service, Organization, Project, LogService, BillingPlan


@app.task()
def status_service() -> None:
    def is_page_available(url: str, method_request: requests, **kwargs) -> bool:
        """This function retreives the status code of a website by requesting
        HEAD data from the host. This means that it only requests the headers.
        If the host cannot be reached or something else goes wrong, it returns
        False.
        """
        try:
            response = method_request(url=url, **kwargs)
            if int(response.status_code) == 200:
                return True
            return False
        except Exception:
            return False

    for service in Service.objects.all():
        if not service.maintenance:
            service.log_service.create(
                status=is_page_available(
                    url=service.url, method_request=requests.get, timeout=10
                )
            )


@app.task(name="delete_organization")
def delete_organization(inteligence_organization: int, user_email):
    grpc_instance = utils.get_grpc_types().get("inteligence")
    grpc_instance.delete_organization(
        organization_id=inteligence_organization,
        user_email=user_email,
    )
    return True


@app.task(name="update_organization")
def update_organization(inteligence_organization: int, organization_name: str):
    grpc_instance = utils.get_grpc_types().get("inteligence")
    grpc_instance.update_organization(
        organization_id=inteligence_organization,
        organization_name=organization_name,
    )
    return True


@app.task(
    name="update_user_permission_organization",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_user_permission_organization(
    inteligence_organization: int, user_email: str, permission: int
):
    grpc_instance = utils.get_grpc_types().get("inteligence")
    grpc_instance.update_user_permission_organization(
        organization_id=inteligence_organization,
        user_email=user_email,
        permission=permission,
    )
    return True


@app.task(
    name="update_project",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_project(organization_uuid: str, user_email: str, organization_name: str):
    grpc_instance = utils.get_grpc_types().get("flow")
    grpc_instance.update_project(
        organization_uuid=organization_uuid,
        user_email=user_email,
        organization_name=organization_name,
    )
    return True


@app.task(name="delete_project")
def delete_project(inteligence_organization: int, user_email):
    grpc_instance = utils.get_grpc_types().get("flow")
    grpc_instance.delete_project(
        project_uuid=inteligence_organization,
        user_email=user_email,
    )
    return True


@app.task(
    name="update_user_permission_project",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_user_permission_project(
    flow_organization: str, user_email: str, permission: int
):
    grpc_instance = utils.get_grpc_types().get("flow")
    grpc_instance.update_user_permission_project(
        organization_uuid=flow_organization,
        user_email=user_email,
        permission=permission,
    )
    return True


@app.task(name="migrate_organization")
def migrate_organization(user_email: str):
    user = User.objects.get(email=user_email)
    grpc_instance = utils.get_grpc_types().get("inteligence")

    organizations = grpc_instance.list_organizations(user_email=user_email)

    for organization in organizations:
        org, created = Organization.objects.get_or_create(
            inteligence_organization=organization.get("id"),
            defaults={"name": organization.get("name"), "description": ""},
        )

        role = grpc_instance.get_user_organization_permission_role(
            user_email=user_email, organization_id=organization.get("id")
        )

        org.authorizations.create(user=user, role=role)


@app.task(name="create_organization")
def create_organization(organization_name: str, user_email: str):
    grpc_instance = utils.get_grpc_types().get("inteligence")

    organization = grpc_instance.create_organization(
        organization_name=organization_name,
        user_email=user_email,
    )
    return {"id": organization.id}


@app.task(name="create_project")
def create_project(project_name: str, user_email: str, project_timezone: str):
    grpc_instance = utils.get_grpc_types().get("flow")

    project = grpc_instance.create_project(
        project_name=project_name,
        user_email=user_email,
        project_timezone=project_timezone,
    )
    return {"id": project.id, "uuid": project.uuid}


@app.task(
    name="update_user_language",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_user_language(user_email: str, language: str):
    utils.get_grpc_types().get("flow").update_language(
        user_email=user_email,
        language=language,
    )
    utils.get_grpc_types().get("inteligence").update_language(
        user_email=user_email,
        language=language,
    )
    return True


@app.task(name="search_project")
def search_project(organization_id: int, project_uuid: str, text: str):
    flow_result = (
        utils.get_grpc_types()
        .get("flow")
        .get_project_flows(
            project_uuid=project_uuid,
            flow_name=text,
        )
    )
    inteligence_result = (
        utils.get_grpc_types()
        .get("inteligence")
        .get_organization_inteligences(
            inteligence_name=text,
        )
    )
    return {
        "flow": flow_result,
        "inteligence": inteligence_result,
    }


@app.task()
def sync_updates_projects():
    for project in Project.objects.all():
        flow_instance = utils.get_grpc_types().get("flow")
        inteligence_instance = utils.get_grpc_types().get("inteligence")

        flow_result = flow_instance.get_project_info(
            project_uuid=str(project.flow_organization),
        )

        statistic_project_result = flow_instance.get_project_statistic(
            project_uuid=str(project.flow_organization),
        )

        classifiers_project = flow_instance.get_classifiers(
            project_uuid=str(project.flow_organization),
            classifier_type="bothub",
            is_active=True,
        )

        inteligences_org = inteligence_instance.get_count_inteligences_project(
            classifiers=classifiers_project,
        )

        project.name = str(flow_result.get("name"))
        project.timezone = str(flow_result.get("timezone"))
        project.date_format = str(flow_result.get("date_format"))
        project.inteligence_count = int(inteligences_org.get("repositories_count"))
        project.flow_count = int(statistic_project_result.get("active_flows"))
        project.contact_count = int(statistic_project_result.get("active_contacts"))

        project.save(
            update_fields=[
                "name",
                "timezone",
                "date_format",
                "inteligence_count",
                "flow_count",
                "contact_count",
            ]
        )

    return True


@app.task()
def generate_project_invoice():
    for org in Organization.objects.filter(
        organization_billing__next_due_date=timezone.now().date()
    ):
        invoice = org.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=10),
            invoice_random_id=1
            if org.organization_billing_invoice.last() is None
            else org.organization_billing_invoice.last().invoice_random_id + 1,
        )
        for project in org.project.all():
            invoice.organization_billing_invoice_project.create(
                project=project,
                contact_count=10,
                amount=invoice.calculate_amount(contact_count=10),
            )
        org.organization_billing.update(
            next_due_date=F("next_due_date")
            + timedelta(
                BillingPlan.BILLING_CYCLE_DAYS.get(org.organization_billing.get().cycle)
            )
        )


@app.task()
def delete_status_logs():
    BATCH_SIZE = 5000
    logs = LogService.objects.filter(
        created_at__lt=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        - timezone.timedelta(days=10)
    )

    num_updated = 0
    max_id = -1
    while True:
        batch = list(logs.filter(id__gt=max_id).order_by("id")[:BATCH_SIZE])

        if not batch:
            break

        max_id = batch[-1].id
        with transaction.atomic():
            for log in batch:
                log.delete()

        num_updated += len(batch)
        print(f" > deleted {num_updated} status logs")
