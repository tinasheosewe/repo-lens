from services.auth import AuthService
from services.payment import PaymentService


def main():
    auth = AuthService()
    payment = PaymentService()
    user = auth.authenticate("user_123")
    payment.process_payment(user.id, 100.0)


if __name__ == "__main__":
    main()
