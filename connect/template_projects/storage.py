import uuid

from storages.backends.s3boto3 import S3Boto3Storage


class TemplateTypeImageStorage(S3Boto3Storage):
    location = "media/template/image/"
    default_acl = "public-read"
    file_overwrite = False
    custom_domain = False
    override_available_name = True

    def get_available_name(self, name, max_length=None):
        print(name)
        if self.override_available_name:
            ext = name.split(".")[-1]
            filename = "av_%s.%s" % (uuid.uuid4(), ext)
            return super().get_available_name(filename, max_length)
        return super().get_available_name(name, max_length)
