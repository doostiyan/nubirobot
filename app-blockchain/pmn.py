from decimal import Decimal
from typing import List

from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.pmn.kuknos_horizon import KuknosHorizonAPI
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class PaymonBlockchainInspector(BaseBlockchainInspector):

    get_balance_method = {
        'PMN': 'get_wallets_balance_pmn',
    }

    @classmethod
    def get_wallets_balance(cls, address_list_per_network):
        balances = []
        for network in address_list_per_network:
            address_list = address_list_per_network.get(network)
            balances.extend(getattr(cls, cls.get_balance_method.get(network))(address_list) or [])
        return balances

    @classmethod
    def get_wallets_balance_pmn(cls, address_list: List[str]):
        return cls.get_wallets_balance_horizon(address_list=address_list)

    @classmethod
    def get_wallets_balance_horizon(cls, address_list, raise_error=False):
        balances = []
        api = KuknosHorizonAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.pmn, {}).get('amount', 0)
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions(cls, address, network=None):
        return cls.get_wallet_transactions_horizon(address=address)

    @classmethod
    def get_wallet_transactions_horizon(cls, address, raise_error=False):
        api = KuknosHorizonAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.pmn)
                value = tx_info.get('amount')

                # Process transaction types
                if tx_info.get('direction') == 'outgoing':
                    # Transaction is from this address, so it is a withdraw
                    value = -value

                transactions.append(Transaction(
                    address=address,
                    from_address=[tx_info.get('from_address')],
                    hash=tx_info.get('hash'),
                    timestamp=tx_info.get('date'),
                    value=value,
                    confirmations=int(tx_info.get('confirmations') or 1),
                    is_double_spend=False,  # TODO: check for double spends for PMN
                    details=tx_info,
                    tag=tx_info.get('memo'),
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
            return []
