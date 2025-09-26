from django.db.models import Q

from exchange.base.models import ACTIVE_CURRENCIES, RIAL
from exchange.base.money import money_is_close
from exchange.wallet.models import Wallet, ConfirmedWalletDeposit, WithdrawRequest, Transaction


def get_user_diff_for_currency(
    user, currency, deposits=None, bank_deposits=None, withdraws=None,
    transactions=None, balance=None):
    """ Calculate diff for each user
    :param currency: one of ACTIVE_CURRENCIES
    :return: Boolean
    """
    if currency not in ACTIVE_CURRENCIES:
        return None

    # Calculate sum of deposits
    if deposits is None:
        if currency == RIAL:
            deposits = user.shetab_deposits.order_by('-created_at').select_related('transaction')
        else:
            # TODO: Change this to use _wallet column
            deposits = ConfirmedWalletDeposit.objects.filter(
                Q(address__wallet__user=user) | Q(tag__wallet__user=user),
                Q(address__wallet__currency=currency) | Q(tag__wallet__currency=currency),
            ).order_by('-created_at').select_related('transaction', 'transaction__wallet')
    if not bank_deposits and currency == RIAL:
        bank_deposits = user.bank_deposits.order_by('-created_at').select_related('transaction')
    if currency == RIAL:
        c_deposits = sum(d.net_amount for d in deposits if (d.transaction and d.is_valid))
        c_deposits += sum(d.net_amount for d in bank_deposits if (d.transaction and d.confirmed))
    else:
        c_deposits = sum(d.transaction.amount for d in deposits if (d.confirmed and d.transaction and d.validated))

    # Wallet
    user_wallet = Wallet.get_user_wallet(user, currency)

    # Calculate sum of withdraws
    if withdraws is None:
        withdraws = user_wallet.withdraw_requests.order_by('-created_at').select_related('transaction', 'wallet')
    c_withdraws = sum(w.transaction.amount.copy_abs() for w in withdraws if w.transaction)

    # Calculate sum of buys, sells, manual and gateway transactions
    if transactions is None:
        transactions = user_wallet.transactions.order_by('-created_at')
    c_buys = sum(t.amount.copy_abs() for t in transactions if t.tp == t.TYPE.buy)
    c_sells = sum(t.amount.copy_abs() for t in transactions if t.tp == t.TYPE.sell)
    c_manual = sum(t.amount for t in transactions if t.tp == t.TYPE.manual)
    c_gateways = sum(t.amount for t in transactions if t.tp == t.TYPE.gateway)

    # Calculate balance
    if not balance:
        balance = user_wallet.balance
    net = c_deposits - c_withdraws + c_buys - c_sells + c_gateways

    return {
        'currency': currency,
        'deposits': c_deposits,
        'withdraws': c_withdraws,
        'buys': c_buys,
        'sells': c_sells,
        'net': net,
        'balance': balance,
        'diff': balance - net,
        'manual': c_manual,
        'gateways': c_gateways,
    }


def get_user_diff(user, deposits_curr=None, deposits_rls=None, bank_deposits=None, withdraws=None, transactions=None, balance=None):
    return False
    # if deposits_curr is None:
    #     deposits_curr = ConfirmedWalletDeposit.objects.filter(
    #         Q(address__wallet__user=user) | Q(tag__wallet__user=user),
    #     ).order_by('address__wallet__currency', '-created_at').select_related('transaction', 'transaction__wallet')
    #
    # if deposits_rls is None:
    #     deposits_rls = user.shetab_deposits.order_by('-created_at').select_related('transaction')
    #
    # if withdraws is None:
    #     withdraws = WithdrawRequest.objects.filter(
    #         Q(wallet__user=user),
    #     ).order_by('wallet__currency', '-created_at').select_related('transaction', 'wallet')
    #
    # if transactions is None:
    #     transactions = Transaction.objects.filter(
    #         Q(wallet__user=user)
    #     ).order_by('wallet__currency', '-created_at').select_related('wallet', 'wallet__user')
    #
    # deposits_per_curr = {}
    # withdraws_per_curr = {}
    # transactions_per_curr = {}
    #
    # for currency in ACTIVE_CURRENCIES:
    #     deposits_per_curr[currency] = []
    #     withdraws_per_curr[currency] = []
    #     transactions_per_curr[currency] = []
    #
    # for deposit in deposits_curr:
    #     deposits_per_curr.get(deposit.currency).append(deposit)
    #
    # for withdraw in withdraws:
    #     withdraws_per_curr.get(withdraw.currency).append(withdraw)
    #
    # for transaction in transactions:
    #     transactions_per_curr.get(transaction.currency).append(transaction)
    #
    # for currency in ACTIVE_CURRENCIES:
    #     if currency == RIAL:
    #         deposits = deposits_rls or []
    #     else:
    #         deposits = deposits_per_curr.get(currency, [])
    #
    #     withdraws = withdraws_per_curr.get(currency, [])
    #     transactions = transactions_per_curr.get(currency, [])
    #     report = get_user_diff_for_currency(user=user, currency=currency, deposits=deposits, bank_deposits=bank_deposits, withdraws=withdraws,
    #                                         transactions=transactions, balance=balance)
    #     if not report or 'diff' not in report or 'manual' not in report:
    #         print('[Error] Unable to get user report')
    #         return True
    #     if not money_is_close(report['diff'], report['manual']):
    #         print('[Error] User Diff: diff={}, manual={}'.format(report['diff'], report['manual']))
    #         return True
    # return False
