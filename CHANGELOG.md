# 1.2.0
## *Added*
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
