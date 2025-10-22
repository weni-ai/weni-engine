from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from connect.authentication.models import User
from connect.common.models import Project, Organization


class FeatureFlagsAPIViewTestCase(TestCase):
    """Test cases for the Feature Flags API endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        # Create test organization
        self.organization = Organization.objects.create(
            name="Test Organization",
            description="Test Description",
        )
        
        # Create test project
        self.project = Project.objects.create(
            name="Test Project",
            organization=self.organization,
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_feature_flags_endpoint_requires_authentication(self):
        """Test that the endpoint requires authentication."""
        # Create unauthenticated client
        client = APIClient()
        
        response = client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": str(self.project.uuid)}
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feature_flags_endpoint_requires_project_uuid(self):
        """Test that the endpoint requires project_uuid parameter."""
        response = self.client.get("/api/v2/feature-flags/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_feature_flags_endpoint_validates_project_uuid(self):
        """Test that the endpoint validates project_uuid format."""
        response = self.client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": "invalid-uuid"}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch("connect.api.v2.feature_flags.views.FeatureFlagsService")
    def test_feature_flags_endpoint_returns_features(self, mock_service):
        """Test that the endpoint returns feature flags successfully."""
        # Mock the FeatureFlagsService
        mock_instance = MagicMock()
        mock_instance.get_active_feature_flags_for_attributes.return_value = {
            "new-dashboard": {"enabled": True, "variant": "new"},
            "beta-feature": {"enabled": False},
        }
        mock_service.return_value = mock_instance
        
        # Make request
        response = self.client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": str(self.project.uuid)}
        )
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("features", response.json())
        
        features = response.json()["features"]
        # Features is now a dictionary, not a list
        self.assertIsInstance(features, dict)
        self.assertEqual(len(features), 2)
        
        # Verify feature keys are present
        self.assertIn("new-dashboard", features)
        self.assertIn("beta-feature", features)
        
        # Verify feature values
        self.assertEqual(features["new-dashboard"]["enabled"], True)
        self.assertEqual(features["new-dashboard"]["variant"], "new")
        self.assertEqual(features["beta-feature"]["enabled"], False)
    
    @patch("connect.api.v2.feature_flags.views.FeatureFlagsService")
    def test_feature_flags_endpoint_handles_service_errors(self, mock_service):
        """Test that the endpoint handles service errors gracefully."""
        # Mock service to raise exception
        mock_instance = MagicMock()
        mock_instance.get_active_feature_flags_for_attributes.side_effect = Exception(
            "GrowthBook connection error"
        )
        mock_service.return_value = mock_instance
        
        # Make request
        response = self.client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": str(self.project.uuid)}
        )
        
        # Verify error response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())
    
    def test_feature_flags_endpoint_checks_project_permissions(self):
        """Test that the endpoint checks user permissions for the project."""
        # Create another user without permissions
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123"
        )
        
        # Authenticate as the other user
        client = APIClient()
        client.force_authenticate(user=other_user)
        
        # Try to access the project
        response = client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": str(self.project.uuid)}
        )
        
        # Should fail due to lack of permissions
        # The exact status code depends on ProjectHasPermission implementation
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )
    
    @patch("connect.api.v2.feature_flags.views.FeatureFlagsService")
    def test_feature_flags_passes_correct_attributes(self, mock_service):
        """Test that the endpoint passes correct attributes to the service."""
        # Mock the service
        mock_instance = MagicMock()
        mock_instance.get_active_feature_flags_for_attributes.return_value = {}
        mock_service.return_value = mock_instance
        
        # Make request
        self.client.get(
            "/api/v2/feature-flags/",
            {"project_uuid": str(self.project.uuid)}
        )
        
        # Verify the service was called with correct attributes
        mock_instance.get_active_feature_flags_for_attributes.assert_called_once()
        call_args = mock_instance.get_active_feature_flags_for_attributes.call_args
        attributes = call_args[0][0]
        
        self.assertEqual(attributes["userEmail"], self.user.email)
        self.assertEqual(attributes["projectUUID"], str(self.project.uuid))
