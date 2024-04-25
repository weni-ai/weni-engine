from connect.authentication.models import User
from connect.usecases.users.exceptions import UserDoesNotExist


class RetrieveUserUseCase:
    def get_user_by_email(self, email: str) -> User:
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise UserDoesNotExist(f"User with email: {email} Does not exist")

    def get_user_by_id(self, id: int) -> User:
        try:
            return User.objects.get(id=id)
        except User.DoesNotExist:
            raise UserDoesNotExist(f"User with id: {id} Does not exist")
