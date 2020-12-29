import uuid

from storages.backends.s3boto3 import S3Boto3Storage


class AvatarUserMediaStorage(S3Boto3Storage):
    location = "media/user/avatars/"
    default_acl = "public-read"
    file_overwrite = False
    custom_domain = False

    def get_available_name(self, name, max_length=None):
        ext = name.split(".")[-1]
        filename = "av_%s.%s" % (uuid.uuid4(), ext)
        return super().get_available_name(filename, max_length)
