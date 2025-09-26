import datetime
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.timezone import now
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, DjangoClient

from exchange.accounts.models import BankAccount, User, UserOTP, UserRestriction, UserRestrictionRemoval, UserSms
from exchange.base.api import SemanticAPIError
from exchange.base.models import Currencies, Settings
from exchange.security.models import AddressBook, AddressBookItem, LoginAttempt, WhiteListModeLog
from exchange.wallet.models import Wallet
from tests.base.utils import check_nobitex_response


class AddressBookTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.anonymous_client = DjangoClient()
        self.user.mobile = '09151111111'
        self.user.email = 'user1@example.com'
        self.user_password = 'password'
        self.user.set_password(self.user_password)
        self.user.save()
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.user.notifications.all().delete()

    def test_get_object(self):
        address_books = AddressBook.objects.filter(user=self.user)
        assert not address_books

        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)
        address_books = AddressBook.objects.filter(user=self.user)
        assert address_book == address_books.first()

        with self.assertRaises(IntegrityError):
            AddressBook.objects.create(user=self.user)

    def test_count_whitelist_mode_log_on_create_time(self):
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)
        assert address_book
        whitelist_mode_log_cnt = WhiteListModeLog.objects.filter(address_book=address_book).count()
        assert whitelist_mode_log_cnt == 1

    def test_whitelist_mode_activation(self):
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)
        assert not address_book.whitelist_mode

        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode

        assert not self.user.is_restricted(UserRestriction.RESTRICTION.WithdrawRequestCoin)
        sms = UserSms.objects.filter(user=self.user, tp=UserSms.TYPES.deactivate_whitelist_mode).first()
        assert not sms
        assert not self.user.notifications.exists()

    def test_whitelist_mode_deactivate(self):
        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode

        address_book = AddressBook.deactivate_address_book(self.user)

        assert not address_book.whitelist_mode
        assert self.user.is_restricted(UserRestriction.RESTRICTION.WithdrawRequestCoin)
        restriction = UserRestriction.objects.get(user=self.user,
                                                  restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        restriction_removal = UserRestrictionRemoval.objects.filter(restriction=restriction).first()
        assert restriction_removal
        assert restriction_removal.ends_at > now() + datetime.timedelta(hours=23, minutes=59)

        sms = UserSms.objects.filter(user=self.user, tp=UserSms.TYPES.deactivate_whitelist_mode).first()
        assert sms
        notification = self.user.notifications.last()
        assert notification
        assert notification.message == '۲۴ ساعت محدودیت برداشت به دلیل غیرفعال‌سازی حالت برداشت امن'

    def test_whitelist_mode_check_count(self):
        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode
        address_book = AddressBook.deactivate_address_book(self.user)
        assert not address_book.whitelist_mode
        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode
        whitelist_mode_list = WhiteListModeLog.objects.filter(address_book=address_book).count()
        assert whitelist_mode_list == 3

    def test_add_address_when_address_book_is_not_active(self):
        addresses = AddressBookItem.available_objects.all()
        assert not addresses
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        address = AddressBook.add_address(self.user, 'binance_usdt', 'tx1111111111withdraw222222address',
                                          'mobile_firefox', 'test_network', '192.168.1.1')
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)
        assert not address_book.whitelist_mode
        assert address.address == 'tx1111111111withdraw222222address'
        assert address.title == 'binance_usdt'
        assert not self.user.is_restricted(UserRestriction.RESTRICTION.WithdrawRequestCoin)

        sms = UserSms.objects.filter(user=self.user, tp=UserSms.TYPES.new_address_in_address_book).first()
        assert sms
        notification = self.user.notifications.last()
        assert notification
        assert notification.message == 'یک آدرس به دفتر آدرس شما اضافه شد.'

    def test_add_address_when_address_book_is_active(self):
        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        address = AddressBook.add_address(self.user, 'binance_usdt', 'tx1111111111withdraw222222address',
                                          'mobile_firefox', 'test_network', '192.168.1.1')
        assert address.address == 'tx1111111111withdraw222222address'
        assert address.title == 'binance_usdt'
        assert self.user.is_restricted(UserRestriction.RESTRICTION.WithdrawRequestCoin)
        restriction = UserRestriction.objects.get(user=self.user,
                                                  restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        restriction_removal = UserRestrictionRemoval.objects.filter(restriction=restriction).first()
        assert restriction_removal
        assert restriction_removal.ends_at > now() + datetime.timedelta(minutes=59)

        sms = UserSms.objects.filter(user=self.user, tp=UserSms.TYPES.new_address_in_address_book).first()
        assert sms
        notification = self.user.notifications.last()
        assert notification
        assert notification.message == (
            'یک آدرس به دفتر آدرس شما اضافه شد.\nیک ساعت محدودیت برداشت رمزارز به دلیل فعال بودن حالت برداشت امن'
        )

    def test_add_duplicate_addresses_with_tag(self):
        addresses = AddressBookItem.available_objects.all()
        assert not addresses
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                network='BNB', ip='192.168.121.12', tag='123456')
        # Shouldn't be able to add the same address with the same tag
        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                    network='BNB', ip='192.168.121.12', tag='123456')

        # Should be able to add the same address with a different tag
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                network='BNB', ip='192.168.121.12', tag='234567')
        assert AddressBookItem.available_objects.count() == 2

        # Should be able to add the same address without a tag when the network requires tag
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                network='BNB', ip='192.168.121.12')
        assert AddressBookItem.available_objects.count() == 3

        # Shouldn't be able to add the same address without a tag twice
        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                    network='BNB', ip='192.168.121.12')

    def test_add_duplicate_addresses_on_different_networks(self):
        addresses = AddressBookItem.available_objects.all()
        assert not addresses
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                network='test_network', ip='192.168.121.12')
        AddressBook.add_address(user=self.user, title='test2', address='test2', user_agent='test',
                                network='test_network', ip='192.168.121.12')
        AddressBook.add_address(user=self.user, title='test3', address='test', user_agent='test',
                                network='test_network2', ip='192.168.121.12')

        assert AddressBookItem.available_objects.count() == 3

        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test4', address='test', user_agent='test',
                                    network='test_network', ip='192.168.121.12')

    def test_tags_effect_for_networks_without_tag(self):
        no_tag_network = 'BSC'
        AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                network=no_tag_network, ip='192.168.121.12', tag='should_not_matter')
        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                    network=no_tag_network, ip='192.168.121.12')
        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                    network=no_tag_network, ip='192.168.121.12', tag='another_unimportant_tag')

        address_book = AddressBook.get(self.user)
        assert AddressBookItem.available_objects.filter(address_book=address_book, network=no_tag_network).count() == 1

        address1 = address_book.get_address(address='test_address', network=no_tag_network, tag='')
        address2 = address_book.get_address(address='test_address', network=no_tag_network, tag=None)
        address3 = address_book.get_address(address='test_address', network=no_tag_network, tag='does_not_matter')
        assert address1.id == address2.id
        assert address2.id == address3.id

        AddressBook.activate_address_book(self.user)
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=no_tag_network, tag='') is True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=no_tag_network, tag=None) is True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=no_tag_network, tag='does_not_matter') is True

    def test_tags_effect_for_networks_with_tag(self):
        tag_needing_network = 'EOS'
        AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                network=tag_needing_network, ip='192.168.121.12', tag='')
        with pytest.raises(SemanticAPIError):
            AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                    network=tag_needing_network, ip='192.168.121.12')
        AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                network=tag_needing_network, ip='192.168.121.12', tag='important_tag')

        address_book = AddressBook.get(self.user)
        assert (
            AddressBookItem.available_objects.filter(address_book=address_book, network=tag_needing_network).count()
            == 2
        )

        address1 = address_book.get_address(address='test_address', network=tag_needing_network, tag='')
        address2 = address_book.get_address(address='test_address', network=tag_needing_network, tag=None)
        address3 = address_book.get_address(address='test_address', network=tag_needing_network, tag='non_existent_tag')
        address4 = address_book.get_address(address='test_address', network=tag_needing_network, tag='important_tag')
        assert address1.id == address2.id
        assert address3 is None
        assert address1.id != address4.id

        AddressBook.activate_address_book(self.user)
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=tag_needing_network, tag='') is True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=tag_needing_network, tag=None) is True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=tag_needing_network, tag='important_tag') is True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network=tag_needing_network, tag='non_existent_tag') is False

    def test_delete_address(self):
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        address = AddressBook.add_address(self.user, 'binance_usdt', 'tx1111111111withdraw222222address',
                                          'mobile_firefox', 'test_network', '192.168.1.1')
        assert address
        assert not address.is_removed

        AddressBook.delete_address(self.user, address.id)
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)

        assert not address_book.get_address('tx1111111111withdraw222222address', network='test_network')

        deleted_address = AddressBookItem.all_objects.get(address='tx1111111111withdraw222222address')
        assert deleted_address.is_removed
        assert deleted_address.title == 'binance_usdt'
        assert deleted_address.address == 'tx1111111111withdraw222222address'
        assert deleted_address.address_book == address_book
        assert deleted_address.agent_ip == '192.168.1.1'

    def test_is_address_ok_to_withdraw(self):
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='my_lightning_withdraw_address',
                                                     network='BTCLN') == True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='my_withdraw_address',
                                                     network='some_network') == True

        AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                network='TEST_NETWORK', ip='192.168.121.12')
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='my_withdraw_address',
                                                     network='some_network') == True
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network='TEST_NETWORK') == True

        AddressBook.activate_address_book(self.user)
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='my_withdraw_address',
                                                     network='some_network') == False
        assert AddressBook.is_address_ok_to_withdraw(user=self.user, address='test_address',
                                                     network='TEST_NETWORK') == True

    def test_are_2fa_and_otp_required(self):
        assert AddressBook.are_2fa_and_otp_required(user=self.user, address='some_address', network='some_network',
                                                    is_crypto_currency=False) == True
        assert AddressBook.are_2fa_and_otp_required(user=self.user, address='some_address', network='BTCLN',
                                                    is_crypto_currency=True) == True
        assert AddressBook.are_2fa_and_otp_required(user=self.user, address='some_address', network='some_network',
                                                    is_crypto_currency=True) == True

        AddressBook.add_address(user=self.user, title='test', address='test_address', user_agent='test',
                                network='TEST_NETWORK', ip='192.168.121.12')
        assert AddressBook.are_2fa_and_otp_required(user=self.user, address='some_address', network='some_network',
                                                    is_crypto_currency=True) == True
        assert AddressBook.are_2fa_and_otp_required(user=self.user, address='test_address', network='TEST_NETWORK',
                                                    is_crypto_currency=True) == False

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_deactivate_whitelist_mode_call_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        AddressBook.activate_address_book(self.user)
        AddressBook.deactivate_address_book(self.user)
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_add_address_call_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        shared_params = {'user': self.user, 'user_agent': 'mobile_firefox', 'ip': '192.168.1.1', 'network': 'BNB'}
        AddressBook.add_address(title='binance_usdt', address='tx1111111111withdraw222222address', **shared_params)
        AddressBook.add_address(title='Mom', address='tx1111111111allowance22222address', tag='kid3', **shared_params)
        AddressBook.activate_address_book(self.user)
        AddressBook.add_address(title='Dad', address='tx1111111111payoff22222222address', **shared_params)
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_address_with_tag(self):
        addresses = AddressBookItem.available_objects.all()
        assert not addresses
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        address = AddressBook.add_address(self.user, 'binance_eos', '1111aaaa2222',
                                          'mobile_firefox', 'EOS', '192.168.1.1', 'this_is_a_tag')
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)
        assert not address_book.whitelist_mode
        assert address.address == '1111aaaa2222'
        assert address.title == 'binance_eos'
        assert address.tag == 'this_is_a_tag'


class WithdrawsApiTest(APITestCase):
    fixtures = ['test_data', ]

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '09151111111'
        cls.user.save(update_fields=('user_type', 'mobile'))
        vp = cls.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save(update_fields=('mobile_confirmed',))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.white_address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce'
        self.black_address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4cc'
        self.wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        self.wallet.create_transaction(tp='manual', amount='1000').commit()
        self.rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.rial_wallet.create_transaction(tp='manual', amount='10000000').commit()
        self.bank_account = BankAccount.objects.create(account_number='1', shaba_number='IR27053000000000000000001',
                                                       bank_id=53, user=self.user, owner_name=self.user.get_full_name(),
                                                       confirmed=True, status=0)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        AddressBook.add_address(self.user, 'binance_usdt', self.white_address, 'mobile_firefox',
                                'ETH', '192.168.1.1')

    def _send_withdraw_request(self, wallet, address, amount='100', network=None):
        data = {
            'wallet': wallet.id,
            'amount': amount,
            'address': address,
        }
        if network:
            data.update({'network': network})
        return self.client.post('/users/wallets/withdraw', data)

    def test_withdraw_whitelist_activated(self):
        AddressBook.activate_address_book(self.user)
        response = self._send_withdraw_request(self.wallet, self.black_address)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data
        check_nobitex_response(data, "failed", "NotWhitelistedTargetAddress",
                               "Target address is not whitelisted to withdraw!")

        response = self._send_withdraw_request(self.wallet, self.white_address)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'  # withdraw request accept this target address

    def test_withdraw_required_2fa_or_not(self):
        self.user.requires_2fa = True
        self.user.save()
        response = self._send_withdraw_request(self.wallet, self.black_address)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'failed'
        assert data['code'] == 'Invalid2FA'
        assert data['message'] == 'msgInvalid2FA'

        response = self._send_withdraw_request(self.wallet, self.white_address)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'  # withdraw request accept this target address

    def test_rial_withdraw_whitelist_activated_or_not(self):
        self.user.requires_2fa = True
        self.user.save()
        address_book = AddressBook.activate_address_book(self.user)
        assert address_book.whitelist_mode

        # Rial withdraw - there's no difference whether whitelist mode is enabled or not
        response = self._send_withdraw_request(self.rial_wallet, self.bank_account.id, '1000000', 'FIAT_MONEY')
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'failed'
        assert data['code'] == 'Invalid2FA'
        assert data['message'] == 'msgInvalid2FA'

        # CryptoCurrency withdraw
        response = self._send_withdraw_request(self.wallet, self.white_address)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'  # withdraw request accept this target address

    @patch('exchange.wallet.signals.EmailManager.send_withdraw_request_confirmation_code')
    @patch('exchange.wallet.signals.AddressBook.send_addressbook_withdraw_request_affirmation')
    def test_sending_email_or_sms_after_withdraw_request_creation(self, affirmation_mock, confirmation_mock):
        self._send_withdraw_request(self.wallet, self.black_address)
        confirmation_mock.assert_called_once()
        affirmation_mock.assert_not_called()

        self._send_withdraw_request(self.wallet, self.white_address)
        affirmation_mock.assert_called_once()


class AddressBookAPITest(APITestCase):
    fixtures = ['test_data', 'otp', ]

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user_2 = User.objects.get(pk=204)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.requires_2fa = True
        cls.user.mobile = '09151111111'
        cls.user.save()
        vp = cls.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save(update_fields=('mobile_confirmed', 'email_confirmed'))
        LoginAttempt.objects.create(user=cls.user, ip='31.56.129.161', is_successful=True, is_known=True)
        LoginAttempt.objects.create(user=cls.user_2, ip='31.56.129.161', is_successful=True)

    def setUp(self):
        self.user_otp = UserOTP.objects.get(pk=54)
        self.user_otp.otp_usage = UserOTP.OTP_Usage.address_book
        self.user_otp.otp_type = UserOTP.OTP_TYPES.mobile
        self.user_otp.user = self.user
        self.user_otp.save(update_fields=['otp_usage', 'otp_type', 'user'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.valid_networks = ['BSC', 'bsc', 'bSc']
        self.valid_addresses = [
            '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4cc',
            '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4cd',
            '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce']

    def tearDown(self):
        UserOTP.objects.all().delete()

    def test_list_address_book_successfully(self):
        addr1 = AddressBook.add_address(user=self.user, title='test', address='test', user_agent="test",
                                        network='TEST_NETWORK', ip="192.168.121.12")
        addr2 = AddressBook.add_address(user=self.user, title='test_2', address='test2', user_agent="test",
                                        network='TEST_NETWORK', ip="192.168.121.12")
        data = {'network': 'TEST_NETWORK'}

        url = reverse("address_book_list_create")
        response = self.client.get(url, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert 'data' in response.json()
        results = response.json().get('data')
        assert len(results) == 2
        for i in range(len(results)):
            assert results[i]['network'] == 'TEST_NETWORK'
            title_check = results[i]['title'] == 'test' if i == 0 else results[i]['title'] == 'test_2'
            assert title_check is True
            address_check = results[i]['address'] == 'test' if i == 0 else results[i]['address'] == 'test2'
            assert address_check is True
            assert results[i]['id']
            assert results[i]['createdAt']
        assert sorted([result['id'] for result in results]) == sorted([addr1.id, addr2.id])

    def test_list_address_book_dont_show_other_user_address_book_successfully(self):
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent="test",
                                network='TEST_NETWORK', ip="192.168.121.12")
        AddressBook.add_address(user=self.user, title='test_2', address='test2', user_agent="test",
                                network='TEST_NETWORK', ip="192.168.121.12")
        AddressBook.add_address(user=self.user, title='test_3', address='test3', user_agent="test",
                                network='TEST_NETWORK2', ip="192.168.121.12")

        AddressBook.add_address(user=self.user_2, title='test_3', address='test', user_agent="testt",
                                network='TEST_NETWORK', ip="192.168.121.11")
        AddressBook.add_address(user=self.user_2, title='test_4', address='test2', user_agent="testt",
                                network='TEST_NETWORK', ip="192.168.121.11")
        data = {'network': 'TEST_NETWORK'}

        url = reverse("address_book_list_create")
        response = self.client.get(url, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data')) == 2

    def test_get_all_addresses_versus_addresses_from_one_network(self):
        AddressBook.add_address(user=self.user, title='test', address='test', user_agent='test',
                                network='TEST_NETWORK', ip='192.168.121.12')
        AddressBook.add_address(user=self.user, title='test_2', address='test2', user_agent='test',
                                network='TEST_NETWORK', ip='192.168.121.12')
        AddressBook.add_address(user=self.user, title='test_3', address='test3', user_agent='test',
                                network='TEST_NETWORK2', ip='192.168.121.12')

        url = reverse("address_book_list_create")
        response = self.client.get(url, data={})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data')) == 3

        data = {'network': 'TEST_NETWORK2'}
        response = self.client.get(url, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data')) == 1

    def test_list_address_book_for_pseudo_networks(self):
        defaults = dict(user=self.user, network='ETH', user_agent='Mozilla/5.0', ip='192.168.121.12')
        AddressBook.add_address(title='test_1', address='0xaddress1', **defaults)
        AddressBook.add_address(title='test_2', address='0xaddress2', **defaults)

        url = reverse('address_book_list_create')
        response = self.client.get(url, data={'network': 'WETH-ETH'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data')) == 2

        response = self.client.get(url, data={'network': 'WETH-ARB'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data')) == 0

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_successfully(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse('address_book_list_create')
        data = {'title': 'test', 'address': self.valid_addresses[0], 'otpCode': self.user_otp.code, 'tfaCode': 12345,
                'network': self.valid_networks[0]}

        assert not AddressBook.objects.filter(user=self.user).exists()
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        address_book = AddressBook.objects.filter(user=self.user)
        assert address_book.exists()
        assert address_book.first().addresses.all().exists()

    @patch('exchange.security.validations.UserOTP.verify')
    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_getting_addresses_with_lower_or_upper_case_network(self, totp_mock, otp_verify_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse('address_book_list_create')
        for valid_address, network in zip(self.valid_addresses, self.valid_networks):
            otp_verify_mock.return_value = (self.user_otp, None)
            data = {'title': 'test', 'address': valid_address, 'otpCode': self.user_otp.code, 'tfaCode': 12345,
                    'network': network}
            response = self.client.post(url, data)
            assert response.status_code == status.HTTP_200_OK
            self.user_otp = UserOTP.objects.get(pk=54)

        for network in self.valid_networks:
            data = {'network': network}
            response = self.client.get(url, data=data)
            assert response.status_code == status.HTTP_200_OK
            assert len(response.json().get('data')) == 3

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_with_pseudo_network(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse('address_book_list_create')
        data = {
            'title': 'test',
            'address': '0x912ce59144191c1204e64559fe8253a0e49e6548',
            'otpCode': self.user_otp.code,
            'tfaCode': 12345,
            'network': 'WETH-ARB',
        }

        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        address_items = AddressBookItem.available_objects.select_related('address_book')
        assert len(address_items) == 1
        assert address_items[0].address_book.user_id == self.user.id
        assert address_items[0].address == data['address']
        assert address_items[0].network == 'ARB'

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_inactive_2fa_fail(self, totp_mock):
        self.user.requires_2fa = False
        self.user.save()
        TOTPDevice.objects.create(user=self.user)
        url = reverse("address_book_list_create")
        data = {"title": 'test', "address": 'test', "otpCode": self.user_otp.code, "tfaCode": 12345,
                'network': 'test_network'}
        assert not AddressBook.objects.filter(user=self.user).exists()
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "Inactive2FA", "TFA is not enabled!")

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_parser_error_fail(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("address_book_list_create")
        data = {"title": 'test', "otpCode": self.user_otp.code, "tfaCode": 12345,
                'network': 'test_network'}  # without address
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        check_nobitex_response(response.json(), "failed", "ParseError", "Missing string value")

    def test_create_address_book_invalid_totp_fail(self):
        url = reverse("address_book_list_create")
        data = {"title": 'test', "address": 'test', "otpCode": self.user_otp.code, "tfaCode": 12345,
                'network': 'test_network'}

        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "Invalid2FA", "TFA is not valid!")

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_invalid_otp_fail(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("address_book_list_create")
        data = {"title": 'test', "address": 'test', "otpCode": 1234, "tfaCode": 12345,
                'network': 'test_network'}

        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "InvalidOTP", "OTP is not valid!")

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_invalid_address_fail(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse('address_book_list_create')
        data = {'title': 'test', 'address': 'test', 'otpCode': self.user_otp.code, 'tfaCode': 12345, 'network': 'BSC'}

        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), 'failed', 'InvalidAddress',
                               'The address is not valid for this network!')

    def test_delete_address_book_successfully(self):
        address_book = AddressBook.add_address(user=self.user, title='test', address='test', user_agent="test",
                                               network='test_network', ip="192.168.121.12")
        url = reverse("address_book_delete", kwargs={'pk': address_book.id})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not AddressBookItem.available_objects.filter(id=address_book.id, is_removed=False).exists()

    def test_delete_address_book_for_other_user_fail(self):
        address_book = AddressBook.add_address(user=self.user, title='test', address='test', user_agent="test",
                                               network='test_network', ip="192.168.121.12")
        address_book_user_2 = AddressBook.add_address(user=self.user_2, title='test_3', address='test',
                                                      user_agent="testt", network='test_network', ip="192.168.121.11")

        url = reverse("address_book_delete", kwargs={'pk': address_book_user_2.id})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert AddressBookItem.available_objects.filter(id=address_book_user_2.id).exists()

    def test_activate_whitelist_address_book_successfully(self):
        url = reverse("activate_whitelist")
        response = self.client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert AddressBook.objects.get(user=self.user).whitelist_mode

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_deactivate_whitelist_address_book_successfully(self, totp_mock):
        address_book = AddressBook.get(self.user)
        if not address_book:
            AddressBook.create(user=self.user, whitelist=True)
        TOTPDevice.objects.create(user=self.user)
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        url = reverse("deactivate_whitelist")
        data = {"otpCode": self.user_otp.code, "tfaCode": 1234}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert not AddressBook.objects.get(user=self.user).whitelist_mode

    def test_whitelist_mode_is_true_in_profile(self):
        response = self.client.post('/users/profile')
        assert response.status_code == status.HTTP_200_OK

        profile = response.json()['profile']
        assert not profile['options']['whitelist']

        with self.assertRaises(AddressBook.DoesNotExist):
            AddressBook.objects.get(user=self.user)

        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user, whitelist=True)
        address_book.activate_address_book(self.user)

        response = self.client.post('/users/profile')
        assert response.status_code == status.HTTP_200_OK

        profile = response.json()['profile']
        assert profile['options']['whitelist']
        assert AddressBook.objects.get(user=self.user).whitelist_mode

    def test_whitelist_mode_is_false_in_profile(self):
        response = self.client.post('/users/profile')
        assert response.status_code == status.HTTP_200_OK

        profile = response.json()['profile']
        assert not profile['options']['whitelist']

        with self.assertRaises(AddressBook.DoesNotExist):
            AddressBook.objects.get(user=self.user)

        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user, whitelist=True)
        address_book.deactivate_address_book(self.user)

        response = self.client.post('/users/profile')
        assert response.status_code == status.HTTP_200_OK

        profile = response.json()['profile']
        assert not profile['options']['whitelist']
        assert not AddressBook.objects.get(user=self.user).whitelist_mode

    def test_deactivate_whitelist_address_book_invalid_totp_fail(self):
        url = reverse("deactivate_whitelist")
        data = {"otpCode": self.user_otp.code, "tfaCode": 1234}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "Invalid2FA", "TFA is not valid!")

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_deactivate_whitelist_address_book_invalid_otp_fail(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("deactivate_whitelist")
        data = {"otpCode": 1234, "tfaCode": 1234}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "InvalidOTP", "OTP is not valid!")

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_deactivate_whitelist_address_book_inactive_2fa_fail(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        self.user.requires_2fa = False
        self.user.save()
        url = reverse("deactivate_whitelist")
        data = {"otpCode": self.user_otp.code, "tfaCode": 1234}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        json_response = response.json()
        check_nobitex_response(json_response, 'failed', 'Inactive2FA', 'TFA is not enabled!')

    def test_deactivate_whitelist_address_book_do_transaction_later_invalid_2fa_fail(self):
        url = reverse("deactivate_whitelist")
        data = {"otpCode": self.user_otp.code, "tfaCode": 12345}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "Invalid2FA", "TFA is not valid!")
        self.user_otp.refresh_from_db()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_deactivate_whitelist_address_book_do_transaction_without_error_successfully(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("deactivate_whitelist")
        data = {"otpCode": self.user_otp.code, "tfaCode": "1234"}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        self.user_otp.refresh_from_db()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.used

    def test_create_address_book_do_transaction_later_invalid_2fa_fail(self):
        url = reverse("address_book_list_create")
        data = {"title": 'test', "address": 'test', "otpCode": self.user_otp.code, "tfaCode": 12345,
                'network': 'test_network'}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.address_book
        self.user_otp.save()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        check_nobitex_response(response.json(), "failed", "Invalid2FA", "TFA is not valid!")
        self.user_otp.refresh_from_db()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_do_transaction_without_error_successfully(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("address_book_list_create")
        data = {'title': 'test', 'address': self.valid_addresses[0], 'otpCode': self.user_otp.code, 'tfaCode': '1234',
                'network': self.valid_networks[0]}
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.new
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        self.user_otp.refresh_from_db()
        assert self.user_otp.otp_status == UserOTP.OTP_STATUS.used

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_activate_deactivate_whitelist_address_book_checking_count(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url_activate = reverse("activate_whitelist")
        url_deactivate = reverse("deactivate_whitelist")
        address_book = AddressBook.get(self.user)
        if not address_book:
            address_book = AddressBook.create(user=self.user)

        response = self.client.post(url_activate)
        assert response.status_code == status.HTTP_200_OK
        assert AddressBook.objects.get(user=self.user).whitelist_mode

        data = {"otpCode": self.user_otp.code, "tfaCode": 1234}
        self.user_otp.otp_usage = UserOTP.OTP_Usage.deactivate_whitelist
        self.user_otp.save()
        response = self.client.post(url_deactivate, data)
        assert response.status_code == status.HTTP_200_OK
        assert not AddressBook.objects.get(user=self.user).whitelist_mode

        response = self.client.post(url_activate)
        assert response.status_code == status.HTTP_200_OK
        assert AddressBook.objects.get(user=self.user).whitelist_mode

        whitelist_mode_list = WhiteListModeLog.objects.filter(address_book=address_book).count()
        assert whitelist_mode_list == 4

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_invalid_tag(self, _):
        TOTPDevice.objects.create(user=self.user)
        url = reverse("address_book_list_create")
        data = {'title': 'test', 'address': 'r4H8cFUTSV8tT27DAr8LKfm9ikhvQDxBEA', 'otpCode': self.user_otp.code, 'tfaCode': '1234',
                'network': 'XRP', 'tag': 'bad_tag'}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'InvalidTag'

        data['tag'] = '1178304782bvg24eg2'
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'InvalidTag'

        data['tag'] = '1178'
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

    @patch('django_otp.plugins.otp_totp.models.TOTPDevice.verify_token', return_value=True)
    def test_create_address_book_on_new_device_login(self, totp_mock):
        TOTPDevice.objects.create(user=self.user)
        url = reverse('address_book_list_create')
        data = {
            'title': 'test',
            'address': self.valid_addresses[0],
            'otpCode': self.user_otp.code,
            'tfaCode': 12345,
            'network': self.valid_networks[0],
        }

        LoginAttempt.objects.create(user=self.user, ip='148.253.127.74', is_successful=True, is_known=False)
        # Right away
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        check_nobitex_response(
            response.json(),
            'failed',
            'NewDeviceLoginRestriction',
            'Adding address to address book is restricted for 1 hour after logging in from new device.',
        )
        assert not AddressBook.objects.filter(user=self.user).exists()

        # After one hour
        self.user.login_attempts.filter(is_known=False).update(created_at=timezone.now() - datetime.timedelta(hours=1))
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        address_book = AddressBook.get(self.user)
        assert address_book
        assert address_book.addresses.exists()

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_otp_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        for usage in ('address_book', 'deactivate_whitelist'):
            response = self.client.post('/otp/request', data={'type': 'email', 'usage': usage})
            assert response.status_code == status.HTTP_200_OK
            assert response.json()['status'] == 'ok'

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
