from rest_framework import routers

from connect.api.v1.account.views import MyUserProfileViewSet, SearchUserViewSet
from connect.api.v1.dashboard.views import (
    NewsletterViewSet,
    StatusServiceViewSet,
)
from connect.api.v1.invoice.views import InvoiceViewSet
from connect.api.v1.organization.views import (
    OrganizationViewSet,
    OrganizationAuthorizationViewSet,
    RequestPermissionOrganizationViewSet,
)
from connect.api.v1.project.views import ProjectViewSet, RequestPermissionProjectViewSet


class Router(routers.SimpleRouter):  # pragma: no cover
    routes = [
        # Dynamically generated list routes.
        # Generated using @action decorator
        # on methods of the viewset.
        routers.DynamicRoute(
            url=r"^{prefix}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=True,
            initkwargs={},
        ),
        # Dynamically generated detail routes.
        # Generated using @action decorator on methods of the viewset.
        routers.DynamicRoute(
            url=r"^{prefix}/{lookup}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=True,
            initkwargs={},
        ),
    ]

    def get_routes(self, viewset):  # pragma: no cover
        ret = super().get_routes(viewset)
        lookup_field = getattr(viewset, "lookup_field", None)

        if lookup_field:
            # List route.
            ret.append(
                routers.Route(
                    url=r"^{prefix}{trailing_slash}$",
                    mapping={"get": "list", "post": "create"},
                    name="{basename}-list",
                    detail=False,
                    initkwargs={"suffix": "List"},
                )
            )

        detail_url_regex = r"^{prefix}/{lookup}{trailing_slash}$"
        if not lookup_field:
            detail_url_regex = r"^{prefix}{trailing_slash}$"
        # Detail route.
        ret.append(
            routers.Route(
                url=detail_url_regex,
                mapping={
                    "get": "retrieve",
                    "put": "update",
                    "patch": "partial_update",
                    "delete": "destroy",
                },
                name="{basename}-detail",
                detail=True,
                initkwargs={"suffix": "Instance"},
            )
        )

        return ret

    def get_lookup_regex(self, viewset, lookup_prefix=""):  # pragma: no cover
        lookup_fields = getattr(viewset, "lookup_fields", None)
        if lookup_fields:
            base_regex = "(?P<{lookup_prefix}{lookup_url_kwarg}>[^/.]+)"
            return "/".join(
                map(
                    lambda x: base_regex.format(
                        lookup_prefix=lookup_prefix, lookup_url_kwarg=x
                    ),
                    lookup_fields,
                )
            )
        return super().get_lookup_regex(viewset, lookup_prefix)


router = Router()
router.register("dashboard/newsletter", NewsletterViewSet)
router.register("dashboard/status-service", StatusServiceViewSet)
router.register("account/my-profile", MyUserProfileViewSet)
router.register("account/search-user", SearchUserViewSet)
router.register("organization/org", OrganizationViewSet)
router.register("organization/project", ProjectViewSet)
router.register("organization/authorizations", OrganizationAuthorizationViewSet)
router.register("organization/request-permission", RequestPermissionOrganizationViewSet)
router.register("organization/invoice", InvoiceViewSet)
router.register('project/request-permission', RequestPermissionProjectViewSet)
