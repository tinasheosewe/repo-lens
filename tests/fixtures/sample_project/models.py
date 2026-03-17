class User:
    def __init__(self, id: str, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email


class Payment:
    def __init__(self, user_id: str, amount: float, status: str = "pending"):
        self.user_id = user_id
        self.amount = amount
        self.status = status


class PremiumUser(User):
    def __init__(self, id: str, name: str, email: str, tier: str = "gold"):
        super().__init__(id, name, email)
        self.tier = tier
