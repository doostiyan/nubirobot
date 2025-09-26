from exchange.base.models import Currencies, NOT_COIN

from exchange.explorer.wallets.models import Address

currencies = [Currencies.cati, Currencies.dogs, Currencies.hmstr, NOT_COIN]
addresses = [
    'EQBFMtW837BdMnXL8lW8kcNjXNSNY7cZRBWBxVQqR1D99S1Q',
    'EQBdWoMOSCFHkfSrU1KQDGJNO_88Xv1jAZaxgBWOt4mZD1Rc',
    'EQCb8B3kz3ylBgFkcEQzue0U_LgtZqj62OQ2b4xQ7crVOXhG',
    'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs',
    'EQDK2JiyAKCTTuQWwgObvz9dfxoyMXKHWzwZ03im9UD3sSze',
]


def reg_addr(address, currency, client='core'):
    addr, created = Address.objects.get_or_create(blockchain_address=address,
                                                  currency=currency,
                                                  owner=client,
                                                  is_registered_highload_address=True)
    return addr, created
