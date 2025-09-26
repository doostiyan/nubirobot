from decimal import ROUND_DOWN, Decimal
from functools import partial
from typing import Dict, List, Union

from django.db import transaction

from exchange.accounts.models import Notification, User
from exchange.base.formatting import f_m
from exchange.base.models import XCHANGE_CURRENCIES, Currencies, get_currency_codename
from exchange.base.money import money_is_zero, quantize_number
from exchange.base.strings import _t
from exchange.wallet.helpers import RefMod, create_and_commit_system_user_transaction, create_and_commit_transaction
from exchange.wallet.models import Wallet
from exchange.xchange import exceptions
from exchange.xchange.helpers import get_small_assets_convert_system_user
from exchange.xchange.models import MarketStatus, SmallAssetConvert


class SmallAssetConvertor:
    @classmethod
    def convert(
        cls,
        user: User,
        src_currencies: List[int],
        dst_currency: int,
    ) -> Dict[int, Union[str, exceptions.XchangeError]]:

        if dst_currency not in [Currencies.rls, Currencies.usdt]:
            raise exceptions.InvalidPair("dstCurrency should be 'rls' or 'usdt'")

        results = {}

        valid_src_currencies = []
        for currency in src_currencies:
            if currency in XCHANGE_CURRENCIES:
                valid_src_currencies.append(currency)
            else:
                results[currency] = exceptions.InvalidPair('srcCurrency should be in convert coins')

        if not valid_src_currencies:
            raise exceptions.InvalidPair('srcCurrency should be in convert coins')

        available_markets = {
            market_status.base_currency: market_status
            for market_status in MarketStatus.objects.exclude(status=MarketStatus.STATUS_CHOICES.delisted).filter(
                quote_currency=dst_currency,
                base_currency__in=valid_src_currencies,
            )
        }

        if not available_markets:
            raise exceptions.MarketUnavailable('Market is not available.')

        results.update(
            {
                currency: exceptions.MarketUnavailable('Market is not available.')
                for currency in valid_src_currencies
                if currency not in available_markets
            },
        )

        wallets = {
            wallet.currency: wallet
            for wallet in Wallet.get_user_wallets(user=user, tp=Wallet.WALLET_TYPE.spot)
            .filter(currency__in=available_markets)
            .exclude(balance=Decimal('0'))
        }

        results.update(
            {
                currency: exceptions.FailedAssetTransfer('Wrong wallet or Zero balance.')
                for currency in available_markets
                if currency not in wallets
            },
        )

        for currency, wallet in wallets.items():
            try:
                cls._convert(wallet, available_markets[currency])
                results[currency] = 'success'
            except (exceptions.FailedAssetTransfer, exceptions.PairIsClosed) as e:
                results[currency] = e

        return results

    @classmethod
    @transaction.atomic
    def _convert(cls, wallet: Wallet, market_status: MarketStatus):
        if money_is_zero(wallet.active_balance):
            raise exceptions.FailedAssetTransfer('Wallet has not sufficient active balance.')

        if wallet.active_balance > market_status.min_base_amount:
            raise exceptions.FailedAssetTransfer('Wallet balance is more than convert minimum.')

        quote_amount = wallet.active_balance * market_status.base_to_quote_price_sell
        quote_amount = quantize_number(
            quote_amount,
            precision=market_status.quote_precision.normalize(),
            rounding=ROUND_DOWN,
        )

        convert = SmallAssetConvert.objects.create(
            user=wallet.user,
            src_currency=wallet.currency,
            src_amount=wallet.active_balance,
            dst_currency=market_status.quote_currency,
            dst_amount=quote_amount,
        )

        cls._create_and_commit_wallet_transactions(convert)

        transaction.on_commit(
            partial(cls._send_new_successful_convert_notification, convert=convert),
        )

    @classmethod
    def _create_and_commit_wallet_transactions(cls, convert: SmallAssetConvert):
        giving_currency = _t(get_currency_codename(convert.src_currency))
        receiving_currency = _t(get_currency_codename(convert.dst_currency))

        transactions_description = f'تبدیل {giving_currency} به {receiving_currency}'

        user_src_transaction_amount = -1 * convert.src_amount
        user_dst_transaction_amount = convert.dst_amount
        try:
            convert.src_transaction = create_and_commit_transaction(
                user_id=convert.user_id,
                currency=convert.src_currency,
                amount=user_src_transaction_amount,
                ref_module=RefMod.convert_sa_user_src,
                ref_id=convert.id,
                description=transactions_description,
            )
            convert.dst_transaction = create_and_commit_transaction(
                user_id=convert.user_id,
                currency=convert.dst_currency,
                amount=user_dst_transaction_amount,
                ref_module=RefMod.convert_sa_user_dst,
                ref_id=convert.id,
                description=transactions_description,
            )
        except ValueError as e:
            raise exceptions.FailedAssetTransfer('Insufficient Balance Or Inactive Wallet') from e

        try:
            convert.system_src_transaction = create_and_commit_system_user_transaction(
                user_id=get_small_assets_convert_system_user().id,
                currency=convert.src_currency,
                amount=-user_src_transaction_amount,
                ref_module=RefMod.convert_sa_system_src,
                ref_id=convert.id,
                description=transactions_description,
            )
            convert.system_dst_transaction = create_and_commit_system_user_transaction(
                user_id=get_small_assets_convert_system_user().id,
                currency=convert.dst_currency,
                amount=-user_dst_transaction_amount,
                ref_module=RefMod.convert_sa_system_dst,
                ref_id=convert.id,
                description=transactions_description,
            )
        except ValueError as e:
            raise exceptions.PairIsClosed('This pair is not convertible at the moment.') from e

        convert.save()

    @classmethod
    def _send_new_successful_convert_notification(cls, convert: SmallAssetConvert) -> None:
        Notification.objects.create(
            user=convert.user,
            message=f'معامله انجام شد: فروش {f_m(convert.src_amount, c=convert.src_currency, exact=True)} {_t(get_currency_codename(convert.src_currency))}',
        )
