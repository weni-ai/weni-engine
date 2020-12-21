from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


def create_user_and_token(nickname="fake"):
    user = User.objects.create_user("{}@user.com".format(nickname), nickname)
    token, create = Token.objects.get_or_create(user=user)
    return (user, token)
