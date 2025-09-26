from unittest import TestCase

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.notification.user_service_activation import (
    get_service_activation_help_link_data,
)
from tests.asset_backed_credit.helper import ABCMixins


class GetUserServiceActivationHelpLinkTest(TestCase, ABCMixins):
    def test_with_tara_service(self):
        service = self.create_service(
            provider=Service.PROVIDERS.tara,
            tp=Service.TYPES.credit,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/discover/credit/activating-credit-purchasing/'

    def test_with_digipay_service(self):
        service = self.create_service(
            provider=Service.PROVIDERS.digipay,
            tp=Service.TYPES.credit,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/discover/credit/activating-credit-digipay/'

    def test_with_credit_service(self):
        service = self.create_service(
            provider=Service.PROVIDERS.pnovin,
            tp=Service.TYPES.credit,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/discover/credit/'

    def test_with_loan_service(self):
        service = self.create_service(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/discover/loan/'

    def test_when_service_provider_is_not_found_then_service_type_link_is_returned(self):
        service = self.create_service(
            provider=Service.PROVIDERS.maani,
            tp=Service.TYPES.credit,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/discover/credit/'

    def test_when_service_provider_and_service_type_has_no_link_then_default_help_link_is_returned(self):
        service = self.create_service(
            provider=Service.PROVIDERS.parsian,
            tp=Service.TYPES.debit,
        )

        help_link = get_service_activation_help_link_data(service)

        assert help_link == 'https://nobitex.ir/help/'
