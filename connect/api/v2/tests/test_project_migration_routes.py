from django.test import SimpleTestCase
from django.urls import resolve, reverse

from connect.api.v2.internals.migration.views import (
    ProjectMigrationCreateView,
    ProjectMigrationDetailView,
    ProjectMigrationRepublishView,
    ProjectMigrationStatusView,
)


class ProjectMigrationRoutesTestCase(SimpleTestCase):
    def test_create_route_is_registered(self):
        match = resolve("/v2/internals/connect/project-migrations")
        self.assertEqual(match.func.view_class, ProjectMigrationCreateView)
        self.assertEqual(match.url_name, "internal-project-migration-create")
        self.assertTrue(
            reverse("internal-project-migration-create").endswith(
                "internals/connect/project-migrations"
            )
        )

    def test_detail_route_is_registered(self):
        event_id = "11111111-1111-1111-1111-111111111111"
        match = resolve(f"/v2/internals/connect/project-migrations/{event_id}")
        self.assertEqual(match.func.view_class, ProjectMigrationDetailView)
        self.assertEqual(match.url_name, "internal-project-migration-detail")

    def test_status_route_is_registered(self):
        event_id = "11111111-1111-1111-1111-111111111111"
        match = resolve(
            f"/v2/internals/connect/project-migrations/{event_id}/status"
        )
        self.assertEqual(match.func.view_class, ProjectMigrationStatusView)
        self.assertEqual(match.url_name, "internal-project-migration-status")

    def test_republish_route_is_registered(self):
        event_id = "11111111-1111-1111-1111-111111111111"
        match = resolve(
            f"/v2/internals/connect/project-migrations/{event_id}/republish"
        )
        self.assertEqual(match.func.view_class, ProjectMigrationRepublishView)
        self.assertEqual(match.url_name, "internal-project-migration-republish")
