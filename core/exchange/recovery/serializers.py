from decimal import Decimal

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.serializers import register_serializer, serialize
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.segwit_address import eth_to_one_address
from exchange.recovery.models import (
    RecoveryCurrency,
    RecoveryNetwork,
    RecoveryRequest,
    RecoveryTransaction,
    RejectReason,
)
from exchange.wallet.models import Wallet


@register_serializer(model=RecoveryCurrency)
def serialize_recovery_currency(recovery_currency: RecoveryCurrency, opts: dict):
    return {
        'id': recovery_currency.id,
        'name': recovery_currency.name,
        'createdAt': recovery_currency.created_at,
        'contract': '',
    }


@register_serializer(model=RecoveryNetwork)
def serialize_recovery_network(recovery_network: RecoveryNetwork, opts: dict):
    return {
        'id': recovery_network.id,
        'name': recovery_network.name,
        'fee': recovery_network.fee,
        'createdAt': recovery_network.created_at,
    }


@register_serializer(model=RecoveryRequest)
def serialize_recovery_request(recovery_request: RecoveryRequest, opts: dict):
    fee = None
    if recovery_request.status in [
        RecoveryRequest.STATUS.rejected,
        RecoveryRequest.STATUS.unrecoverable,
        RecoveryRequest.STATUS.canceled,
    ]:
        fee = Decimal('0')
    elif recovery_request.status in [
        RecoveryRequest.STATUS.ready,
        RecoveryRequest.STATUS.done,
    ]:
        fee_transaction = recovery_request.recovery_transactions.filter(
            recovery_request=recovery_request,
            tp=RecoveryTransaction.TYPES.user_fee_deduction,
        ).first()
        if fee_transaction:
            fee = fee_transaction.amount
    elif recovery_request.block_order:
        fee = recovery_request.block_order.amount

    currency = recovery_request.currency
    network = recovery_request.network

    return {
        'id': recovery_request.id,
        'updatedAt': recovery_request.updated_at,
        'contract': recovery_request.contract,
        'currency': currency.name if currency else '',
        'network': network.name if network else '',
        'status': recovery_request.get_status_display(),
        'amount': recovery_request.amount,
        'createdAt': recovery_request.created_at,
        'depositAddress': recovery_request.deposit_address,
        'depositTag': recovery_request.deposit_tag,
        'depositHash': recovery_request.deposit_hash,
        'returnAddress': recovery_request.return_address,
        'returnTag': recovery_request.return_tag,
        'recoveryLink': recovery_request.recovery_link,
        'recoveryHash': recovery_request.recovery_hash,
        'fee': fee,
    }


def serialize_wallet_all_addresses(wallet: Wallet) -> dict:
    """
    serialize all(old and new) deposit address with tag, separated with network
    """
    available_networks = []
    deposit_info = {}
    currency_info = CURRENCY_INFO.get(wallet.currency)
    if currency_info:
        for network, network_value in currency_info.get('network_list', {}).items():
            if not network_value.get('deposit_enable', True):
                continue
            if 'contract_addresses' in network_value.keys():
                for contract_address in list(network_value.get('contract_addresses').keys()):
                    available_networks.append(contract_address)
            available_networks.append(network)

    for network in available_networks:
        c_address = None
        network_to_show = network
        if network in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            c_address = network
            network_to_show = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(c_address).get('title')
            network = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(c_address).get('real_network')

        deposit_info[network_to_show] = {
            'addresses': wallet.get_all_deposit_address(network=network, contract_address=c_address, use_cache=False),
        }

        if network == CurrenciesNetworkName.ONE:
            try:
                addresses = deposit_info[network]['addresses']
                deposit_info[network]['addresses'] = [eth_to_one_address(addr) for addr in addresses]
            except Exception:
                deposit_info[network]['addresses'] = None

        deposit_info[network_to_show]['tag'] = wallet.get_all_deposit_tag_numbers(network=network)

    return serialize(
        {
            'depositInfo': deposit_info,
        }
    )

