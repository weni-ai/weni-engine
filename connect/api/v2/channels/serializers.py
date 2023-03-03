from rest_framework import serializers


class ReleaseChannelSerializer(serializers.Serializer):
    channel_uuid = serializers.CharField(required=True)
    user = serializers.CharField(required=True)


class CreateChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    data = serializers.JSONField(required=True)
    channeltype_code = serializers.CharField(required=True)


class CreateWACChannelSerializer(serializers.Serializer):
    user = serializers.CharField(required=True)
    project_uuid = serializers.CharField(required=True)
    config = serializers.JSONField(required=True)
    phone_number_id = serializers.CharField(required=True)
