from functools import partial

from django_cron import Schedule

from exchange.blockchain.models import CurrenciesNetworkName, Currencies
from exchange.base.models import NOT_COIN
from exchange.explorer.utils.logging import get_logger
from ..service.transaction_address_service import TransactionAddressService
from ...networkproviders.services import NetworkService

from ...utils.cron import CronJob, set_cron_code
from ..services import WalletExplorerService

code_fmt = 'get_{}_wallet_txs'

set_code = partial(set_cron_code, code_fmt=code_fmt)


class GetWalletTxsCron(CronJob):
    network = None

    def run(self):
        logger = get_logger()
        network_id = NetworkService.get_network_by_name(network_name=self.network).id
        addresses = TransactionAddressService.get_active_address_list_by_network(network=network_id)
        logger.info('symbol: {}'.format(self.symbol))
        for address in addresses:
            logger.info('address: {}'.format(address))
            wallet_txs = WalletExplorerService.get_wallet_transactions_dto_from_default_provider(
                network=self.network,
                address=address,
                currency=self.symbol,
            )
            logger.info('len transfers: {}'.format(len(wallet_txs)))


@set_code
class GetBitcoinCashWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.BCH
    currency = Currencies.bch
    schedule = Schedule(run_every_mins=10)


@set_code
class GetTronWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.TRX
    currency = Currencies.trx
    schedule = Schedule(run_every_mins=1)


@set_code
class GetBitcoinWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.BTC
    currency = Currencies.btc
    schedule = Schedule(run_every_mins=3)


@set_code
class GetDogecoinWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.DOGE
    currency = Currencies.doge
    schedule = Schedule(run_every_mins=1)


@set_code
class GetLitecoinWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.LTC
    currency = Currencies.ltc
    schedule = Schedule(run_every_mins=2)


@set_code
class GetCardanoWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.ADA
    currency = Currencies.ada
    schedule = Schedule(run_every_mins=2)


@set_code
class GetMoneroWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.XMR
    currency = Currencies.xmr
    schedule = Schedule(run_every_mins=2)


@set_code
class GetAlgorandWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.ALGO
    currency = Currencies.algo
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFlowWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.FLOW
    currency = Currencies.flow
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFilecoinWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.FIL
    currency = Currencies.fil
    schedule = Schedule(run_every_mins=2)


@set_code
class GetArbitrumWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.ARB
    currency = Currencies.arb
    schedule = Schedule(run_every_mins=1)


@set_code
class GetAptosWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.APT
    currency = Currencies.apt
    schedule = Schedule(run_every_mins=1)

@set_code
class GetAvalancheWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.AVAX
    currency = Currencies.avax
    schedule = Schedule(run_every_mins=1)


@set_code
class GetElrondWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.EGLD
    currency = Currencies.egld
    schedule = Schedule(run_every_mins=3)


@set_code
class GetSolanaWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.SOL
    currency = Currencies.sol
    schedule = Schedule(run_every_mins=1)


@set_code
class GetHamsterWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.TON
    currency = Currencies.hmstr
    schedule = Schedule(run_every_mins=1)


@set_code
class GetNotcoinWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.TON
    currency = NOT_COIN
    schedule = Schedule(run_every_mins=1)


@set_code
class GetDogsWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.TON
    currency = Currencies.dogs
    schedule = Schedule(run_every_mins=1)


@set_code
class GetCatizenWalletTxsCron(GetWalletTxsCron):
    network = CurrenciesNetworkName.TON
    currency = Currencies.cati
    schedule = Schedule(run_every_mins=1)