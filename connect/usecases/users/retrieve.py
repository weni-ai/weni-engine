from connect.authentication.models import User
from connect.usecases.users.exceptions import UserDoesNotExist


class RetrieveUserUseCase:
    def get_user_by_email(self, email: str) -> User:
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise UserDoesNotExist(f"User with email: {email} Does not exist")
