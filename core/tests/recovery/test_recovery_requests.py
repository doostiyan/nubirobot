from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import BABYDOGE, Currencies, Settings
from exchange.blockchain.segwit_address import eth_to_one_address
from exchange.config.config.data.coins_info import CURRENCY_INFO
from exchange.config.config.derived_data.constant import TESTING_CURRENCIES
from exchange.config.config.models import NOT_COIN
from exchange.market.models import Order
from exchange.recovery.models import (
    RecoveryCurrency,
    RecoveryNetwork,
    RecoveryRejectReasons,
    RecoveryRequest,
    RecoveryTransaction,
    RejectReason,
)
from exchange.usermanagement.models import BlockedOrderLog
from exchange.wallet.models import (
    AvailableDepositAddress,
    ConfirmedWalletDeposit,
    ManualDepositRequest,
    Transaction,
    Wallet,
    WalletDepositAddress,
    WalletDepositTag,
)


class RecoveryRequestTest(APITestCase):

    def setUp(self):
        self.currency1 = RecoveryCurrency.objects.create(
            name='BTC',
        )
        self.network1 = RecoveryNetwork.objects.create(name='BSC', fee=Decimal('100.2'))

        self.currency_test = RecoveryCurrency.objects.create(
            name='test',
        )
        self.network_test = RecoveryNetwork.objects.create(name='TEST', fee=Decimal('120'))
        self.default_recovery_data = {
            'amount': '150.98821',
            'currency': self.currency1.pk,
            'network': self.network1.pk,
            'contract': 'Sample',
            'depositAddress': 'ABCDABCD',
            'depositHash': 'x0hheffgwedd',
            'returnAddress': 'eeefgggqqqq',
        }
        self.user1 = User.objects.get(pk=201)
        block_order = Order.objects.create(
            user=self.user1,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            description='کسر کارمزد بازیابی',
            channel=Order.CHANNEL.system_block,
            order_type=Order.ORDER_TYPES.sell,
            price=Decimal(90_000_000_000_0),
            status=Order.STATUS.active,
            amount=Decimal('120'),
        )
        BlockedOrderLog.add_blocked_order_log(block_order)
        self.recovery_request = RecoveryRequest.objects.create(
            amount=Decimal('1000'),
            user=self.user1,
            currency=self.currency_test,
            network=self.network_test,
            deposit_hash='xhaekkko',
            return_address='AAVRFWEFGrfwefw',
            deposit_address='wefweRRRwfwefw',
            block_order=block_order
            )
        self.available_deposit_address = AvailableDepositAddress.objects.create(
            currency=Currencies.xrp,
            address='0Xheewdddddd',
        )
        self.wallet = Wallet.get_user_wallet(self.user1, Currencies.pmn)
        self.deposit_address = WalletDepositAddress.objects.create(
            wallet=self.wallet,
            address='ABCDABCD',
        )
        Settings.set('recovery_fee', Decimal('1000.2'))
        usdt_wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        usdt_wallet.balance = 5000
        usdt_wallet.save(update_fields={'balance'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

        # add old WalletDepositAddress for ltc
        self.ltc_wallet = Wallet.get_user_wallet(self.user1, Currencies.ltc)
        self.dp_old = WalletDepositAddress.objects.create(
            wallet=self.ltc_wallet,
            address='oldwalletdepositaddress',
            type=5,
            network='BSC',
        )
        self.dp_old.created_at = settings.LAST_ADDRESS_ROTATION_LTC - timedelta(days=10)
        self.dp_old.save()

        # add new ltc WalletDepositAddress
        self.ltc_wallet = Wallet.get_user_wallet(self.user1, Currencies.ltc)
        self.dp_new = WalletDepositAddress.objects.create(
            wallet=self.ltc_wallet,
            address='newwalletdepositaddress',
            type=5,
            network='BSC',
        )

        # add disable ltc WalletDepositAddress
        self.ltc_wallet = Wallet.get_user_wallet(self.user1, Currencies.ltc)
        self.dp_new = WalletDepositAddress.objects.create(
            wallet=self.ltc_wallet, address='disablewalletdepositaddress', type=5, network='BSC', is_disabled=True
        )

        # add multiple AvailableDepositAddress for tag needed currency (ton)
        self.ton_wallet = Wallet.get_user_wallet(self.user1, Currencies.ton)
        self.not_coin = Wallet.get_user_wallet(self.user1, NOT_COIN)
        WalletDepositTag.objects.create(wallet=self.ton_wallet, tag='12', currency=NOT_COIN)
        WalletDepositTag.objects.create(wallet=self.ton_wallet, tag='1234', currency=NOT_COIN)
        WalletDepositTag.objects.create(wallet=self.not_coin, tag='122', currency=NOT_COIN)

        self.available_deposit_address_1 = AvailableDepositAddress.objects.create(
            currency=Currencies.ton, address='tagneededaddress_1'
        )

        self.available_deposit_address_2 = AvailableDepositAddress.objects.create(
            currency=Currencies.ton, address='tagneededaddress_2'
        )

        # add harmony(ONE) for check
        self.eth_address = '0x26bf419ae196a8eca40c0ef257dfe8d77eb52d66'
        self.eth_address_disabled = '0x0b585f8daefbc68a311fbd4cb20d9174ad174016'

        self.one_wallet = Wallet.get_user_wallet(self.user1, Currencies.one)
        self.available_deposit_address_one = WalletDepositAddress.objects.create(
            wallet=self.one_wallet, address=self.eth_address, type=5, network='ONE'
        )

        self.available_deposit_address_one_disable = WalletDepositAddress.objects.create(
            wallet=self.one_wallet, address=self.eth_address_disabled, type=5, network='ONE', is_disabled=True
        )

        # check different type of address (address_type) shown
        WalletDepositAddress.objects.create(
            wallet=Wallet.get_user_wallet(self.user1, Currencies.eth), address='randomethaddress', type=5, network='ETH'
        )

        WalletDepositAddress.objects.create(
            wallet=Wallet.get_user_wallet(self.user1, Currencies.eth), address='randomethaddress', type=2, network='ETH'
        )

        WalletDepositAddress.objects.create(
            wallet=Wallet.get_user_wallet(self.user1, Currencies.eth), address='randomethaddress', type=3, network='ETH'
        )

        # test for checking TESTNET_CURRENCY is in response
        self.last_currency_of_testing = TESTING_CURRENCIES[-1]
        self.name_of_testing_currency = [
            cur
            for cur in Currencies._identifier_map
            if Currencies._identifier_map.get(cur) == self.last_currency_of_testing
        ]
        self.testing_default_network = CURRENCY_INFO[self.last_currency_of_testing]['default_network']

        self.testnet_currency_wallet = Wallet.get_user_wallet(self.user1, self.last_currency_of_testing)
        self.available_deposit_address_one = WalletDepositAddress.objects.create(
            wallet=self.testnet_currency_wallet,
            address='randomaddressfortestnetcurrency',
            type=5,
            network=self.testing_default_network,
        )

        self.babydoge_wallet = Wallet.get_user_wallet(self.user1, BABYDOGE)
        self.available_deposit_address_one = WalletDepositAddress.objects.create(
            wallet=self.babydoge_wallet, address='randomaddressforbabydoge', type=5, network='BSC'
        )
        self.available_deposit_address_babydoge = AvailableDepositAddress.objects.create(
            currency=BABYDOGE, address='randomaddressforbabydoge'
        )

        # check for reject reasons show
        block_order = Order.objects.create(
            user=self.user1,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            description='کسر کارمزد بازیابی',
            channel=Order.CHANNEL.system_block,
            order_type=Order.ORDER_TYPES.sell,
            price=Decimal(90_000_000_000_0),
            status=Order.STATUS.active,
            amount=Decimal('120'),
        )
        BlockedOrderLog.add_blocked_order_log(block_order)
        self.recovery_request_rejected = RecoveryRequest.objects.create(
            amount=Decimal('1000'),
            user=self.user1,
            currency=self.currency_test,
            network=self.network_test,
            deposit_hash='xhaekkko',
            return_address='AAVRFWEFGrfwefw',
            deposit_address='wefweRRRwfwefw',
            block_order=block_order,
            status=RecoveryRequest.STATUS.rejected,
        )

        self.reject_reason_a = RejectReason.objects.create(
            title='Example for RejectReason', description='This is description for Reject'
        )

        self.reject_reason_b = RejectReason.objects.create(
            title='Example for RejectReason b', description='This is description for Reject b'
        )
        self.recovery_reject_reason = RecoveryRejectReasons.objects.create(
            recovery=self.recovery_request_rejected,
            allocated_by=self.user1,
        )
        self.recovery_request_rejected.reject_reason.reasons.add(self.reject_reason_a)
        self.recovery_request_rejected.reject_reason.reasons.add(self.reject_reason_b)
        self.old_android_version = {'User-Agent': 'Android/7.0.2'}
        self.new_version_andriod = {'User-Agent': 'Android/7.2.0'}

    @staticmethod
    def create_transaction(recovery_request, fee, tp=RecoveryTransaction.TYPES.user_fee_deduction):
        usdt_wallet = Wallet.get_user_wallet(recovery_request.user, Currencies.usdt)
        transaction = Transaction.objects.create(
            wallet=usdt_wallet,
            tp=Transaction.TYPE.manual,
            amount=fee,
            description='test recovery transaction',
            ref_module=None,
            ref_id=None,
            created_at=timezone.now(),
            balance=usdt_wallet.balance + fee,
        )
        return RecoveryTransaction.objects.create(
            transaction=transaction,
            recovery_request=recovery_request,
            tp=tp,
            amount=fee
        )

    def request(self, data, headers=None):
        request_data = {'data': data}
        if headers:
            request_data.update({'headers': headers})

        return self.client.post('/recovery/recovery-requests', **request_data)

    def get_recovery_request_result(self, recovery_request_id):
        response = self.client.get(f'/recovery/recovery-requests?recoveryId={recovery_request_id}')
        return response.json()

    def test_recovery_currency_list(self):
        response = self.client.get('/recovery/currencies/list')
        result = response.json()
        assert result['currencies']
        assert result['currencies'][0]['name'] == self.currency_test.name

    def test_recovery_network_list(self):
        response = self.client.get('/recovery/networks/list')
        result = response.json()
        assert result['networks']
        assert result['networks'][0]['name'] == self.network_test.name
        assert result['networks'][0]['fee'] == str(self.network_test.fee)
        assert result['fee'] == str(Decimal('1000.2'))

    def test_recovery_request_list(self):
        response = self.client.get('/recovery/recovery-requests')
        result = response.json()
        assert result['recoveryRequests']
        assert result['recoveryRequests'][0]['amount'] == str(self.recovery_request.amount)
        assert result['recoveryRequests'][0]['currency'] == self.recovery_request.currency.name
        assert result['recoveryRequests'][0]['returnAddress'] == self.recovery_request.return_address
        assert result['recoveryRequests'][0]['depositAddress'] == self.recovery_request.deposit_address

    def test_android_version(self):
        response = self.request(data=self.default_recovery_data, headers=self.old_android_version)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'PleaseUpdateApp'
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_recovery_request_no_email(self):
        self.user1.email = None
        self.user1.save(update_fields=['email'])
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'EmailRequired'
        assert result['message'] == 'User has no email.'

    def test_create_recovery_request_with_invalid_currency(self):
        self.default_recovery_data['currency'] = 'invalid'  # string
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'ParseError'

        self.default_recovery_data['currency'] = list(Currencies._db_values)[-1] + 1  # Invalid currency number
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidCurrency'
        assert result['message'] == 'Invalid currency value.'

    def test_create_recovery_request_with_invalid_deposit_tag(self):
        self.default_recovery_data['depositTag'] = 'تست2'
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidDepositTag'
        assert result['message'] == 'Invalid deposit tag value.'

    def test_create_recovery_request_with_invalid_return_tag(self):
        self.default_recovery_data['returnTag'] = 'test_'
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidReturnTag'
        assert result['message'] == 'Invalid return tag value.'

    def test_create_recovery_request_with_invalid_deposit_address(self):
        self.default_recovery_data['depositAddress'] = 'Cwe13'
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidDepositAddress'
        assert result['message'] == 'Invalid deposit address.'

    def test_create_recovery_request_with_invalid_return_address(self):
        self.default_recovery_data['returnAddress'] = 'Cwe13_سی'
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidReturnAddress'
        assert result['message'] == 'Invalid return Address.'

    def test_create_recovery_request_with_valid_return_address(self):
        self.default_recovery_data['returnAddress'] = r'-_.Cwe13'
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'ok'
        assert result['recoveryRequest']

    def test_create_recovery_request_with_nobitex_return_address(self):
        self.default_recovery_data['returnAddress'] = self.deposit_address.address
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidReturnAddress'
        assert result['message'] == 'Invalid return Address.'

    def test_create_recovery_request_with_duplicated_hash_in_recovery(self):
        self.default_recovery_data['depositHash'] = self.recovery_request.deposit_hash
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'DuplicateDepositHash'
        assert result['message'] == 'Duplicate deposit hash.'

    def test_create_recovery_request_with_duplicated_hash_in_deposits(self):
        ConfirmedWalletDeposit.objects.create(
            tx_hash=self.default_recovery_data['depositHash'],
            _wallet=self.wallet,
            amount=Decimal('1.0'),
            address=self.deposit_address,
        )
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'DuplicateDepositHash'
        assert result['message'] == 'Duplicate deposit hash.'

    def test_create_recovery_request_with_duplicated_hash_in_manual_deposits(self):
        ManualDepositRequest.objects.create(
            tx_hash=self.default_recovery_data['depositHash'],
            wallet=self.wallet,
            amount=Decimal('1.0'),
        )
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'DuplicateDepositHash'
        assert result['message'] == 'Duplicate deposit hash.'

    def test_create_recovery_request_with_insufficient_balance(self):
        wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)
        wallet.balance = 1
        wallet.save(update_fields={'balance'})
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InsufficientBalance'
        assert result['message'] == 'Insufficient balance.'

    def test_create_recovery_request(self):
        response = self.request(data=self.default_recovery_data)
        result = response.json()
        assert result['status'] == 'ok'
        assert result['recoveryRequest']
        recovery_request = RecoveryRequest.objects.get(id=result['recoveryRequest']['id'])
        assert recovery_request.block_order
        assert recovery_request.block_order.amount == Decimal('100.2')
        assert recovery_request.block_order.src_currency == Currencies.usdt
        assert recovery_request.block_order.dst_currency == Currencies.rls
        assert recovery_request.block_order.description == 'کسر کارمزد بازیابی'
        assert recovery_request.block_order.channel == Order.CHANNEL.system_block
        assert recovery_request.block_order.order_type == Order.ORDER_TYPES.sell
        assert recovery_request.block_order.price == Decimal(90_000_000_000_0)
        assert recovery_request.block_order.status == Order.STATUS.active
        # Check blocked_order_log
        block_order_log = BlockedOrderLog.objects.filter(order_id=recovery_request.block_order.id).first()
        assert block_order_log
        assert block_order_log.amount == recovery_request.block_order.amount
        assert block_order_log.src_currency == recovery_request.block_order.src_currency
        assert block_order_log.dst_currency == recovery_request.block_order.dst_currency
        assert block_order_log.status == recovery_request.block_order.status
        assert block_order_log.user == recovery_request.block_order.user
        assert block_order_log.admin_user == recovery_request.block_order.user
        assert block_order_log.order_type == recovery_request.block_order.order_type
        assert result['recoveryRequest']['amount'] == '150.98821'
        assert result['recoveryRequest']['fee'] == str(Decimal('100.2'))
        assert result['recoveryRequest']['currency'] == 'BTC'
        assert result['recoveryRequest']['network'] == 'BSC'
        assert result['recoveryRequest']['contract'] == ''
        assert result['recoveryRequest']['depositAddress'] == 'ABCDABCD'
        assert result['recoveryRequest']['depositHash'] == 'x0hheffgwedd'
        assert result['recoveryRequest']['returnAddress'] == 'eeefgggqqqq'

    def test_create_recovery_request_with_correct_andriod(self):
        response = self.request(data=self.default_recovery_data, headers=self.new_version_andriod)
        result = response.json()
        assert result['status'] == 'ok'
        assert result['recoveryRequest']
        recovery_request = RecoveryRequest.objects.get(id=result['recoveryRequest']['id'])
        assert recovery_request.block_order
        assert recovery_request.block_order.amount == Decimal('100.2')
        assert recovery_request.block_order.src_currency == Currencies.usdt
        assert recovery_request.block_order.dst_currency == Currencies.rls
        assert recovery_request.block_order.description == 'کسر کارمزد بازیابی'
        assert recovery_request.block_order.channel == Order.CHANNEL.system_block
        assert recovery_request.block_order.order_type == Order.ORDER_TYPES.sell
        assert recovery_request.block_order.price == Decimal(90_000_000_000_0)
        assert recovery_request.block_order.status == Order.STATUS.active
        # Check blocked_order_log
        block_order_log = BlockedOrderLog.objects.filter(order_id=recovery_request.block_order.id).first()
        assert block_order_log
        assert block_order_log.amount == recovery_request.block_order.amount
        assert block_order_log.src_currency == recovery_request.block_order.src_currency
        assert block_order_log.dst_currency == recovery_request.block_order.dst_currency
        assert block_order_log.status == recovery_request.block_order.status
        assert block_order_log.user == recovery_request.block_order.user
        assert block_order_log.admin_user == recovery_request.block_order.user
        assert block_order_log.order_type == recovery_request.block_order.order_type
        assert result['recoveryRequest']['amount'] == '150.98821'
        assert result['recoveryRequest']['fee'] == str(Decimal('100.2'))
        assert result['recoveryRequest']['currency'] == 'BTC'
        assert result['recoveryRequest']['network'] == 'BSC'
        assert result['recoveryRequest']['contract'] == ''
        assert result['recoveryRequest']['depositAddress'] == 'ABCDABCD'
        assert result['recoveryRequest']['depositHash'] == 'x0hheffgwedd'
        assert result['recoveryRequest']['returnAddress'] == 'eeefgggqqqq'

    def test_check_recovery_request_hash(self):
        response = self.client.get(f'/recovery/recovery-requests/check-hash?depositHash={self.recovery_request.deposit_hash}')
        result = response.json()
        assert result['exists']

    def test_check_recovery_request_hash_with_special_status(self):
        url = f'/recovery/recovery-requests/check-hash?depositHash={self.recovery_request.deposit_hash}'
        self.recovery_request.status = RecoveryRequest.STATUS.rejected
        self.recovery_request.save(update_fields=['status'])
        response = self.client.get(url).json()
        assert not response['exists']

        self.recovery_request.status = RecoveryRequest.STATUS.canceled
        self.recovery_request.save(update_fields=['status'])
        response = self.client.get(url).json()
        assert not response['exists']

        self.recovery_request.status = RecoveryRequest.STATUS.unrecoverable
        self.recovery_request.save(update_fields=['status'])
        response = self.client.get(url).json()
        assert response['exists']

    def test_reject_recovery_request_with_invalid_status(self):
        self.recovery_request.status = RecoveryRequest.STATUS.ready
        self.recovery_request.save(update_fields=['status'])
        response = self.client.post(f'/recovery/recovery-requests/{self.recovery_request.id}/reject')
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidRecoveryRequest'
        assert result['message'] == 'Invalid Recovery Request.'

    def test_reject_recovery_request(self):
        response = self.client.post(f'/recovery/recovery-requests/{self.recovery_request.id}/reject')
        result = response.json()
        previous_time = self.recovery_request.updated_at
        assert result['status'] == 'ok'
        assert result['recoveryRequest']
        self.recovery_request.refresh_from_db()
        assert self.recovery_request.status == RecoveryRequest.STATUS.canceled
        assert self.recovery_request.block_order.status == Order.STATUS.canceled
        assert self.recovery_request.updated_at != previous_time
        block_order_log = BlockedOrderLog.objects.filter(order_id=self.recovery_request.block_order.id).first()
        assert block_order_log
        assert block_order_log.status == Order.STATUS.canceled

    def test_reject_recovery_request_fee(self):
        result = self.get_recovery_request_result(self.recovery_request.id)
        assert result['recoveryRequests']
        assert result['recoveryRequests'][0]['fee'] == str(self.recovery_request.block_order.amount)

        # Update recovery_request status to 'ready' and create a new transaction with a different fee
        self.recovery_request.status = RecoveryRequest.STATUS.ready
        self.recovery_request.save(update_fields=['status'])
        new_fee = Decimal('2')
        self.create_transaction(recovery_request=self.recovery_request, fee=new_fee)
        self.recovery_request.refresh_from_db()

        # Check the updated fee in the response
        result = self.get_recovery_request_result(self.recovery_request.id)
        assert result['recoveryRequests']
        assert result['recoveryRequests'][0]['fee'] == str(new_fee)

    @staticmethod
    def get_address_from_deposit_info(result, currnecy, network, field='addresses'):
        for deposit in result['wallets']:
            if deposit['currency'] == currnecy:
                return deposit['depositInfo'][network][field]
        return []

    @patch('exchange.recovery.views.is_from_unsupported_app')
    def test_get_all_wallet_deposit_address(self, mock_is_from_unsupported_app):
        mock_is_from_unsupported_app.return_value = True

        response = self.client.get('/recovery/all-deposit-address')
        result = response.json()
        ltc_addresses = self.get_address_from_deposit_info(result, 'ltc', 'BSC')
        not_addresses = self.get_address_from_deposit_info(result, 'not', 'TON')
        one_addresses = self.get_address_from_deposit_info(result, 'one', 'ONE')
        eth_addresses = self.get_address_from_deposit_info(result, 'eth', 'ETH')
        ton_tags = self.get_address_from_deposit_info(result, 'ton', 'TON', 'tag')

        # check for testnet currency not in addresses
        testnet_currency_addresses = self.get_address_from_deposit_info(
            result, self.name_of_testing_currency, self.testing_default_network
        )
        assert testnet_currency_addresses == []

        # check BABYDOGE not exists when flat is True
        babydoge_address = self.get_address_from_deposit_info(result, '1b_babydoge', 'BSC')
        assert babydoge_address == []

        # check for old and disabled are shown

        assert len(ltc_addresses) == 3
        assert 'oldwalletdepositaddress' in ltc_addresses
        assert 'disablewalletdepositaddress' in ltc_addresses

        # check for tag needed currencies to show all
        assert len(not_addresses) == 2

        # check for harmony
        assert len(one_addresses) == 2
        assert eth_to_one_address(self.eth_address) in one_addresses
        assert eth_to_one_address(self.eth_address_disabled) in one_addresses

        # check for multiple of address_type
        assert len(eth_addresses) == 3

        # check for multiple tag
        assert len(ton_tags) == 2
        assert bool(12 in ton_tags) == True
        assert bool(1234 in ton_tags) == True

        response = self.client.get('/users/wallets/list')
        result = response.json()
        ltc_address = self.get_address_from_deposit_info(result, 'ltc', 'BSC', 'address')
        not_address = self.get_address_from_deposit_info(result, 'not', 'TON', 'address')
        one_address = self.get_address_from_deposit_info(result, 'one', 'ONE', 'address')

        assert ltc_address == 'newwalletdepositaddress'
        assert not_address == 'tagneededaddress_2'
        assert one_address == eth_to_one_address(self.eth_address)

    @patch('exchange.base.helpers.is_from_unsupported_app')
    def test_babydoge_exists(self, mock_is_from_unsupported_app):
        mock_is_from_unsupported_app.return_value = False
        response = self.client.get('/recovery/all-deposit-address')
        result = response.json()
        babydoge_address = self.get_address_from_deposit_info(result, '1b_babydoge', 'BSC')
        assert babydoge_address == ['randomaddressforbabydoge']

    def test_get_reject_reason_show(self):
        response = self.client.get(f'/recovery/recovery-requests/{self.recovery_request_rejected.id}/reject-reasons')
        result = response.json()
        reject_reasons = result.get('rejectReasons')

        assert len(reject_reasons) == 2
        assert self.reject_reason_a.description in reject_reasons

        # check recovery_request without reject_reason
        response = self.client.get(f'/recovery/recovery-requests/{self.recovery_request.id}/reject-reasons')
        result = response.json()

        assert result['status'] == 'failed'
        assert result['code'] == 'InvalidRecoveryRequest'
