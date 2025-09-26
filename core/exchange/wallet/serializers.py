from django.conf import settings

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import MAX_PRECISION
from exchange.base.id_translation import encode_id
from exchange.base.models import CURRENCY_CODENAMES, Currencies, get_currency_codename
from exchange.base.serializers import register_serializer, serialize, serialize_choices, serialize_currency
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.segwit_address import eth_to_one_address
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import (
    BankDeposit,
    ConfirmedWalletDeposit,
    Transaction,
    Wallet,
    WalletBulkTransferRequest,
    WalletDepositAddress,
    WalletDepositTag,
    WithdrawRequest,
)


def serialize_wallet_addresses(wallet):
    """
        show_multiple_formats: in case of we store address with a specific format in database, but we need to show
        users that address in multiple formats. As I am writing this we have this situation for harmony.
    """
    # Available networks
    deposit_info = {}
    available_networks = []
    default_network = None
    currency_info = CURRENCY_INFO.get(wallet.currency)
    if currency_info:
        default_network = currency_info.get('default_network')
        for network, network_value in currency_info.get('network_list', {}).items():
            if not network_value.get('deposit_enable', True):
                continue
            if 'contract_addresses' in network_value.keys():
                for contract_address in list(network_value.get('contract_addresses').keys()):
                    available_networks.append(contract_address)
            available_networks.append(network)

    # Provide deposit address for each supported network of this currency
    for network in available_networks:
        c_address = None
        network_to_show = network
        if network in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            c_address = network
            network_to_show = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(c_address).get('title')
            network = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(c_address).get('real_network')
        if c_address:
            deposit_info[network_to_show] = {
                'address': wallet.get_current_deposit_address(network=network, contract_address=c_address),
            }
        else:
            deposit_info[network_to_show] = {
                'address': wallet.get_current_deposit_address(network=network),
            }

        if network == CurrenciesNetworkName.ONE:
            try:
                deposit_info[network]['address'] = eth_to_one_address(deposit_info[network]['address'].address)
            except Exception:
                deposit_info[network]['address'] = None

        deposit_info[network_to_show]['tag'] = wallet.get_current_deposit_tag_number(network=network)

    # Provide deposit info for currencies without network and for older clients
    default_deposit = deposit_info.get(default_network)
    if default_deposit:
        deposit_address = default_deposit['address']
        deposit_tag = default_deposit['tag']
    else:
        # No address is available for unknown currencies
        deposit_address = None
        deposit_tag = None

    # TODO: serialize values directly in code above
    return serialize({
        'depositAddress': deposit_address,
        'depositTag': deposit_tag,
        'depositInfo': deposit_info,
    })


@register_serializer(model=Wallet)
def serialize_wallet(wallet, opts=None):
    # Balance and estimates
    balance = wallet.balance
    blocked_balance = wallet.blocked_balance
    if balance < MAX_PRECISION:
        estimate_buy = 0
        estimate_sell = 0
    else:
        price_range = PriceEstimator.get_price_range(wallet.currency)
        estimate_buy = int(price_range[0] * balance)
        estimate_sell = int(price_range[1] * balance)
    obj = {
        'id': wallet.pk,
        'currency': CURRENCY_CODENAMES[wallet.currency].lower(),
        'balance': balance,
        'blockedBalance': blocked_balance,
        'activeBalance': balance - blocked_balance,
        'rialBalance': estimate_buy,
        'rialBalanceSell': estimate_sell,
        'type': serialize_choices(Wallet.WALLET_TYPE, wallet.type),
    }
    # Deposit addresses
    opts = opts or {}
    if wallet.type == Wallet.WALLET_TYPE.spot and not opts.get('no_deposit_addresses'):
        obj.update(serialize_wallet_addresses(wallet))
    return obj


@register_serializer(model=WalletDepositTag)
def serialize_deposit_address_tag(deposit_tag, opts):
    return deposit_tag.tag


@register_serializer(model=WalletDepositAddress)
def serialize_deposit_address(deposit_address, opts):
    return deposit_address.address


@register_serializer(model=ConfirmedWalletDeposit)
def serialize_confirmed_wallet_deposit(deposit, opts):
    return {
        'id': deposit.pk,
        'txHash': deposit.tx_hash,
        'address': deposit.address.address if deposit.address else deposit.tag,
        'confirmed': deposit.confirmed,
        'transaction': deposit.transaction,
        'currency': Currencies[deposit.currency],
        'currencySymbol': get_currency_codename(deposit.currency),
        'blockchainUrl': deposit.get_external_url(),
        'confirmations': deposit.confirmations,
        'requiredConfirmations': deposit.required_confirmations,
        'isConfirmed': deposit.is_confirmed,
        'amount': deposit.amount,
        'depositType': 'coinDeposit',
        'date': deposit.effective_date,
        'invoice': deposit.invoice,
        'expired': deposit.expired,
    }


@register_serializer(model=Transaction)
def serialize_transaction(transaction, opts=None):
    opts = opts or {}
    level = opts.get('level', 1)
    data = {
        'id': encode_id(transaction.pk),
        'amount': transaction.amount,
        'currency': serialize_currency(transaction.currency),
        'description': transaction.description,
        'created_at': transaction.created_at,
        'balance': transaction.balance,
    }
    if level >= 2:
        data['type'] = transaction.get_type_human_display()
        data['calculatedFee'] = None
    return data


@register_serializer(model=WithdrawRequest)
def serialize_withdraw_request(withdraw_request, opts):
    status = withdraw_request.get_status_display() if not withdraw_request.is_accepted else 'Accepted'

    return {
        'id': withdraw_request.pk,
        'createdAt': withdraw_request.created_at,
        'status': status,
        'amount': withdraw_request.amount,
        'currency': serialize_currency(withdraw_request.wallet.currency),
        'address': withdraw_request.target_address,
        'tag': withdraw_request.tag,
        'wallet_id': withdraw_request.wallet_id,
        'blockchain_url': withdraw_request.blockchain_url,
        'is_cancelable': withdraw_request.is_cancelable if settings.WITHDRAW_ENABLE_CANCEL else False,
        'network': withdraw_request.network,
        'invoice': withdraw_request.invoice,
    }


@register_serializer(model=BankDeposit)
def serialize_bank_deposit(bank_deposit, opts):
    return {
        'id': bank_deposit.pk,
        'receiptID': bank_deposit.receipt_id,
        'srcBankAccount': bank_deposit.src_bank_account,
        'dstBankAccount': bank_deposit.dst_bank_account,
        'dst_account': bank_deposit.dst_system_account,
        'amount': bank_deposit.amount,
        'date': bank_deposit.effective_date,
        'created_at': bank_deposit.created_at,
        'deposited_at': bank_deposit.deposited_at,
        'status': bank_deposit.get_status_display(),
        'depositType': 'bankDeposit',
        'transaction': bank_deposit.transaction,
        'confirmed': bank_deposit.confirmed,
    }


@register_serializer(model=WalletBulkTransferRequest)
def serialize_wallet_bulk_transfer(wallet_bulk_transfer: WalletBulkTransferRequest, opts):
    return {
        'id': wallet_bulk_transfer.pk,
        'createdAt': wallet_bulk_transfer.created_at,
        'rejectionReason': wallet_bulk_transfer.rejection_reason,
        'status': serialize_choices(WalletBulkTransferRequest.STATUS, wallet_bulk_transfer.status),
        'srcType': serialize_choices(Wallet.WALLET_TYPE, wallet_bulk_transfer.src_wallet_type),
        'dstType': serialize_choices(Wallet.WALLET_TYPE, wallet_bulk_transfer.dst_wallet_type),
        'transfers': [
            {
                'amount': amount,
                'currency': get_currency_codename(int(currency)),
            }
            for currency, amount in wallet_bulk_transfer.currency_amounts.items()
        ],
    }
