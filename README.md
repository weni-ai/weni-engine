# Weni

[![Build Status](https://travis-ci.com/Ilhasoft/weni-engine.svg?branch=main)](https://travis-ci.com/Ilhasoft/weni-engine)
[![Coverage Status](https://coveralls.io/repos/github/Ilhasoft/weni-engine/badge.svg?branch=main)](https://coveralls.io/github/Ilhasoft/weni-engine?branch=main)
[![Python Version](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/)
[![License GPL-3.0](https://img.shields.io/badge/license-%20GPL--3.0-yellow.svg)](https://github.com/Ilhasoft/weni-engine/blob/master/LICENSE)

## Environment Variables

You can set environment variables in your OS, write on ```.env``` file or pass via Docker config.

| Variable | Type | Default | Description |
|--|--|--|--|
| SECRET_KEY | ```string```|  ```None``` | A secret key for a particular Django installation. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value.
| DEBUG | ```boolean``` | ```False``` | A boolean that turns on/off debug mode.
| BASE_URL | ```string``` | ```https://api.weni.ai``` | URL Base Weni Engine Backend.
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
| USE_SENTRY |  ```bool``` | ```False``` | Enable Support Sentry
| SENTRY_URL |  ```string``` | ```None``` | URL Sentry
| APM_DISABLE_SEND |  ```bool``` | ```False``` | Disable sending Elastic APM
| APM_SERVICE_DEBUG |  ```bool``` | ```False``` | Enable APM debug mode
| APM_SERVICE_NAME |  ```string``` | ```''``` | APM Service Name
| APM_SECRET_TOKEN |  ```string``` | ```''``` | APM Secret Token
| APM_SERVER_URL |  ```string``` | ```''``` | APM URL
| FLOW_GRPC_ENDPOINT |  ```string``` | ```'localhost:8002'``` | gRPC Endpoint URL
| INTELIGENCE_GRPC_ENDPOINT |  ```string``` | ```'localhost:8003'``` | gRPC Endpoint URL
| ENVIRONMENT |  ```string``` | ```production``` | Specify the environment you are going to run, it is also used for sentry


## License

Distributed under the MPL-2.0 License. See `LICENSE` for more information.


## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
