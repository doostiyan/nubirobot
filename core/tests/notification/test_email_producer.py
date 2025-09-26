import decimal
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.emailmanager import EmailManager
from exchange.base.models import Currencies, Settings
from exchange.broker.broker.schema import EmailSchema
from exchange.broker.broker.topics import Topics
from exchange.wallet.models import Wallet, WithdrawRequest


class ProducerEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.user_rls_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.user.user_type = User.USER_TYPES.level2
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        self.user.save()

        self.withdraw_request = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_rls_wallet,
            amount=decimal.Decimal('1400'),
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.accepted,
        )
        Settings.objects.create(key='email_send_withdraw_request_status_update', value='yes')

    @patch('exchange.base.emailmanager.NotificationConfig.is_email_logging_enabled', return_value=True)
    @patch('exchange.base.emailmanager.NotificationConfig.is_email_broker_enabled', return_value=True)
    @patch('exchange.accounts.producer.EventProducer.write_event')
    @patch('post_office.mail.send_many')
    @override_settings(IS_PROD=True)
    def test_send_email(self, mock_email_manager, producer_write_event, *_):
        call_command('update_email_templates')
        EmailManager.send_withdraw_request_status_update(self.withdraw_request)
        email_data = {
            'title': 'برداشت ثبت شد',
            'destination': '-',
            'trackLink': None,
            'trackCode': None,
            'amount': Decimal('1400'),
            'currency': '﷼',
            'amountDisplay': '﷼1,400',
            'tag': None,
            'coinTypeDisplay': 'وجه',
            'is_withdrawal_rial': True,
            'is_prod': True,
            'isTestnet': False,
        }
        email_schema = EmailSchema(
            to='user2@example.com',
            template='withdraw_done',
            context=email_data,
            priority='medium',
            backend='default',
            scheduled_time=None,
        )
        producer_write_event.assert_called_with(Topics.EMAIL.value, email_schema.serialize())
        assert mock_email_manager.call_count == 0

    @patch('exchange.base.emailmanager.NotificationConfig.is_email_logging_enabled', return_value=True)
    @patch('exchange.base.emailmanager.NotificationConfig.is_email_broker_enabled', return_value=False)
    @patch('exchange.accounts.producer.EventProducer.write_event')
    @patch('post_office.mail.send_many')
    @override_settings(IS_PROD=True)
    def test_send_email_when_switch_is_off(self, mock_email_manager, producer_write_event, *_):
        call_command('update_email_templates')
        EmailManager.send_withdraw_request_status_update(self.withdraw_request)
        email_data = {
            'title': 'برداشت ثبت شد',
            'destination': '-',
            'trackLink': None,
            'trackCode': None,
            'amount': Decimal('1400'),
            'currency': '﷼',
            'amountDisplay': '﷼1,400',
            'tag': None,
            'coinTypeDisplay': 'وجه',
            'is_withdrawal_rial': True,
            'is_prod': True,
            'isTestnet': False,
        }
        email_schema = EmailSchema(
            to='user2@example.com',
            template='withdraw_done',
            context=email_data,
            priority='medium',
            backend='default',
            scheduled_time=None,
        )
        producer_write_event.assert_called_with(Topics.EMAIL.value, email_schema.serialize())
        assert mock_email_manager.call_count == 1
