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
