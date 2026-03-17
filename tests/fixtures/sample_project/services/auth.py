from models import User


class AuthService:
    def authenticate(self, user_id: str) -> User:
        return User(id=user_id, name="Test User", email="test@example.com")

    def authorize(self, user: User, permission: str) -> bool:
        return True

    def revoke_token(self, token: str) -> None:
        pass
