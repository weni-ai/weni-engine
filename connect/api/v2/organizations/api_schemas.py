from drf_yasg2 import openapi


authorizations_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "user_email": openapi.Schema(
            description="User email",
            type=openapi.TYPE_STRING,
        ),
        "role": openapi.Schema(
            description="Authorization role",
            type=openapi.TYPE_INTEGER,
        ),
    },
)


create_organization_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "name": openapi.Schema(
            description="Organization name",
            type=openapi.TYPE_STRING,
        ),
        "description": openapi.Schema(
            description="Organization description",
            type=openapi.TYPE_STRING,
        ),
        "plan": openapi.Schema(
            description="Organization description",
            type=openapi.TYPE_STRING,
        ),
        "customer": openapi.Schema(
            description="Stripe customer",
            type=openapi.TYPE_STRING,
        ),
        "authorizations": openapi.Schema(
            description="Array of authorizations",
            type=openapi.TYPE_ARRAY,
            items=authorizations_schema,
        ),
    },
)
