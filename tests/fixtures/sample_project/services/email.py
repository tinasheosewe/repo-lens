from models import User


def send_welcome_email(user: User) -> None:
    pass


def send_receipt_email(user: User, amount: float) -> None:
    pass


def unused_email_function() -> None:
    """This function is never called anywhere — dead code."""
    pass
