"""
Django settings for weni project.

Generated by 'django-admin startproject' using Django 2.2.17.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
import sys

import environ
from django.utils.log import DEFAULT_LOGGING
from django.utils.translation import ugettext_lazy as _

environ.Env.read_env(env_file=(environ.Path(__file__) - 2)(".env"))

env = environ.Env(
    # set casting, default value
    ENVIRONMENT=(str, "production"),
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(lambda v: [s.strip() for s in v.split(",")], "*"),
    LANGUAGE_CODE=(str, "en-us"),
    TIME_ZONE=(str, "UTC"),
    STATIC_URL=(str, "/static/"),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/0"),
    AWS_ACCESS_KEY_ID=(str, None),
    AWS_SECRET_ACCESS_KEY=(str, None),
    AWS_STORAGE_BUCKET_NAME=(str, None),
    AWS_S3_REGION_NAME=(str, None),
    EMAIL_HOST=(lambda v: v or None, None),
    DEFAULT_FROM_EMAIL=(str, "webmaster@localhost"),
    SERVER_EMAIL=(str, "root@localhost"),
    EMAIL_PORT=(int, 25),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    EMAIL_USE_SSL=(bool, False),
    EMAIL_USE_TLS=(bool, False),
    SEND_EMAILS=(bool, True),
    CSRF_COOKIE_DOMAIN=(lambda v: v or None, None),
    CSRF_COOKIE_SECURE=(bool, False),
    BASE_URL=(str, "https://api.weni.ai"),
    WEBAPP_BASE_URL=(str, "https://dash.weni.ai"),
    CHATS_URL=(str, "https://chats.dev.cloud.weni.ai/"),
    INTELIGENCE_URL=(str, "https://bothub.it/"),
    FLOWS_URL=(str, "https://new.push.al/"),
    FLOWS_ELASTIC_URL=(str, None),
    FLOWS_REST_ENDPOINT=(str, "https://flows-staging.weni.ai"),
    INTEGRATIONS_URL=(str, None),
    USE_SENTRY=(bool, False),
    SENTRY_URL=(str, None),
    APM_DISABLE_SEND=(bool, False),
    APM_SERVICE_DEBUG=(bool, False),
    APM_SERVICE_NAME=(str, ""),
    APM_SECRET_TOKEN=(str, ""),
    APM_SERVER_URL=(str, ""),
    FLOW_GRPC_ENDPOINT=(str, "localhost:8002"),
    INTELIGENCE_GRPC_ENDPOINT=(str, "localhost:8003"),
    INTEGRATIONS_GRPC_ENDPOINT=(str, "localhost:8004"),
    SYNC_ORGANIZATION_INTELIGENCE=(bool, False),
    INTELIGENCE_CERTIFICATE_GRPC_CRT=(str, None),
    FLOW_CERTIFICATE_GRPC_CRT=(str, None),
    INTEGRATIONS_CERTIFICATE_GRPC_CRT=(str, None),
    CHATS_REST_ENDPOINT=(str, "https://chats-engine.dev.cloud.weni.ai"),
    INTEGRATIONS_REST_ENDPOINT=(str, "https://integrations-engine.dev.cloud.weni.ai"),
    INTELLIGENCE_REST_ENDPOINT=(str, "https://engine-ai.dev.cloud.weni.ai/"),
    INSIGHTS_REST_ENDPOINT=(str, "https://insights-engine.dev.cloud.weni.ai"),
    SEND_REQUEST_FLOW=(bool, False),
    FLOW_MARKETING_UUID=(str, None),
    TOKEN_AUTHORIZATION_FLOW_MARKETING=(str, None),
    BILLING_TEST_MODE=(bool, False),
    BILLING_SETTINGS=(dict, {}),
    TOKEN_EXTERNAL_AUTHENTICATION=(str, None),
    ROCKET_CLIENT_ID=(str, None),
    ROCKET_USERNAME=(str, None),
    ROCKET_PASSWORD=(str, None),
    ROCKET_TEST_MODE=(bool, False),
    VERIFICATION_AMOUNT=(float, 1),
    SYNC_CONTACTS_SCHEDULE=(str, "*/1"),
    SCROLL_SIZE=(int, 500),
    SCROLL_KEEP_ALIVE=(str, "1m"),
    USE_FLOW_REST=(bool, True),
    PLAN_TRIAL_PRICE=(int, 0),
    PLAN_TRIAL_LIMIT=(int, 100),
    PLAN_START_LIMIT=(int, 200),
    PLAN_START_PRICE=(int, 390),
    PLAN_SCALE_LIMIT=(int, 500),
    PLAN_SCALE_PRICE=(int, 689),
    PLAN_ADVANCED_LIMIT=(int, 1000),
    PLAN_ADVANCED_PRICE=(int, 999),
    PLAN_ENTERPRISE_LIMIT=(str, "limitless"),
    PLAN_ENTERPRISE_PRICE=(str, "Contact the suport team"),
    DEFAULT_CURRENCY=(str, "BRL"),
    SEND_REQUEST_FLOW_PRODUCT=(bool, False),
    FLOW_PRODUCT_UUID=(str, None),
    TOKEN_AUTHORIZATION_FLOW_PRODUCT=(str, None),
    CREATE_AI_ORGANIZATION=(bool, False),
    VERIFICATION_MARKETING_TOKEN=(str, ""),
    ELASTICSEARCH_TIMEOUT_REQUEST=(int, 10),
    FILTER_SENTRY_EVENTS=(list, []),
    RATE_LIMIT_REQUESTS=(int, 10),
    RATE_LIMIT_WINDOW=(int, 60),
    RATE_LIMIT_BLOCK_TIME=(int, 300),
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

BASE_URL = env.str("BASE_URL")

WEBAPP_BASE_URL = env.str("WEBAPP_BASE_URL")

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_yasg2",
    "django_filters",
    "mozilla_django_oidc",
    "elasticapm.contrib.django",
    "connect.authentication.apps.AuthenticationConfig",
    "connect.common.apps.CommonConfig",
    "connect.billing",
    "connect.internals",
    "connect.template_projects",
    "connect.alerts",
    "connect.sentry",
    "django_celery_results",
    "django_celery_beat",
    "storages",
    "corsheaders",
    "django_grpc_framework",
    "stripe",
    "django_prometheus",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "elasticapm.contrib.django.middleware.TracingMiddleware",
    "elasticapm.contrib.django.middleware.Catch404Middleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "connect.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "elasticapm.contrib.django.context_processors.rum_tracing",
            ]
        },
    }
]

WSGI_APPLICATION = "connect.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {"default": env.db(var="DEFAULT_DATABASE", default="sqlite:///db.sqlite3")}


# Auth

AUTH_USER_MODEL = "authentication.User"


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

DEFAULT_ERROR_MESSAGE = _("An error has occurred")

LANGUAGE_CODE = env.str("LANGUAGE_CODE")

# -----------------------------------------------------------------------------------
# Available languages for translation
# -----------------------------------------------------------------------------------
LANGUAGES = (("en-us", _("English")), ("pt-br", _("Portuguese")), ("es", _("Spanish")))

MODELTRANSLATION_DEFAULT_LANGUAGE = "en-us"

LOCALE_PATHS = (os.path.join(os.path.dirname(__file__), "locale"),)

DEFAULT_LANGUAGE = "en-us"

TIME_ZONE = env.str("TIME_ZONE")

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = env.str("STATIC_URL")

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Logging

LOGGING = DEFAULT_LOGGING
LOGGING["handlers"]["elasticapm"] = {
    "level": "WARNING",
    "class": "elasticapm.contrib.django.handlers.LoggingHandler",
}
LOGGING["formatters"]["verbose"] = {
    "format": "%(levelname)s  %(asctime)s  %(module)s "
    "%(process)d  %(thread)d  %(message)s"
}
LOGGING["handlers"]["console"] = {
    "level": "DEBUG",
    "class": "logging.StreamHandler",
    "formatter": "verbose",
}
LOGGING["loggers"]["django.db.backends"] = {
    "level": "ERROR",
    "handlers": ["console"],
    "propagate": False,
}
LOGGING["loggers"]["sentry.errors"] = {
    "level": "DEBUG",
    "handlers": ["console"],
    "propagate": False,
}
LOGGING["loggers"]["elasticapm.errors"] = {
    "level": "ERROR",
    "handlers": ["console"],
    "propagate": False,
}
LOGGING["loggers"]["connect.authentication.signals"] = {
    "level": "ERROR",
    "handlers": ["console"],
    "propagate": False,
}
LOGGING["loggers"]["mozilla_django_oidc"] = {
    "level": "DEBUG",
    "handlers": ["console"],
    "propagate": False,
}

# rest framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "connect.middleware.WeniOIDCAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

if TESTING:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].append(
        "rest_framework.authentication.TokenAuthentication"
    )

# CSRF

CSRF_COOKIE_DOMAIN = env.str("CSRF_COOKIE_DOMAIN")

CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE")

# Sentry Environment

USE_SENTRY = env.bool("USE_SENTRY")
SENTRY_URL = env.str("SENTRY_URL")
ENVIRONMENT = env.str("ENVIRONMENT")
FILTER_SENTRY_EVENTS = env.list("FILTER_SENTRY_EVENTS")

# Elastic Observability APM
ELASTIC_APM = {
    "DISABLE_SEND": env.bool("APM_DISABLE_SEND"),
    "DEBUG": env.bool("APM_SERVICE_DEBUG"),
    "SERVICE_NAME": env.str("APM_SERVICE_NAME"),
    "SECRET_TOKEN": env.str("APM_SECRET_TOKEN"),
    "SERVER_URL": env.str("APM_SERVER_URL"),
    "ENVIRONMENT": env.str("ENVIRONMENT"),
    "DJANGO_TRANSACTION_NAME_FROM_ROUTE": True,
    "PROCESSORS": [
        "elasticapm.processors.sanitize_stacktrace_locals",
        "elasticapm.processors.sanitize_http_request_cookies",
        "elasticapm.processors.sanitize_http_headers",
        "elasticapm.processors.sanitize_http_wsgi_env",
        "elasticapm.processors.sanitize_http_request_body",
    ],
}

# mozilla-django-oidc
OIDC_RP_SERVER_URL = env.str("OIDC_RP_SERVER_URL")
OIDC_RP_REALM_NAME = env.str("OIDC_RP_REALM_NAME")
OIDC_RP_CLIENT_ID = env.str("OIDC_RP_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = env.str("OIDC_RP_CLIENT_SECRET")
OIDC_OP_AUTHORIZATION_ENDPOINT = env.str("OIDC_OP_AUTHORIZATION_ENDPOINT")
OIDC_OP_TOKEN_ENDPOINT = env.str("OIDC_OP_TOKEN_ENDPOINT")
OIDC_OP_USER_ENDPOINT = env.str("OIDC_OP_USER_ENDPOINT")
OIDC_OP_JWKS_ENDPOINT = env.str("OIDC_OP_JWKS_ENDPOINT")
OIDC_RP_SIGN_ALGO = env.str("OIDC_RP_SIGN_ALGO", default="RS256")
OIDC_DRF_AUTH_BACKEND = env.str(
    "OIDC_DRF_AUTH_BACKEND",
    default="connect.middleware.WeniOIDCAuthenticationBackend",
)
OIDC_RP_SCOPES = env.str("OIDC_RP_SCOPES", default="openid email")

OIDC_CACHE_TOKEN = env.bool(
    "OIDC_CACHE_TOKEN", default=False
)  # Enable/disable user token caching (default: False).
OIDC_CACHE_TTL = env.int(
    "OIDC_CACHE_TTL", default=600
)  # Time-to-live for cached user tokens (default: 600 seconds).

# Swagger

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "DOC_EXPANSION": "list",
    "APIS_SORTER": "alpha",
    "SECURITY_DEFINITIONS": {
        "OIDC": {"type": "apiKey", "name": "Authorization", "in": "header"}
    },
}

# Celery

REDIS_URL = env.str("CELERY_BROKER_URL", default="redis://localhost:6379/1")

CELERY_RESULT_BACKEND = "django-db"
CELERY_BROKER_URL = REDIS_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"

SYNC_CONTACTS_SCHEDULE = env.str("SYNC_CONTACTS_SCHEDULE")


# Cache

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# AWS

AWS_ACCESS_KEY_ID = env.str("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env.str("AWS_SECRET_ACCESS_KEY")

AWS_STORAGE_BUCKET_NAME = env.str("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env.str("AWS_S3_REGION_NAME")

# cors headers

CORS_ORIGIN_ALLOW_ALL = True

# mail

envvar_EMAIL_HOST = env.str("EMAIL_HOST")

EMAIL_SUBJECT_PREFIX = "[weni] "
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = env.str("SERVER_EMAIL")

if envvar_EMAIL_HOST:
    EMAIL_HOST = envvar_EMAIL_HOST
    EMAIL_PORT = env.int("EMAIL_PORT")
    EMAIL_HOST_USER = env.str("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD")
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SEND_EMAILS = env.bool("SEND_EMAILS")
SENDGRID_UNSUBSCRIBE_GROUP_ID = env.str("SENDGRID_UNSUBSCRIBE_GROUP_ID", default=None)

# Products URL

INTELIGENCE_URL = env.str("INTELIGENCE_URL")
FLOWS_URL = env.str("FLOWS_URL")
INTEGRATIONS_URL = env.str("INTEGRATIONS_URL")
CHATS_URL = env.str("CHATS_URL")

INTEGRATIONS_REST_ENDPOINT = env.str("INTEGRATIONS_REST_ENDPOINT")
INTELLIGENCE_REST_ENDPOINT = env.str("INTELLIGENCE_REST_ENDPOINT")
CHATS_REST_ENDPOINT = env.str("CHATS_REST_ENDPOINT")
INSIGHTS_REST_ENDPOINT = env.str("INSIGHTS_REST_ENDPOINT")

FLOW_GRPC_ENDPOINT = env.str("FLOW_GRPC_ENDPOINT")
INTELIGENCE_GRPC_ENDPOINT = env.str("INTELIGENCE_GRPC_ENDPOINT")
INTEGRATIONS_GRPC_ENDPOINT = env.str("INTEGRATIONS_GRPC_ENDPOINT")

SYNC_ORGANIZATION_INTELIGENCE = env.bool("SYNC_ORGANIZATION_INTELIGENCE")

INTELIGENCE_CERTIFICATE_GRPC_CRT = env.str("INTELIGENCE_CERTIFICATE_GRPC_CRT")
FLOW_CERTIFICATE_GRPC_CRT = env.bool("FLOW_CERTIFICATE_GRPC_CRT")
INTEGRATIONS_CERTIFICATE_GRPC_CRT = env.str("INTEGRATIONS_CERTIFICATE_GRPC_CRT")

# Internal communication
USE_FLOW_REST = env.bool("USE_FLOW_REST")

# Flow Marketing Weni

SEND_REQUEST_FLOW = env.bool("SEND_REQUEST_FLOW")
FLOW_MARKETING_UUID = env.str("FLOW_MARKETING_UUID")
TOKEN_AUTHORIZATION_FLOW_MARKETING = env.str("TOKEN_AUTHORIZATION_FLOW_MARKETING")

VERIFICATION_MARKETING_TOKEN = env.str("VERIFICATION_MARKETING_TOKEN")

# Flow Product Weni
SEND_REQUEST_FLOW_PRODUCT = env.bool("SEND_REQUEST_FLOW_PRODUCT")
FLOW_PRODUCT_UUID = env.str("FLOW_PRODUCT_UUID")
TOKEN_AUTHORIZATION_FLOW_PRODUCT = env.str("TOKEN_AUTHORIZATION_FLOW_PRODUCT")

# Billing
"""
Set gateway payment setting

example:
{
    "stripe": {
        "API_KEY": "",
        "PUBLISHABLE_KEY": "",
    }
}

"""

BILLING_TEST_MODE = env.bool("BILLING_TEST_MODE")
BILLING_SETTINGS = env.json("BILLING_SETTINGS")
BILLING_COST_PER_WHATSAPP = env.float("BILLING_COST_PER_WHATSAPP")

TOKEN_EXTERNAL_AUTHENTICATION = env.str("TOKEN_EXTERNAL_AUTHENTICATION")

VERIFICATION_AMOUNT = env.float("VERIFICATION_AMOUNT")

PLAN_TRIAL_PRICE = env.int("PLAN_TRIAL_PRICE")
PLAN_TRIAL_LIMIT = env.int("PLAN_TRIAL_LIMIT")

PLAN_START_LIMIT = env.int("PLAN_START_LIMIT")
PLAN_START_PRICE = env.int("PLAN_START_PRICE")

PLAN_SCALE_LIMIT = env.int("PLAN_SCALE_LIMIT")
PLAN_SCALE_PRICE = env.int("PLAN_SCALE_PRICE")

PLAN_ADVANCED_LIMIT = env.int("PLAN_ADVANCED_LIMIT")
PLAN_ADVANCED_PRICE = env.int("PLAN_ADVANCED_PRICE")

PLAN_ENTERPRISE_LIMIT = env.str("PLAN_ENTERPRISE_LIMIT")
PLAN_ENTERPRISE_PRICE = env.str("PLAN_ENTERPRISE_PRICE")

DEFAULT_CURRENCY = env.str("DEFAULT_CURRENCY")

# Rocket
ROCKET_CLIENT_ID = env.str("ROCKET_CLIENT_ID")
ROCKET_USERNAME = env.str("ROCKET_USERNAME")
ROCKET_PASSWORD = env.str("ROCKET_PASSWORD")
ROCKET_TEST_MODE = env.bool("ROCKET_TEST_MODE")

# Elastic Search
FLOWS_ELASTIC_URL = env.str("FLOWS_ELASTIC_URL")
ELASTICSEARCH_TIMEOUT_REQUEST = env.int("ELASTICSEARCH_TIMEOUT_REQUEST")

SCROLL_SIZE = env.str("SCROLL_SIZE")
SCROLL_KEEP_ALIVE = env.int("SCROLL_KEEP_ALIVE")

FLOWS_REST_ENDPOINT = env.str("FLOWS_REST_ENDPOINT")


CREATE_AI_ORGANIZATION = env.bool("CREATE_AI_ORGANIZATION")

OMIE_APP_KEY = env.str("OMIE_APP_KEY", default="ap_test")
OMIE_APP_SECRET = env.str("OMIE_APP_SECRET", default="sk_test")

# Event driven architecture settings
USE_EDA = env.bool("USE_EDA", default=False)

if USE_EDA:
    EDA_CONNECTION_BACKEND = (
        "connect.internals.event_driven.connection.pymqp.PyAMQPConnectionBackend"
    )
    EDA_CONSUMERS_HANDLE = "connect.internals.event_driven.handle.handle_consumers"

    EDA_BROKER_HOST = env.str("EDA_BROKER_HOST", default="localhost")
    EDA_BROKER_PORT = env.int("EDA_BROKER_PORT", default=5672)
    EDA_BROKER_USER = env.str("EDA_BROKER_USER", default="guest")
    EDA_BROKER_PASSWORD = env.str("EDA_BROKER_PASSWORD", default="guest")
    EDA_VIRTUAL_HOST = env.str("EDA_VIRTUAL_HOST", default="/")
    EDA_WAIT_TIME_RETRY = env.int("EDA_WAIT_TIME_RETRY", default=5)

NEW_ATTENDANCE_DATE = env.str("NEW_ATTENDANCE_DATE", default="2023-09-30")


ALLOW_CRM_ACCESS = env.bool("ALLOW_CRM_ACCESS", default=True)

if ALLOW_CRM_ACCESS:
    CRM_EMAILS_LIST = env.list("CRM_EMAILS_LIST", default=[])

USE_EDA_PERMISSIONS = env.bool("USE_EDA_PERMISSIONS", default=True)

KC_DB_NAME = env.str("KC_DB_NAME", default="")
KC_DB_USER = env.str("KC_DB_USER", default="")
KC_DB_PASSWORD = env.str("KC_DB_PASSWORD", default="")
KC_DB_HOST = env.str("KC_DB_HOST", default="")
KC_DB_PORT = env.int("KC_DB_PORT", default=0)

DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int("DATA_UPLOAD_MAX_NUMBER_FIELDS", default=10000)

# Rate Limiting
RATE_LIMIT_REQUESTS = env.int("RATE_LIMIT_REQUESTS")
RATE_LIMIT_WINDOW = env.int("RATE_LIMIT_WINDOW")
RATE_LIMIT_BLOCK_TIME = env.int("RATE_LIMIT_BLOCK_TIME")
