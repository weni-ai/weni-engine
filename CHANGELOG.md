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
