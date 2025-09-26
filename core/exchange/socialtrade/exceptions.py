from exchange.features.models import QueueItem


class SocialTradeException(Exception):
    pass


class LeaderAlreadyExist(SocialTradeException):
    pass


class PendingLeadershipRequestExist(SocialTradeException):
    pass


class AcceptNotNewLeaderRequest(SocialTradeException):
    pass


class RejectNotNewLeaderRequest(SocialTradeException):
    pass


class InsufficientBalance(SocialTradeException):
    pass


class SelfSubscriptionImpossible(SocialTradeException):
    pass


class AlreadySubscribedException(SocialTradeException):
    pass


class LeaderNotFound(SocialTradeException):
    pass


class ReachedSubscriptionLimit(SocialTradeException):
    pass


class SubscriptionNotRenewable(SocialTradeException):
    pass


class SubscriptionFeeIsLessThanTheMinimum(SocialTradeException):
    pass


class SubscriptionFeeIsMoreThanTheMaximum(SocialTradeException):
    pass


class SubscriptionIsNotAllowed(SocialTradeException):
    pass
