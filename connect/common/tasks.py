from datetime import timedelta
from django.utils import timezone
import requests
from django.conf import settings
from django.db import transaction
from grpc._channel import _InactiveRpcError
from connect import utils, billing
from connect.authentication.models import User
from connect.celery import app
from connect.common.models import (
    Service,
    Organization,
    Project,
    LogService,
    BillingPlan,
    Invoice,
    GenericBillingData,
)


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
def update_project(organization_uuid: str, organization_name: str):
    grpc_instance = utils.get_grpc_types().get("flow")
    grpc_instance.update_project(
        organization_uuid=organization_uuid,
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
    flow_organization: str, project_uuid: str, user_email: str, permission: int
):
    flow_instance = utils.get_grpc_types().get("flow")
    integrations_instance = utils.get_grpc_types().get("integrations")
    flow_instance.update_user_permission_project(
        organization_uuid=flow_organization,
        user_email=user_email,
        permission=permission,
    )
    integrations_instance.update_user_permission_project(
        project_uuid=project_uuid,
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
def check_organization_free_plan():
    limits = GenericBillingData.objects.first() if GenericBillingData.objects.all().exists() else GenericBillingData.objects.create()
    for organization in Organization.objects.filter(organization_billing__plan='free'):
        current_active_contacts = 0
        print(current_active_contacts)
        for project in organization.project.all():
            print(project.contact_count)
            current_active_contacts += project.contact_count
        print(current_active_contacts)
        if current_active_contacts > limits.free_active_contacts_limit:
            organization.is_suspended = True
            for project in organization.project.all():
                app.send_task(
                    "update_suspend_project",
                    args=[
                        str(project.flow_organization),
                        True
                    ],
                )
    return True


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

        if project.organization.organization_billing.last_invoice_date is None:
            after = project.organization.created_at.strftime("%Y-%m-%d %H:%M")
        else:
            after = project.organization.organization_billing.last_invoice_date.strftime("%Y-%m-%d %H:%M")

        if project.organization.organization_billing.next_due_date is None:
            before = timezone.now().strftime("%Y-%m-%d %H:%M")
        else:
            before = project.organization.organization_billing.next_due_date.strftime("%Y-%m-%d %H:%M")

        contact_count = flow_instance.get_billing_total_statistics(
            project_uuid=str(project.flow_organization),
            before=before,
            after=after
        ).get("active_contacts")

        project.name = str(flow_result.get("name"))
        project.timezone = str(flow_result.get("timezone"))
        project.date_format = str(flow_result.get("date_format"))
        project.inteligence_count = int(inteligences_org.get("repositories_count"))
        project.flow_count = int(statistic_project_result.get("active_flows"))
        project.contact_count = int(contact_count)

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
        organization_billing__next_due_date__lte=timezone.now().date(),
        is_suspended=False,
    ):
        invoice = org.organization_billing_invoice.create(
            due_date=timezone.now() + timedelta(days=10),
            invoice_random_id=1
            if org.organization_billing_invoice.last() is None
            else org.organization_billing_invoice.last().invoice_random_id + 1,
            discount=org.organization_billing.fixed_discount,
            extra_integration=org.extra_integration,
            cost_per_whatsapp=settings.BILLING_COST_PER_WHATSAPP,
        )
        for project in org.project.all():
            flow_instance = utils.get_grpc_types().get("flow")

            contact_count = flow_instance.get_billing_total_statistics(
                project_uuid=str(project.flow_organization),
                before=(
                    org.created_at.strftime("%Y-%m-%d %H:%M")
                    if org.organization_billing.last_invoice_date is None
                    else org.organization_billing.last_invoice_date.strftime("%Y-%m-%d %H:%M")),
                after=org.organization_billing.next_due_date.strftime("%Y-%m-%d %H:%M"),
            ).get("active_contacts")
            invoice.organization_billing_invoice_project.create(
                project=project,
                contact_count=contact_count,
                amount=org.organization_billing.calculate_amount(
                    contact_count=contact_count
                ),
            )

        obj = BillingPlan.objects.get(id=org.organization_billing.pk)
        obj.next_due_date = org.organization_billing.next_due_date + timedelta(
            BillingPlan.BILLING_CYCLE_DAYS.get(org.organization_billing.cycle)
        )
        obj.last_invoice_date = timezone.now().date()
        obj.save(update_fields=["next_due_date", "last_invoice_date"])


@app.task()
def capture_invoice():
    for invoice in Invoice.objects.filter(
        payment_status=Invoice.PAYMENT_STATUS_PENDING, capture_payment=True
    ):
        gateway = billing.get_gateway("stripe")
        result = gateway.purchase(
            money=invoice.total_invoice_amount,
            identification=invoice.organization.organization_billing.stripe_customer,
            options={"id": invoice.pk},
        )
        if result.get("status") == "FAILURE":
            invoice.capture_payment = False
            invoice.save(update_fields=["capture_payment"])
            # add send email


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


@app.task(
    name="update_suspend_project",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_suspend_project(project_uuid: str, is_suspended: bool):
    utils.get_grpc_types().get("flow").suspend_or_unsuspend_project(
        project_uuid=project_uuid,
        is_suspended=is_suspended,
    )


@app.task(name="update_user_photo")
def update_user_photo(user_email: str, photo_url: str):
    integrations_instance = utils.get_grpc_types().get("integrations")
    integrations_instance.update_user(user_email, photo_url=photo_url)

    return True


@app.task(name="update_user_name")
def update_user_name(user_email: str, first_name: str, last_name: str):
    integrations_instance = utils.get_grpc_types().get("integrations")
    integrations_instance.update_user(user_email, first_name=first_name, last_name=last_name)

    return True
