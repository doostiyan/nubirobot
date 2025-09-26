""" Shetab Module Serializers """
from exchange.base.parsers import parse_choices


def parse_bank_swift_name(s, **kwargs):
    """ Parse standard swift name of bank to JibitAccount.BANK_CHOICES
    """
    from .models import JibitAccount
    return parse_choices(JibitAccount.BANK_CHOICES, s, **kwargs)


def parse_jibit_deposit_status(s, **kwargs):
    """ Parse status of a deposit based on JibitDeposit.STATUS
    """
    from .models import JibitDeposit
    return parse_choices(JibitDeposit.STATUS, s, **kwargs)
