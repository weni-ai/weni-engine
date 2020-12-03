from rest_framework import serializers

from connect.common.models import DashboardNewsletter


class DashboardNewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardNewsletter
        fields = ["id", "title", "description"]
        ref_name = None
