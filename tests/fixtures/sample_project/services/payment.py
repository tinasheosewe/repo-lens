from models import Payment
from services.auth import AuthService


class PaymentService:
    def __init__(self):
        self.auth = AuthService()

    def process_payment(self, user_id: str, amount: float) -> Payment:
        user = self.auth.authenticate(user_id)
        if not self.auth.authorize(user, "payment"):
            raise ValueError("Unauthorized")
        payment = Payment(user_id=user_id, amount=amount)
        self._validate_payment(payment)
        self._execute_payment(payment)
        return payment

    def _validate_payment(self, payment: Payment) -> None:
        if payment.amount <= 0:
            raise ValueError("Invalid amount")

    def _execute_payment(self, payment: Payment) -> None:
        payment.status = "completed"
