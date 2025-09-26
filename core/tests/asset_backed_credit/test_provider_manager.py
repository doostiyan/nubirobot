from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.asset_backed_credit.exceptions import InvalidIPError, InvalidSignatureError, MissingSignatureError
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.services.providers.provider_manager import ProviderManager
from exchange.base.models import Settings


class ProviderManagerTest(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.provider = SignSupportProvider(
            name='tara',
            ips=['127.0.0.1'],
            pub_key='''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1lxgP1xBHtAS7OvgKIUQ
NmJPN1vBAK6BNKvPWWLpyJV+S/sl4YtDZstNogEBtruiL0a0+FjyiAbC12F7iQEX
khUULHucWKvY+2olvLWeehNcddln+aWmSE+N8Z8ta0Nrw26JtbhKV9XMlkczzRpd
RWKUiSE+sK/XTogscJmpLXcC+Cw6o9Y8bIxtOc2Tq1FKCe/Mr1oInyiA4de4DNgU
hHsGK2SNglxm1GarP4X5TfD+LA8brqY5RL2hD9BDiXepJt9zbcaj3TIraO/JTxmz
7QiFz7+GPg4471tTu88wzUW6gqZ01b+M6bh6TSnx9g4/VNLhZ1rrWr0TNKiAxKO1
yQIDAQAB
-----END PUBLIC KEY-----''',
            id=1,
            account_id=1,
        )
        self._provider_manager_patch = patch.object(
            ProviderManager,
            'providers',
            new=[self.provider],
        )
        self._provider_manager_patch.start()
        self._provider_manager = ProviderManager()
        self.valid_ip = '127.0.0.1'
        self.invalid_ip = '127.0.0.2'
        self.body_data = {'serviceType': 'credit', 'nationalCode': '0921234567'}
        self.valid_signature = '''hxFTZxOeZCqxwC++oT6zHkawNShpi1xU4vCrHm1aWx2u1vpV401r0vyM0UwA7dxjZQwHQb8iSWTy
q114enrHqBmk/POzPLBddObfhSYcrKZ+BPY9ty3lZxjL288SOnNkmbCtAGn+c8eusdlz4bQeXqqH
+4GVtpXJ1j5fl6N/bF1Jz5hg35tvF3FuR0a0SIKasumMvimXzLUQRak3rRPQX6702rgaqNfWbt2B
6tHAqYosTtgN58XzKESsh7MbUoTgT4vbACv+eLaEf1gi1iSHVgOmSMoQZe4fBzvQpk0ndN0ObOKL
iHIFZMB7xsVCcW5jndyN1aiJWJVbtekajcH6wQ=='''

        self.valid_testnet_signature = '0921234567|credit'

    def tearDown(self) -> None:
        patch.stopall()
        cache.clear()

    def test_provider_manager_signature_not_found(self):
        invalid_signature = ''
        with self.assertRaises(MissingSignatureError) as e:
            self._provider_manager.verify_signature(
                signature=invalid_signature, pub_key=self.provider.pub_key, body_data=self.body_data
            )
            assert str(e) == 'x-request-signature parameter is required!'

    def test_provider_manager_provider_not_found(self):
        with self.assertRaises(InvalidIPError):
            self._provider_manager.get_provider_by_ip(self.invalid_ip)

    def test_provider_manager_signature_invalid(self):
        signature = 'test_signature'
        with self.assertRaises(InvalidSignatureError) as e:
            self._provider_manager.verify_signature(
                signature=signature, pub_key=self.provider.pub_key, body_data=self.body_data
            )
            assert str(e) == 'The signature is not valid!'

    def test_provider_manager_success(self):
        signature = self.valid_signature
        self._provider_manager.verify_signature(
            signature=signature, pub_key=self.provider.pub_key, body_data=self.body_data
        )

    @override_settings(IS_TESTNET=True)
    def test_provider_on_testnet(self):
        self._provider_manager.verify_signature(
            signature=self.valid_testnet_signature, pub_key=self.provider.pub_key, body_data=self.body_data
        )

    @override_settings(IS_PROD=True)
    def test_provider_on_prod(self):
        with pytest.raises(InvalidSignatureError):
            self._provider_manager.verify_signature(
                signature=self.valid_testnet_signature, pub_key=self.provider.pub_key, body_data=self.body_data
            )

    @override_settings(IS_TESTNET=True)
    def test_get_provider_by_id(self):
        with patch.object(ProviderManager, 'providers', [self.provider]):
            Settings.set_cached_json('abc_test_net_providers', {1: [self.invalid_ip]})
            provider = ProviderManager.get_provider_by_ip(self.invalid_ip)
            assert provider == self.provider
