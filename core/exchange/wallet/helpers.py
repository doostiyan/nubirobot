from decimal import Decimal
from enum import Enum
from typing import Optional

from exchange.accounts.models import BankAccount
from exchange.base.constants import MAX_PRECISION
from exchange.base.models import RIAL
from exchange.base.validators import validate_transaction_is_atomic

from .models import Transaction, Wallet, WithdrawRequest


def refund_shetab_deposit(shetab_deposit):
    if not shetab_deposit.transaction:
        return False
    if shetab_deposit.status_code == shetab_deposit.STATUS.refunded:
        return False
    WithdrawRequest.objects.create(
        wallet=Wallet.get_user_wallet(shetab_deposit.user, RIAL),
        target_address='کارت کاربر',
        target_account=BankAccount.get_generic_system_account(),
        amount=shetab_deposit.transaction.amount,
        status=WithdrawRequest.STATUS.done,
        explanations='عودت وجه واریز شتابی شماره {}'.format(shetab_deposit.pk),
    )
    shetab_deposit.status_code = shetab_deposit.STATUS.refunded
    shetab_deposit.save(update_fields=['status_code'])
    return True


class RefMod(Enum):
    staking_fee = 'StakingFee'
    staking_request = 'StakingRequest'
    staking_reward = 'StakingReward'
    staking_release = 'StakingRelease'
    yield_farming_reward = 'YieldFarmingReward'
    yield_farming_request = 'YieldFarmingRequest'
    yield_farming_release = 'YieldFarmingRelease'
    credit_lend = 'CreditLend'
    credit_system_lend = 'CreditSystemLend'
    credit_repay = 'CreditRepay'
    credit_system_repay = 'CreditSystemRepay'
    convert = 'Convert'
    convert_user_src = 'ExchangeSrc'
    convert_user_dst = 'ExchangeDst'
    convert_system_src = 'ExchangeSystemSrc'
    convert_system_dst = 'ExchangeSystemDst'
    convert_sa_user_src = 'ExchangeSmallAssetSrc'
    convert_sa_user_dst = 'ExchangeSmallAssetDst'
    convert_sa_system_src = 'ExchangeSmallAssetSystemSrc'
    convert_sa_system_dst = 'ExchangeSmallAssetSystemDst'
    cobank_deposit = 'CoBankDeposit'

    def tp(self):
        return {
            RefMod.staking_fee: 'staking',
            RefMod.staking_request: 'staking',
            RefMod.staking_reward: 'staking',
            RefMod.staking_release: 'staking',
            RefMod.yield_farming_request: 'yield_farming',
            RefMod.yield_farming_reward: 'yield_farming',
            RefMod.yield_farming_release: 'yield_farming',
            RefMod.credit_lend: 'credit',
            RefMod.credit_system_lend: 'credit',
            RefMod.credit_repay: 'credit',
            RefMod.credit_system_repay: 'credit',
            RefMod.convert: 'convert',
            RefMod.convert_user_src: 'convert',
            RefMod.convert_user_dst: 'convert',
            RefMod.convert_system_src: 'convert',
            RefMod.convert_system_dst: 'convert',
            RefMod.convert_sa_user_src: 'convert',
            RefMod.convert_sa_user_dst: 'convert',
            RefMod.convert_sa_system_src: 'convert',
            RefMod.convert_sa_system_dst: 'convert',
            RefMod.cobank_deposit: 'deposit',
        }[self]


def create_and_commit_transaction(
    *,
    user_id: int,
    currency: int,
    amount: Decimal,
    ref_module: RefMod,
    description: str,
    ref_id: Optional[int] = None,
    allow_negative_balance=False,
) -> Transaction:
    validate_transaction_is_atomic()
    wallet = Wallet.get_user_wallet(user=user_id, currency=currency)
    if not allow_negative_balance and wallet.active_balance + amount < 0:
        raise ValueError('InsufficientBalance')

    transaction = wallet.create_transaction(
        tp=ref_module.tp(),
        amount=amount,
        description=description,
        allow_negative_balance=allow_negative_balance,
    )

    if transaction is None:
        raise ValueError('InsufficientBalanceOrInactiveWallet')

    ref = Transaction.Ref(ref_module=ref_module.value, ref_id=ref_id) if ref_id else None
    transaction.commit(ref=ref, allow_negative_balance=allow_negative_balance)
    return transaction


def has_balance(user_id: int, currency: int, amount: Decimal) -> bool:
    wallet = Wallet.get_user_wallet(user=user_id, currency=currency)
    amount = amount.quantize(MAX_PRECISION)
    return wallet.balance >= amount


def create_and_commit_system_user_transaction(
    user_id: int,
    currency: int,
    amount: Decimal,
    ref_module: RefMod,
    description: str,
    ref_id: Optional[int] = None,
) -> Transaction:
    '''This function meant to be used in cases where it is allowed
    for system user balance to be negative.
    '''
    assert ref_module in (
        RefMod.convert_system_src,
        RefMod.convert_system_dst,
        RefMod.convert_sa_system_src,
        RefMod.convert_sa_system_dst,
    )
    validate_transaction_is_atomic()
    transaction = Wallet.get_user_wallet(user=user_id, currency=currency).create_transaction(
        tp=ref_module.tp(),
        amount=amount,
        description=description,
        allow_negative_balance=True,
    )
    if transaction is None:
        raise ValueError('InsufficientBalanceOrInactiveWallet')

    ref = Transaction.Ref(ref_module=ref_module.value, ref_id=ref_id) if ref_id else None
    transaction.commit(ref=ref, allow_negative_balance=True)
    return transaction
