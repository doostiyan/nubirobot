from dataclasses import dataclass
from typing import List, Union

from django.core.cache import cache

from exchange.accounts.models import BankAccount, User
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.models import RIAL
from exchange.wallet.models import Wallet as ExchangeWallet


@dataclass
class Provider:
    """
    Represents a provider with a name, associated IP addresses, and a public key.

    Attributes:
        name (str): The name of the provider.
        ips (List[str]): The list of IP addresses associated with the provider.
        id(int): the number of Service.PROVIDERS
    """

    name: str
    ips: List[str]
    id: int
    account_id: int

    def set_token(self, value: str, timeout: int = 86400) -> None:
        if not self.name:
            raise NotImplementedError()
        cache.set(self.name + '_credit_api_token', value, timeout)

    def get_token(self) -> str:
        if not self.name:
            raise NotImplementedError()
        return cache.get(self.name + '_credit_api_token')

    @property
    def account(self):
        return User.objects.get(pk=self.account_id)

    @property
    def rial_wallet(self) -> Union[Wallet, ExchangeWallet]:
        return WalletService.get_user_wallet(user=self.account, currency=RIAL, wallet_type=Wallet.WalletType.SYSTEM)

    @property
    def bank_account(self) -> BankAccount:
        return BankAccount.objects.filter(
            user=self.account, confirmed=True, is_deleted=False, is_temporary=False
        ).first()


@dataclass
class SignSupportProvider(Provider):
    """
    Represents a provider that supports signing requests with pub_key (RSA)
    """

    pub_key: str


@dataclass
class BasicAuthenticationSupportProvider(Provider):
    """
    Represents a provider that supports basic authentication for requests
    """

    api_username: str
    api_password: str
    username: str
    password: str
