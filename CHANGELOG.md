## 3.29.13
  - Add project status field, to indicate if it is in test, active or inactive

# 3.29.12
## *Add*
  - Metrics endpoint for django-prometheus

# 3.29.11
## *Add*
  - Flag to indicate the mode (extended or opinionated) for a project
  - project_type validation, to prevent it from changing from general to commerce

# 3.29.10
## *Add*
  - Add sanitize function on Project and Organization name on creation

# 3.29.9
## *Add*
  - Adds request to the Insights module to update users' language preference.

# 3.29.8
## *Add*
  - Added a rate limiting decorator to prevent excessive requests.

# 3.29.7
## *Add*
  - Adds check when adding new permissions to the project if the request user is present on project

# 3.29.6
## *Add*
  - Add project authorization endpoint for retrieving user roles

# 3.29.5
## *Add*
  - Adding endpoint to check if exists project and user, if project exists and no user create user and set your permission in project and organization

# 3.29.4
## *Add*
  - Adding an endpoint to return an access token based on the username and password

# 3.29.3
## *Fix*
  - Organization's and project's name maximum length validation when creating them

# 3.29.2
## *Add*
  - Adding validation before deleting organization permissions if the user is the last admin of the organization.

# 3.29.1
## *Fix*
  - Fixing generate password algorithm for commerce user

# 3.29.0
## *Add*
  - Adding endpoint to create commerce organization/project and user

# 3.28.5
## *Add*
  - Adding Project Type (General or Commerce) to Project Model

# 3.28.4
## *Add*
  - Adding validation that only allows removing permissions if the request user is present in the organization

# 3.28.2
## *Remove*
  - Removing obsolete tasks

# 3.28.1
## *Add*
  - Reject recent activity case the entity or action is not valid.
  - Add action `UPDATE` to `NEXUS` entity on recent activity mapper.

# 3.28.0
## *Add*
  - Add to the `TemplateType` and `TemplateFeature` models to enable content translation.

# 3.27.8
## *Add*
  - Add to `show_chat_help` rule E-Commerce organizations

# 3.27.7
## *Add*
  - Add `show_chat_help` to Organization Serializer

# 3.27.6
## *Add*
  - Send the `brain_on` boolean via EDA on Project creation
  - Create the path for the HealthCheck
  - Update the path for the API documentation

# 3.27.5
## *Fix*
  - Deactivate unused tasks on Celery

# 3.27.4
## *Fix*
  - Implemented adjustment to remove only user-present projects when revoking organization permission.

# 3.27.3
## *Fix*
  - Fix error when try set Identity Provider for users

# 3.27.2
## *Add*
  - Add user Identity Provider on authentication

# 3.27.1
## *Add*
  - Add celery task to remove Recent Activities after 180 days
  - Add filter to exceptions on Sentry

# 3.27.0
## *Add*
  - Add mapper to identity_provider on keycloak
  - Add new fields to organization
  - Add new update password rule

# 3.26.1
## *Fix*
  - Fix error in permissions when create new user
  - Add new environment variable to set the max upload number fields

# 3.26.0
## *Add*
  - Add celery task to remove keycloak logs

# 3.25.0
## *Add*
  - Send email invitation when creating project authorization

# 3.24.0
## *Fix*
  - Fix inconsistent value for CHAT_USER permission when it's added in the project

# 3.23.0
## *Add*
  - RecentActivity via EDA

# 3.22.1
## *Fix*
  - fix role null

# 3.22.0
## *Add*
  - Send permissions via EDA

# 3.21.1
## *Update*
  - Set brain_on to always send false temporarily

# 3.21.1
## *Add*
  - RabbitMQ now sends brain_on status on project creation

# 3.20.0
## *Add*
  - RabbitMQ Consumer
  - RecentActivities usecases
  - Consuming RecentActivities messages using AMQP

# 3.19.1
## *Fix*
  - fix IsCRMUser get_object_or_404

# 3.19.0
## *Add*
  - Add IsCRMUser permission

# 3.18.0
## *Add*
  - Event driven publisher for orgs and org authorizations

# 3.17.3
## *Fix*
  - Fix wrong chats role mapping

# 3.17.2
## *Fix*
  - Flake8 imports and pep8
  - Remove unused unittest causing issues regarding updates
  - Fix CI issues regarding unittests
  - Fix celery not finding correct task no unittest

# 3.17.1
## *Add*
  - adding call to chats_update_permission on update_project_permission task

# 3.17.0
## *Remove*
  - Remove not used fields on project serializer to impro overall performace

# 3.16.0
## *Remove*
  - Remove authorizations list on org list api to improve overall performace.

# 3.15.1
## *Fix*
  - Async flow start not capable of handleling user instances

# 3.15.0
## *Add*
  - Sync queue for longer tasks on celery
  - Order function for Organization and Project API, ordering by any pre-existing valid field on the model.
  - Alert app and usecase functions
  - Alert CRUD

# 3.14.0
## *Change*
  - update project using usecase to send all messages
  - send organization uuid when send eda project creation message 
  - ensure that the image is more secure and effective, using a non-administrative user, using high ports (now using 8000), using multi-stage build, only one process per container, writing to /tmp and state check endpoints

## *Remove*:
- Remove ChatsPermission and IA permission when creating a organization and project.

# 3.13.2
## *Fix*
- synchronous call to delete_user_permission_project

# 3.13.1
## *Hotfix*
- remove send_message from tasks

# 3.13.0
## *Add*
  - project description

## *Update*
  - project description sended on project create and update

# 3.12.0
## *Remove*
  - Remove project authorization list from api return
  - AI unused env vars

# 3.11.1
  - change counting method for new attendances

# 3.11.0
  - Configure OIDC middleware to send user token to cache 
  - improve query in get_paginated_contacts
# 3.10.1
  - improve elasticsearch query

# 3.10.0
## *Add*
  - Create RecentActivity v2 create and list endpoint
  - New Pagination class for recent activity

# 3.9.1
## *Fix*
  - get_attendances call
# 3.9.0
## *Add*
  - Overwritte the saving method on admin billing plan to remove newsletter after changes.

# 3.8.2
## *Update*
  - method to count attendances
# 3.8.1
## *Fix*
  - get_contact_active_detailed filter contacts by project
# 3.8.0
## *Update*
  - Remove keycloak signal data update to make it on user serializer

# 3.7.3
## *Fix*
  - Fix task delete user permission

# 3.7.2
## *Fix*
  - NameError: name 'ChatsRole' is not defined
# 3.7.1
## *Add*
  - Request update chats and flows after project update
  - Request to delete user permission project in chats

# 3.7.0
## *Add*
  - Add new company phone field
  - Add new property for other fields position

# 3.6.3
## *Update*
  - Return all organization and company data to invite user in your first login

# 3.6.2
## *Add*
  - Endpoint to v2/organizations to return contacts
  - attribute plan_method to model BillingPlan
# 3.6.1
## *Fix*
  - Add company_segment to update_fields

# 3.6.0
## *Add*
  - authorizations project on create project message

## *Fix*
  - NoneType object has no attribute flow_uuid

## *Delete*
  - EDA: remove rest from project creation

# 3.5.1

## *Fix*
  - value from template_type to get code

## *Add*
  - method to mapping the template code from template name

# 3.5.0

## *Add*
  - New TemplateSuggestion api and model
  - Endpoint for obtaining company information from another user in the same organization

## *Update*
  - Fields changes on project serializer

# 3.4.0

## *Add*
  - New authorization endpoint on v2
  - New unittests for billing tasks

## *Fix*
  - Flake8 issues

# 3.3.0

## *Delete*
  - Remove TemplateAI api, models and unittests.

# 3.2.1

## *Add*
  - register ready from template type
  - internal endpoint to update project

## *Fix*
  - recent activity external user don't create a RecentActivity object

# 3.2.0

## *Add*
  - Cursor pagination to v2 organizations and v2 projects

# 3.1.0

## *update* 
  - Update UserIsPaying viewset query params and authorizations

## *Delete*
  - Remove unused tasks and models

# 3.0.0

## *Add*
  - New Event Driven Architectury to internal communication
  - Publisher code on rabbitmq
  - Connection class for connect the rabbitmq service
  - send messages to rabbitmq for create project and template type actions
  - template type now has the fields: uuid, base_project_uuid, description_photo

## *Delete*
  - Whatsapp Demo integration (now the integrations module make that)

# 2.19.0

## *Add*
  - Adding new fields to template type model

## *update*
  - unit tests to see the new fields

# 2.18.1

## *Add*
  - Improve views testing coverage
  - Adding a timeout to requests using ElasticFlow 

# 2.18.0

## *Add*

  - utm now is updated on add_additional_information endpoint
  - send the new utm field on marketing flow

## *Fix*

  - Serializer file name sintax

# 2.17.0

## *Add*
  - model to management of the send emails from organization and project by user
  - recovery data if that user receive emails on user serializer
  - Add new unit tests to improve serializer coverage 

## *Delete*

  - Remove celery project name task. Weni engine will now make it without flows dependency

# 2.16.0

## *Add*

  - Support for Project in AI module

# 2.15.2

## *Fix*

  - Fix some send email functions to multiple languages
  - Billing plan trial statement

## *Add*

  - Add new unit tests to improve models coverage 

# 2.15.1

## *Fix*

  - Add correct permissions for v2 project api

# 2.15.0

## *Change*

  - Architecture change where the weni-engine will change the project fields and send them to the flows.

# 2.14.0

## *Change*

  - project UUID instead of flow_organization in flows related endpoints

# 2.13.0

## *Change*

  - Change flows_rest_client statistic method calls to use project.uuid

## *Update*

  - Add try/except on statistic method on flows_rest_client.

# 2.12.2

## *Fix*

  - fix get_count_intelligences_project, wrong attribute for classifier

# 2.12.1

## *Fix*

  - Null invoice amount
  - Misplaced ZeroDivisionError


# 2.12.0

## *Add*

  - New template SAC + Chatgpt

## *Fix*
  - Task sync_project_information back to get and update project data from streams
  - Task sync_project_statistics adding error handling
# 2.11.0

## *Add*
  - New template type: Omie Lead Capture

## *Fix*
  - Email translation

## *Change*
  - Coverage from 73% to 75%

# 2.10.1

## *Fix*
  - Merge Migrations

# 2.10.0

## *Add*
  - New project template
  - Verify user after 2nd login

# 2.9.0
## *Fix*
  - template email translations
  - Delete organization newsletter after changing plan
## *Add*
  - Endpoint to get user info about organizations

# 2.8.1
## *Fix*
  - fix api_v2_urls import

# 2.8.0
## *Change*
  - Connect-Flows Communication; Passing `project.uuid` instead of `project.flow_organization`

# 2.7.2
## *Fix*
  - Increase timeout for get_project_statistic request

# 2.7.1
## *Fix*
  - Coverage Files

# 2.7.0
## *Add*
  - Template_project APP
  - Omie Template

# 2.5.0
## *Add*
  - NewsletterOrganization api

# 2.4.0

## *Add*
  - WeniAI external proxy server

# 2.2.0
## *Add*
  - New send email method
  - New template messages

# 2.1.0

## *Update*
  - Readme.md keycloack information
    - Enviroments variables needed for running keycloak

# 2.0.0
## *Add*
  - Updating routers for v2 api urls

# 1.2.1
## Change
  - Change `SyncManagerTask filter` in `count_contacts`  to only get objects with `status=True`
  - remove `task.wait()` from `retry_billing_tasks`
  - Replaces Message `get_or_create` method with `try/except`


# 1.2.0
## *Add*
  - Module permission class
    - On receive a request check if is a module
  - Internal communication class using rest
    - class with the generic request from connect to any weni module
  - New integrations rest endpoints
    - create endpoints on organization and project view to communicate with integrations
    - create endpoints and tasks to get integrations information with rest

# 1.1.2
## CHANGE:
  - fix `get_contact_detailed` method to get all documents instead of paginated results

# 1.1.1
## ADD:
  - exclude support users from authorization list

# 1.1.0
## ADD:
  - Suport Role to organization and project authorizations
  - Signal to add support on new organizations
  - Task to block organization if payment fails
  - Method to delete keycloak user data
  - `Changelog.md` file

## DELETE:
  - the send emails call needed with the design review and user experience

## CHANGE:
  - An organization admin can't be removed of an organization project
