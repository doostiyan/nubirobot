
class WebEngageUserIdDoesNotExist(Exception):
    pass


class DiscountDoesNotExist(Exception):
    pass


class UserRestrictionError(Exception):
    pass


class InactiveUserDiscountExist(Exception):
    pass


class UserDiscountDoesNotExist(Exception):
    pass


class ActiveUserDiscountExist(Exception):
    pass


class CreateNewUserDiscountBudgetLimit(Exception):
    pass


class DiscountTransactionLogDoesNotExist(Exception):
    pass


class NotActiveDiscount(Exception):
    pass
