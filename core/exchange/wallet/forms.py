from django import forms
from model_utils import Choices

from exchange.base.models import BIP39_CURRENCIES, ACTIVE_CRYPTO_CURRENCIES_CHOICES, COLD_CURRENCIES, TRONZ_CURRENCIES, \
    ADDRESS_TYPE_CONTRACT, ALL_CRYPTO_CURRENCIES_CHOICES
from exchange.blockchain.models import CONTRACT_NETWORKS_CHOICES


class CreateWalletBIP39Form(forms.Form):
    currency = forms.ChoiceField(choices=BIP39_CURRENCIES, widget=forms.Select(attrs={'class': 'form-control'}))
    xpub = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'xpub661MyMwAqRbcF35y6H4Yz6uQyh6YKDDunuujuo6xboJjfWYQ3L7QLficCExF27jzfLkxXYWzLt1oWDCpmBPt1unDwD5pD7J9A8kED2pRBSY'
    }), label='Master Public Key')
    number = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Wallet Numbers')
    base_index = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Base Index')
    wallet_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Provided name for wallet in create account'
    }), label='Wallet Name')


class CreateWalletFromColdForm(forms.Form):
    currency = forms.ChoiceField(choices=COLD_CURRENCIES, widget=forms.Select(attrs={'class': 'form-control'}))
    token = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'XKB0OK-wallet_test1.adrs@2f2f8cd3-354d-4cd5-9553-725aee89736f'
    }), label='Token')
    wallet_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Provided name for wallet in create account'
    }), label='Wallet Name')


class CreateWalletForm(forms.Form):
    currency = forms.ChoiceField(choices=ACTIVE_CRYPTO_CURRENCIES_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    addresses = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control',
        'placeholder': 'Seperate with comma. e.g.: Address1,Address2'
    }), label='Addresses')
    wallet_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Provided name for wallet in create account'
    }), label='Wallet Name')


class UpdateDepositForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    currency = forms.ChoiceField(choices=ACTIVE_CRYPTO_CURRENCIES_CHOICES,
                                 widget=forms.Select(attrs={'class': 'form-control'}))


class FreezeUnfreezeWalletForm(forms.Form):
    RESOURCES = Choices(
        ('ENERGY', 'ENERGY'),
        ('BANDWIDTH', 'BANDWIDTH'),
    )
    resource = forms.ChoiceField(choices=RESOURCES, widget=forms.Select(attrs={'class': 'form-control'}))
    receiver_account = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': "[Optional] Don't fill when you want to freeze hot wallet for itself."
    }), empty_value=None, required=False, label='Receiver Account')


class FreezeTronWalletForm(FreezeUnfreezeWalletForm):
    amount = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Amount to Freeze')


class UnfreezeTronWalletForm(FreezeUnfreezeWalletForm):
    pass


class MintTronZWalletForm(forms.Form):
    currency = forms.ChoiceField(choices=TRONZ_CURRENCIES,
                                 widget=forms.Select(attrs={'class': 'form-control'}))
    amount = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Amount to mint')


class BalanceTronZWalletForm(forms.Form):
    currency = forms.ChoiceField(choices=TRONZ_CURRENCIES,
                                 widget=forms.Select(attrs={'class': 'form-control'}))


class ExtractContractAddressesForm(forms.Form):
    NULLABLE_ALL_CRYPTO_CURRENCIES_CHOICES = Choices(('', '----')) + ALL_CRYPTO_CURRENCIES_CHOICES
    network = forms.ChoiceField(choices=CONTRACT_NETWORKS_CHOICES,
                                widget=forms.Select(attrs={'class': 'form-control'}))

    currency = forms.ChoiceField(choices=NULLABLE_ALL_CRYPTO_CURRENCIES_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}), required=False)

    gas_price = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '[Optional] Gas price(gwei)'}), required=False)

    threshold = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '[Optional] Threshold. Default 100$'}), required=False)

    address_type = forms.ChoiceField(choices=ADDRESS_TYPE_CONTRACT,
                                     widget=forms.Select(attrs={'class': 'form-control'}))
