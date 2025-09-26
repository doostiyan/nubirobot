from functools import partial

from django_cron import Schedule

from exchange.blockchain.models import CurrenciesNetworkName, Currencies
from ...utils.cron import CronJob, set_cron_code
from ..services import WalletExplorerService

code_fmt = 'get_{}_wallet_balance'

set_code = partial(set_cron_code, code_fmt=code_fmt)


class GetWalletBalanceCron(CronJob):
    code_fmt = 'get_{}_wallet_balance'

    def run(self):
        addresses = []
        if addresses:
            wallet_balances = WalletExplorerService.get_wallet_balance_dtos(
                network=self.network,
                addresses=addresses,
                currency=self.symbol,
            )
            # TODO implement after db is available


@set_code
class GetBitcoinCashWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.BCH
    currency = Currencies.bch
    schedule = Schedule(run_every_mins=10)


@set_code
class GetTronWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.TRX
    currency = Currencies.trx
    schedule = Schedule(run_every_mins=1)


@set_code
class GetBitcoinWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.BTC
    currency = Currencies.btc
    schedule = Schedule(run_every_mins=3)


@set_code
class GetDogecoinWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.DOGE
    currency = Currencies.doge
    schedule = Schedule(run_every_mins=1)


@set_code
class GetLitecoinWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.LTC
    currency = Currencies.ltc
    schedule = Schedule(run_every_mins=2)


@set_code
class GetCardanoWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.ADA
    currency = Currencies.ada
    schedule = Schedule(run_every_mins=2)


@set_code
class GetMoneroWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.XMR
    currency = Currencies.xmr
    schedule = Schedule(run_every_mins=2)


@set_code
class GetAlgorandWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.ALGO
    currency = Currencies.algo
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFlowWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.FLOW
    currency = Currencies.flow
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFilecoinWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.FIL
    currency = Currencies.fil
    schedule = Schedule(run_every_mins=2)


@set_code
class GetArbitrumWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.ARB
    currency = Currencies.arb
    schedule = Schedule(run_every_mins=1)


@set_code
class GetAptosWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.APT
    currency = Currencies.apt
    schedule = Schedule(run_every_mins=1)


@set_code
class GetElrondWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.EGLD
    currency = Currencies.egld
    schedule = Schedule(run_every_mins=3)


@set_code
class GetSolanaWalletBalanceCron(GetWalletBalanceCron):
    network = CurrenciesNetworkName.SOL
    currency = Currencies.sol
    schedule = Schedule(run_every_mins=1)
