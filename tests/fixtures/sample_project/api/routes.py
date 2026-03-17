from services.auth import AuthService
from services.payment import PaymentService
from services.email import send_receipt_email


auth_service = AuthService()
payment_service = PaymentService()


def get_user(user_id: str):
    """GET /users/{user_id}"""
    return auth_service.authenticate(user_id)


def create_payment(user_id: str, amount: float):
    """POST /payments"""
    payment = payment_service.process_payment(user_id, amount)
    user = auth_service.authenticate(user_id)
    send_receipt_email(user, amount)
    return payment
