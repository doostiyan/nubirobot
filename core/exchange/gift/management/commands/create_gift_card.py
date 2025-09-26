from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from exchange.accounts.models import User, BankAccount
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.crypto import random_string
from exchange.base.models import RIAL, TAG_NEEDED_CURRENCIES
from exchange.base.parsers import parse_currency, parse_money
from exchange.gift.models import GiftCard, CardDesign, GiftPackage
from exchange.wallet.models import Wallet, WithdrawRequest


def create_gift_manually(user, amount, currency, pin, design: str):
    sender_wallet = Wallet.get_user_wallet(user, currency)
    gift_user = User.get_gift_system_user()
    gift_wallet = Wallet.get_user_wallet(gift_user, currency)
    address_params = {}
    bank_account = None
    network = CURRENCY_INFO[currency]['default_network']
    if currency == RIAL:
        try:
            bank_account = BankAccount.objects.get(user=gift_user, confirmed=True, is_deleted=False, is_temporary=False)
        except BankAccount.DoesNotExist:
            if settings.IS_PROD:
                print('No BankAccount defined for system-gift user')
                return
            bank_account = BankAccount.objects.create(
                user=gift_user, account_number='888888771', shaba_number='IR000100000000000888888771',
                owner_name=gift_user.get_full_name(), bank_id=BankAccount.BANK_ID.centralbank,
                bank_name='بانک‌مرکزی', confirmed=True,
            )
        address_params['target_address'] = bank_account.display_name
    elif currency in TAG_NEEDED_CURRENCIES:
        gift_wallet_tag = gift_wallet.get_current_deposit_tag(create=True)
        if isinstance(gift_wallet_tag, int):
            address_params['tag'] = gift_wallet_tag
        else:
            address_params['tag'] = gift_wallet_tag.tag
        gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
        if isinstance(gift_wallet_address, str):
            address_params['target_address'] = gift_wallet_address
        else:
            address_params['target_address'] = gift_wallet_address.address
    else:
        gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
        if isinstance(gift_wallet_address, str):
            address_params['target_address'] = gift_wallet_address
        else:
            address_params['target_address'] = gift_wallet_address.address
    # Create withdraw and gift card
    initial_user_withdraw = WithdrawRequest.objects.create(
        tp=WithdrawRequest.TYPE.internal,
        wallet=sender_wallet,
        amount=amount,
        explanations='بابت صدور کارت هدیه',
        target_account=bank_account,
        network=network,
        **address_params,
    )
    initial_user_withdraw.do_verify()
    gift_package, created = GiftPackage.objects.get_or_create(
            name='test-package',
            price=10_000,
            stock=0,
            weight=10,
            width=10,
            height=10,
            depth=10,
            can_batch_request=True,
        )
    GiftCard.objects.create(
        gift_type=GiftCard.GIFT_TYPES.physical,
        amount=amount,
        sender=user,
        currency=currency,
        package_type=gift_package,
        password=make_password(pin),
        redeem_type=GiftCard.REDEEM_TYPE.lightning if currency == RIAL else GiftCard.REDEEM_TYPE.internal,
        card_design=CardDesign.get_by_title(design),
        redeem_code=random_string(32).upper(),
        initial_withdraw=initial_user_withdraw,
    )


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--currency', required=True)
        parser.add_argument('--amount', required=True)
        parser.add_argument('--username', required=True)
        parser.add_argument('--pin', required=True)
        parser.add_argument('--design', required=True)

    def handle(self, *args, **kwargs):
        currency = parse_currency(kwargs['currency'])
        amount = parse_money(kwargs['amount'])
        user = User.objects.get(username=kwargs['username'])
        design = kwargs['design']
        pin = kwargs['pin']
        create_gift_manually(user, amount, currency, pin, design)
