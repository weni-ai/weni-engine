import json
import pendulum
import grpc
from grpc._channel import _InactiveRpcError

from django.conf import settings

from connect import utils, billing
from connect.authentication.models import User
from connect.celery import app
from connect.common.models import (
    Organization,
    Project,
    Invoice,
    GenericBillingData,
    RecentActivity,
)

from connect.api.v1.internal.chats.chats_rest_client import ChatsRESTClient
from connect.api.v1.internal.flows.flows_rest_client import FlowsRESTClient
from connect.api.v1.internal.integrations.integrations_rest_client import (
    IntegrationsRESTClient,
)
from connect.api.v1.internal.intelligence.intelligence_rest_client import (
    IntelligenceRESTClient,
)
from connect.common.keycloak import KeycloakCleanup

import logging


logger = logging.getLogger(__name__)


@app.task(name="delete_organization")
def delete_organization(inteligence_organization: int, user_email):
    ai_client = IntelligenceRESTClient()
    ai_client.delete_organization(
        organization_id=inteligence_organization,
        user_email=user_email,
    )
    return True


@app.task(name="update_organization")
def update_organization(
    inteligence_organization: int, organization_name: str, user_email: str
):
    ai_client = IntelligenceRESTClient()
    ai_client.update_organization(
        organization_id=inteligence_organization,
        organization_name=organization_name,
        user_email=user_email,
    )
    return True


@app.task(name="update_user_permission_organization")
def update_user_permission_organization(
    inteligence_organization: int, user_email: str, permission: int
):
    ai_client = IntelligenceRESTClient()
    ai_client.update_user_permission_organization(
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
    flow_instance = FlowsRESTClient()
    chats = ChatsRESTClient()
    chats.update_chats_project(project_uuid=organization_uuid)
    flow_instance.update_project(
        project_uuid=organization_uuid,
        organization_name=organization_name,
    )
    return True


@app.task(name="delete_project")
def delete_project(project_uuid: str, user_email):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    flow_instance.delete_project(
        project_uuid=project_uuid,
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
    project_uuid: str, flow_organization: str, user_email: str, permission: int
):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    chats_client = ChatsRESTClient()
    integrations_client = IntegrationsRESTClient()

    flow_instance.update_user_permission_project(
        organization_uuid=flow_organization,
        user_email=user_email,
        permission=permission,
    )
    integrations_client.update_user_permission_project(
        project_uuid=project_uuid, user_email=user_email, role=permission
    )
    chats_client.update_user_permission(
        permission=permission, user_email=user_email, project_uuid=project_uuid
    )
    return True


@app.task(name="migrate_organization")
def migrate_organization(user_email: str):
    user = User.objects.get(email=user_email)
    ai_client = IntelligenceRESTClient()

    organizations = ai_client.list_organizations(user_email=user_email)

    for organization in organizations:
        org, created = Organization.objects.get_or_create(
            inteligence_organization=organization.get("id"),
            defaults={"name": organization.get("name"), "description": ""},
        )

        role = ai_client.get_user_organization_permission_role(
            user_email=user_email, organization_id=organization.get("id")
        )

        org.authorizations.create(user=user, role=role)


@app.task(name="create_organization")
def create_organization(organization_name: str, user_email: str):
    ai_client = IntelligenceRESTClient()
    organization = ai_client.create_organization(
        organization_name=organization_name,
        user_email=user_email,
    )
    return {"id": organization.id}


@app.task(name="get_contacts_detailed")
def get_contacts_detailed(project_uuid: str, before: str, after: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    project = Project.objects.get(uuid=project_uuid)
    response = []
    try:
        contacts = flow_instance.get_active_contacts(
            str(project.flow_organization), before, after
        )
        active_contacts_info = []
        for contact in contacts:
            active_contacts_info.append({"name": contact.name, "uuid": contact.uuid})
        response.append(
            {
                "project_name": project.name,
                "active_contacts": len(active_contacts_info),
                "contacts_info": active_contacts_info,
            }
        )
        return response
    except grpc.RpcError as e:
        if e.code() is not grpc.StatusCode.NOT_FOUND:
            raise e


@app.task(name="create_project")
def create_project(project_name: str, user_email: str, project_timezone: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    project = flow_instance.create_project(
        project_name=project_name,
        user_email=user_email,
        project_timezone=project_timezone,
    )
    return {"id": project.get("id"), "uuid": project.get("uuid")}


@app.task(name="create_template_project")
def create_template_project(project_name: str, user_email: str, project_timezone: str):

    rest_client = FlowsRESTClient()

    project = rest_client.create_template_project(
        project_name=project_name,
        user_email=user_email,
        project_timezone=project_timezone,
    )
    if project.get("status") == 201:
        uuid = json.loads(project.get("data")).get("uuid")
        return {"uuid": uuid}


@app.task(
    name="update_user_language",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_user_language(user_email: str, language: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    flow_instance.update_language(
        user_email=user_email,
        language=language,
    )
    IntelligenceRESTClient().update_language(
        user_email=user_email,
        language=language,
    )
    return True


@app.task(name="search_project")
def search_project(organization_id: int, project_uuid: str, text: str):
    if not settings.USE_FLOW_REST:
        flows_client = utils.get_grpc_types().get("flow")
    else:
        flows_client = FlowsRESTClient()
    flow_result = flows_client.get_project_flows(
        project_uuid=project_uuid, flow_name=text
    )

    inteligence_result = IntelligenceRESTClient().get_organization_intelligences(
        intelligence_name=text, organization_id=organization_id
    )
    return {
        "flow": flow_result,
        "inteligence": inteligence_result,
    }


@app.task()
def check_organization_free_plan():
    limits = GenericBillingData.get_generic_billing_data_instance()
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    for organization in Organization.objects.filter(
        organization_billing__plan="free", is_suspended=False
    ):
        for project in organization.project.all():
            project_timezone = project.timezone
            now = pendulum.now(project_timezone)
            before = now.strftime("%Y-%m-%d %H:%M")
            # first day of month
            after = now.start_of("month").strftime("%Y-%m-%d %H:%M")

            contact_count = flow_instance.get_billing_total_statistics(
                project_uuid=str(project.flow_organization), before=before, after=after
            ).get("active_contacts")
            project.contact_count = int(contact_count)
            project.save(update_fields=["contact_count"])
        current_active_contacts = organization.active_contacts
        if current_active_contacts > limits.free_active_contacts_limit:
            organization.is_suspended = True
            for project in organization.project.all():
                app.send_task(
                    "update_suspend_project",
                    args=[str(project.uuid), True],
                )
            organization.save(update_fields=["is_suspended"])
            organization.organization_billing.send_email_expired_free_plan(
                organization.name,
                organization.authorizations.values_list("user__email", flat=True),
            )
    return True


@app.task(name="sync_total_contact_count")
def sync_total_contact_count():
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    for project in Project.objects.all():
        response = flow_instance.get_project_statistic(project_uuid=str(project.uuid))
        contacts = response.get("active_contacts", project.total_contact_count)
        project.total_contact_count = contacts
        project.save(update_fields=["total_contact_count"])
    return True


@app.task()
def sync_repositories_statistics():
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    ai_client = IntelligenceRESTClient()

    for project in Project.objects.all():
        intelligence_count = 0
        if not settings.TESTING:
            classifiers_project = flow_instance.get_classifiers(
                project_uuid=str(project.flow_organization),
                classifier_type="bothub",
                is_active=True,
            )
            try:
                intelligence_count = int(
                    ai_client.get_count_intelligences_project(
                        classifiers=classifiers_project,
                    ).get("repositories_count")
                )
            except Exception:
                intelligence_count = 0

        project.inteligence_count = intelligence_count
        project.save(update_fields=["inteligence_count"])


@app.task()
def capture_invoice():
    for invoice in Invoice.objects.filter(
        payment_status=Invoice.PAYMENT_STATUS_PENDING, capture_payment=True
    ):
        gateway = billing.get_gateway("stripe")
        purchase_result = gateway.purchase(
            money=invoice.invoice_amount,
            identification=invoice.organization.organization_billing.stripe_customer,
            options={"id": invoice.pk},
        )
        if purchase_result.get("status") == "FAILURE":
            invoice.capture_payment = False
            invoice.save(update_fields=["capture_payment"])
            # add send email


@app.task(
    name="update_suspend_project",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def update_suspend_project(project_uuid: str, is_suspended: bool):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    flow_instance.suspend_or_unsuspend_project(
        project_uuid=project_uuid,
        is_suspended=is_suspended,
    )


@app.task(name="update_user_photo")
def update_user_photo(user_email: str, photo_url: str):

    chats_client = ChatsRESTClient()
    integrations_client = IntegrationsRESTClient()

    user = User.objects.filter(email=user_email)

    if user.exists():
        user = user.first()
        integrations_client.update_user(
            user_email=user_email,
            photo_url=photo_url,
        )
        chats_client.update_user(user_email=user_email, photo_url=photo_url)
    return True


@app.task(name="update_user_name")
def update_user_name(user_email: str, first_name: str, last_name: str):

    chats_client = ChatsRESTClient()
    integrations_client = IntegrationsRESTClient()

    user = User.objects.filter(email=user_email)

    if user.exists():
        user = user.first()
        integrations_client.update_user(
            user_email=user_email, first_name=first_name, last_name=last_name
        )
        chats_client.update_user(
            user_email=user_email, first_name=first_name, last_name=last_name
        )
    return True


@app.task(name="get_billing_total_statistics")
def get_billing_total_statistics(project_uuid: str, before: str, after: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    contact_count = flow_instance.get_billing_total_statistics(
        project_uuid=str(project_uuid),
        before=before,
        after=after,
    )

    return contact_count


@app.task(
    name="delete_user_permission_project",
    autoretry_for=(_InactiveRpcError, Exception),
    retry_kwargs={"max_retries": 5},
    retry_backoff=True,
)
def delete_user_permission_project(
    flow_organization: str, project_uuid: str, user_email: str, permission: int
):
    flow_instance = FlowsRESTClient()
    chats_instance = ChatsRESTClient()

    flow_instance.delete_user_permission_project(
        project_uuid=flow_organization, user_email=user_email, permission=permission
    )

    chats_instance.delete_user_permission_project(
        project_uuid=project_uuid, user_email=user_email, permission=permission
    )


@app.task(name="list_channels")
def list_channels(channel_type):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
        response = flow_instance.list_channel(channel_type=channel_type)
    else:
        flow_instance = utils.get_grpc_types().get("flow")
        response = list(flow_instance.list_channel(channel_type=channel_type))
    channels = []
    for channel in response:
        org = channel.get("org") if settings.USE_FLOW_REST else channel.org
        project = Project.objects.filter(flow_organization=org)
        if project:
            project = project.first()
            if settings.USE_FLOW_REST:
                channel_data = dict(
                    uuid=str(channel.get("uuid")),
                    name=channel.get("name"),
                    config=channel.get("config"),
                    address=channel.get("address"),
                    project_uuid=str(project.uuid),
                    is_active=channel.get("is_active"),
                )
            else:
                channel_data = dict(
                    uuid=str(channel.uuid),
                    name=channel.name,
                    config=channel.config,
                    address=channel.address,
                    project_uuid=str(project.uuid),
                    is_active=channel.is_active,
                )
            channels.append(channel_data)
    return channels


@app.task(name="release_channel")
def realease_channel(channel_uuid, user):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    flow_instance.release_channel(
        channel_uuid=channel_uuid,
        user=user,
    )
    return True


@app.task(name="create_channel")
def create_channel(user, project_uuid, data, channeltype_code):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
        return flow_instance.create_channel(
            user=user,
            project_uuid=project_uuid,
            data=data,
            channeltype_code=channeltype_code,
        )
    else:
        flow_instance = utils.get_grpc_types().get("flow")

    try:
        response = flow_instance.create_channel(
            user=user,
            project_uuid=project_uuid,
            data=data,
            channeltype_code=channeltype_code,
        )
        return dict(
            uuid=response.uuid,
            name=response.name,
            config=response.config,
            address=response.address,
        )
    except grpc.RpcError as error:
        raise error


@app.task(name="create_wac_channel")
def create_wac_channel(user, flow_organization, config, phone_number_id):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
        return flow_instance.create_wac_channel(
            user=user,
            flow_organization=str(flow_organization),
            config=config,
            phone_number_id=phone_number_id,
        )
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    try:
        response = flow_instance.create_wac_channel(
            user=user,
            flow_organization=str(flow_organization),
            config=config,
            phone_number_id=phone_number_id,
        )
        return dict(
            uuid=response.uuid,
            name=response.name,
            config=response.config,
            address=response.address,
        )
    except grpc.RpcError as error:
        raise error


@app.task(name="retrieve_classifier")
def retrieve_classifier(classifier_uuid: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    response = flow_instance.get_classifiers(
        classifier_uuid=str(classifier_uuid),
    )
    return dict(
        authorization_uuid=response.get("access_token"),
        classifier_type=response.get("classifier_type"),
        name=response.get("name"),
        is_active=response.get("is_active"),
        uuid=response.get("uuid"),
    )


@app.task(name="destroy_classifier")
def destroy_classifier(classifier_uuid: str, user_email: str):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    flow_instance.delete_classifier(
        classifier_uuid=str(classifier_uuid),
        user_email=str(user_email),
    )
    return True


@app.task(name="create_classifier")
def create_classifier(
    project_uuid: str, user_email: str, classifier_name: str, access_token
):
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    response = flow_instance.create_classifier(
        project_uuid=project_uuid,
        user_email=user_email,
        classifier_type="bothub",
        classifier_name=classifier_name,
        access_token=access_token,
    )
    return response.get("data", {})


@app.task(name="list_classifier")
def list_classifier(project_uuid: str):
    classifiers = {"data": []}
    if settings.USE_FLOW_REST:
        flow_instance = FlowsRESTClient()
    else:
        flow_instance = utils.get_grpc_types().get("flow")
    response = flow_instance.get_classifiers(
        project_uuid=str(project_uuid),
        classifier_type="bothub",
        is_active=True,
    )
    for i in response:
        authorization = (
            i.get("access_token")
            if settings.USE_FLOW_REST
            else i.get("authorization_uuid")
        )
        classifiers["data"].append(
            {
                "authorization_uuid": authorization,
                "classifier_type": i.get("classifier_type"),
                "name": i.get("name"),
                "is_active": i.get("is_active"),
                "uuid": i.get("uuid"),
            }
        )
    return classifiers


@app.task(name="list_project_flows")
def list_project_flows(flow_organization: str):
    flow_type = utils.get_grpc_types().get("flow")
    return flow_type.list_flows(flow_organization)


@app.task(name="delete_recent_activities")
def delete_recent_activities():
    date_limit = pendulum.now().start_of("day").subtract(days=180)
    RecentActivity.objects.filter(created_on__lte=date_limit).delete()


@app.task(name="send_user_flow_info", ignore_result=True)
def send_user_flow_info(
    flow_data: dict,
    user_email: str,
) -> bool:
    try:
        user = User.objects.get(email=user_email)
        user.send_request_flow_user_info(flow_data=flow_data)
        return True
    except Exception as e:
        logger.error(e)
        return False


@app.task
def keycloak_logs_cleanup_routine():
    date_time = pendulum.now().subtract(months=1)
    client = KeycloakCleanup()
    client.delete(date_time)
    client.vacuum()
