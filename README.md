# Weni

[![Build Status](https://github.com/ilhasoft/weni-engine/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Ilhasoft/weni-engine/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage Status](https://coveralls.io/repos/github/Ilhasoft/weni-engine/badge.svg?branch=main)](https://coveralls.io/github/Ilhasoft/weni-engine?branch=main)
[![Python Version](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

## Index

[Running locally](#running)

[Environment Variables List](#environment-variables-list)

[License](#license)

[Contributing](#contributing)

## Running

```sh
git clone https://github.com/weni-ai/weni-engine.git
```

### Keycloak

[Docs](https://www.keycloak.org/guides#getting-started) | [Docker](https://hub.docker.com/r/jboss/keycloak/)

```sh
docker run -p 8080:8080 -e KEYCLOAK_USER=<USERNAME> -e KEYCLOAK_PASSWORD=<PASSWORD> jboss/keycloak
```

Keycloak will be running on `http://localhost:8080`

#### Setting up the clients

1. [Create a new realm](https://www.keycloak.org/getting-started/getting-started-docker#_create_a_realm), not recommended to use master realm

2. Setup the clients 

Each service uses a client

- Backend:
    1. Create a client for the back-end
    2. Set your access type to `confidential`
    3. Standard Flow Enabled: On
    4. Service Account Enabled: On
    5. Service Account Roles --> Client Roles --> realm-management (user related roles)
- Frontend:
    1. Create a client for the front-end
    2. Access Type: public
    3. Standard Flow Enabled: on
    4. Direct Access Grants Enabled: On

### Environment Variables

`OIDC_RP_CLIENT_ID` and `OIDC_RP_CLIENT_SECRET` refers to backend client credentials 

`<KEYCLOAK-SERVER-URL>` could be `https://<your-keycloak-host>/` or `https://your-keycloak-host/auth/` depending on the keycloak version

You can get the `OIDC_RP_*` variables at: `https://your-keycloak-host/realms/<realm-name>/.well-known/openid-configuration`
> Ex for keycloak 16.1: `http://127.0.0.1:8080/auth/realms/engine_realm/.well-known/openid-configuration`

engine_realm as realm name

### Required environment variables

```
SECRET_KEY=<SECRET_KEY>
OIDC_RP_REALM_NAME=<KEYCLOAK-REALM-NAME>
OIDC_RP_CLIENT_ID=<KEYCLOAK-CLIENT-ID>
OIDC_RP_CLIENT_SECRET=<KEYCLOAK-CLIENT-SECRET>
OIDC_OP_LOGOUT_ENDPOINT=<KEYCLOAK-SERVER-URL>/realms/<KEYCLOAK-REALM-NAME>/protocol/openid-connect/logout
OIDC_OP_TOKEN_ENDPOINT=<KEYCLOAK-SERVER-URL>/auth/realms/<KEYCLOAK-REALM-NAME>/protocol/openid-connect/token
OIDC_RP_SCOPES=email profile openid offline_access
OIDC_OP_AUTHORIZATION_ENDPOINT=<KEYCLOAK-SERVER-URL>/realms/<KEYCLOAK-REALM-NAME>/protocol/openid-connect/auth
OIDC_RP_SIGN_ALGO= Sets the algorithm the IdP uses to sign ID tokens.
OIDC_RP_SERVER_URL=<KEYCLOAK-SERVER-URL>
OIDC_OP_USER_ENDPOINT=<KEYCLOAK-SERVER-URL>/auth/realms/<KEYCLOAK-REALM-NAME>/protocol/openid-connect/userinfo
OIDC_OP_JWKS_ENDPOINT=<KEYCLOAK-SERVER-URL>/auth/realms/<KEYCLOAK-REALM-NAME>/protocol/openid-connect/certs
```

## Environment Variables List

You can set environment variables in your OS, write on ```.env``` file or pass via Docker config.

| Variable | Type | Default | Description |
|--|--|--|--|
| SECRET_KEY | ```string```|  ```None``` | A secret key for a particular Django installation. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value.
| DEBUG | ```boolean``` | ```False``` | A boolean that turns on/off debug mode.
| BASE_URL | ```string``` | ```https://api.weni.ai``` | URL Base Weni Engine Backend.
| WEBAPP_BASE_URL | ```string``` | ```https://dash.weni.ai``` | URL Base Weni Webapp.
| ALLOWED_HOSTS | ```string``` | ```*``` | A list of strings representing the host/domain names that this Django site can serve.
| DEFAULT_DATABASE | ```string``` | ```sqlite:///db.sqlite3``` | Read [django-environ](https://django-environ.readthedocs.io/en/latest/) to configure the database connection.
| LANGUAGE_CODE | ```string``` | ```en-us``` | A string representing the language code for this installation.This should be in standard [language ID format](https://docs.djangoproject.com/en/2.0/topics/i18n/#term-language-code).
| TIME_ZONE | ```string``` | ```UTC``` | A string representing the time zone for this installation. See the [list of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
| STATIC_URL | ```string``` | ```/static/``` | URL to use when referring to static files located in ```STATIC_ROOT```.
| CSRF_COOKIE_DOMAIN | ```string``` | ```None``` | The domain to be used when setting the CSRF cookie.
| CSRF_COOKIE_SECURE | ```boolean``` | ```False``` | Whether to use a secure cookie for the CSRF cookie.
| OIDC_RP_SERVER_URL | ```string``` | ```None``` | Open ID Connect Server URL, example: https://accounts.weni.ai/auth/.
| OIDC_RP_REALM_NAME | ```string``` | ```None``` | Open ID Connect Realm Name.
| OIDC_RP_CLIENT_ID | ```string``` | ```None``` | OpenID Connect client ID provided by your OP.
| OIDC_RP_CLIENT_SECRET | ```string``` | ```None``` | OpenID Connect client secret provided by your OP.
| OIDC_OP_AUTHORIZATION_ENDPOINT | ```string``` | ```None``` | URL of your OpenID Connect provider authorization endpoint.
| OIDC_OP_TOKEN_ENDPOINT | ```string``` | ```None``` | URL of your OpenID Connect provider token endpoint.
| OIDC_OP_USER_ENDPOINT | ```string``` | ```None``` | URL of your OpenID Connect provider userinfo endpoint.
| OIDC_OP_JWKS_ENDPOINT | ```string``` | ```None``` | URL of your OpenID Connect provider JWKS endpoint.
| OIDC_RP_SIGN_ALGO | ```string``` | ```RS256``` | Sets the algorithm the IdP uses to sign ID tokens.
| OIDC_DRF_AUTH_BACKEND | ```string``` | ```weni.oidc_authentication.WeniOIDCAuthenticationBackend``` | Define the authentication middleware for the django rest framework.
| AWS_ACCESS_KEY_ID | ```string``` | ```None``` | Specify Access Key ID S3.
| AWS_SECRET_ACCESS_KEY | ```string``` | ```None``` | Specify Secret Access Key ID S3.
| AWS_STORAGE_BUCKET_NAME | ```string``` | ```None``` | Specify Bucket Name S3.
| AWS_S3_REGION_NAME | ```string``` | ```None``` | Specify the Bucket S3 region.
| EMAIL_HOST | ```string``` | ```None``` | The host to use for sending email. When setted to ```None``` or empty string, the ```EMAIL_BACKEND``` setting is setted to ```django.core.mail.backends.console.EmailBackend```
| EMAIL_PORT | ```int``` | ```25``` | Port to use for the SMTP server defined in ```EMAIL_HOST```.
| DEFAULT_FROM_EMAIL | ```string``` | ```webmaster@localhost``` | Default email address to use for various automated correspondence from the site manager(s).
| SERVER_EMAIL | ```string``` | ```root@localhost``` | The email address that error messages come from, such as those sent to ```ADMINS``` and ```MANAGERS```.
| EMAIL_HOST_USER | ```string``` | ```''``` | Username to use for the SMTP server defined in ```EMAIL_HOST```.
| EMAIL_HOST_PASSWORD | ```string``` | ```''``` | Password to use for the SMTP server defined in ```EMAIL_HOST```.
| EMAIL_USE_SSL | ```boolean``` | ```False``` | Whether to use an implicit TLS (secure) connection when talking to the SMTP server.
| EMAIL_USE_TLS | ```boolean``` | ```False``` | Whether to use a TLS (secure) connection when talking to the SMTP server.
| SEND_EMAILS | ```boolean``` | ```True``` | Send emails flag.
| INTELIGENCE_URL | ```string``` | ```https://bothub.it/``` | Specify the URL of the intelligence service.
| FLOWS_URL | ```string``` | ```https://new.push.al/``` | Specify the URL of the flows service.
| INTEGRATIONS_URL | ```string``` | ```None``` | Specify the URL of the integration service.
| USE_SENTRY |  ```bool``` | ```False``` | Enable Support Sentry
| SENTRY_URL |  ```string``` | ```None``` | URL Sentry
| APM_DISABLE_SEND |  ```bool``` | ```False``` | Disable sending Elastic APM
| APM_SERVICE_DEBUG |  ```bool``` | ```False``` | Enable APM debug mode
| APM_SERVICE_NAME |  ```string``` | ```''``` | APM Service Name
| APM_SECRET_TOKEN |  ```string``` | ```''``` | APM Secret Token
| APM_SERVER_URL |  ```string``` | ```''``` | APM URL
| FLOW_GRPC_ENDPOINT |  ```string``` | ```'localhost:8002'``` | gRPC Endpoint URL
| INTELIGENCE_GRPC_ENDPOINT |  ```string``` | ```'localhost:8003'``` | gRPC Endpoint URL
| INTEGRATIONS_GRPC_ENDPOINT |  ```string``` | ```'localhost:8004'``` | gRPC Endpoint URL
| SYNC_ORGANIZATION_INTELIGENCE |  ```bool``` | ```False``` | Enable or Disable sync organization inteligences service
| INTELIGENCE_CERTIFICATE_GRPC_CRT |  ```string``` | ```None``` | Absolute certificate path for secure grpc communication
| FLOW_CERTIFICATE_GRPC_CRT |  ```string``` | ```None``` | Absolute certificate path for secure grpc communication
| INTEGRATIONS_CERTIFICATE_GRPC_CRT |  ```string``` | ```None``` | Absolute certificate path for secure grpc communication
| SEND_REQUEST_FLOW |  ```boolean``` | ```False``` | Enables or disables sending user information to flows
| FLOW_MARKETING_UUID |  ```string``` | ```None``` | UUID Flow
| TOKEN_AUTHORIZATION_FLOW_MARKETING |  ```string``` | ```None``` | Token Authorization API Flow
| BILLING_TEST_MODE |  ```boolean``` | ```False``` | Configure Test mode Billing
| BILLING_SETTINGS |  ```json``` | ```{}``` | Set configuration for gateways payment billing
| BILLING_COST_PER_WHATSAPP |  ```float``` | ```None``` | Set cost for extra whatsapp
| TOKEN_EXTERNAL_AUTHENTICATION |  ```string``` | ```None``` | Token External Authorization API
| ENVIRONMENT |  ```string``` | ```production``` | Specify the environment you are going to run, it is also used for sentry


## License

Distributed under the MPL-2.0 License. See `LICENSE` for more information.

## Running

[Install docker](https://docs.docker.com/get-docker/)

Create an .env file in the project root and add the above environment variables

For authentication, we use Keycloak, you need to run it locally:
  - [Documentation](https://www.keycloak.org/documentation.html)

Execute `docker-compose build` to build application

Execute `docker-compose up` to up the server

Very good, your application is running :rocket:                                   


## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

To see more go to the [Weni Platform central repository](https://github.com/Ilhasoft/weni-platform).