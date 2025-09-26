from functools import partial
from django_cron import Schedule
from exchange.blockchain.models import CurrenciesNetworkName, Currencies
from exchange.explorer.blocks.tasks import run_get_block_txs_cron
from exchange.explorer.utils.cron import CronJob, set_cron_code
from exchange.explorer.utils.logging import get_logger

code_fmt = 'get_{}_block_txs'

set_code = partial(set_cron_code, code_fmt=code_fmt)


class GetBlockTxsCron(CronJob):

    def run(self):
        logger = get_logger()
        logger.info(f'{self.network} block txs cron started!')
        run_get_block_txs_cron(self.network)
        logger.info(f'{self.network} block txs cron finished')


# sorted by alphabet, keep the arrangement please.

@set_code
class GetCardanoBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.ADA
    currency = Currencies.ada
    schedule = Schedule(run_every_mins=2)


@set_code
class GetAlgorandBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.ALGO
    currency = Currencies.algo
    schedule = Schedule(run_every_mins=1)


@set_code
class GetAptosBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.APT
    currency = Currencies.apt
    schedule = Schedule(run_every_mins=1)


@set_code
class GetArbitrumBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.ARB
    currency = Currencies.arb
    schedule = Schedule(run_every_mins=1)


@set_code
class GetAvalancheBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.AVAX
    currency = Currencies.avax
    schedule = Schedule(run_every_mins=1)


@set_code
class GetBaseBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=4)
    currency = Currencies.eth
    network = CurrenciesNetworkName.BASE


@set_code
class GetBitcoinCashBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=4)
    currency = Currencies.bch
    network = CurrenciesNetworkName.BCH


@set_code
class GetBinanceSmartChainBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=1)
    currency = Currencies.bnb
    network = CurrenciesNetworkName.BSC


@set_code
class GetBitcoinBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.BTC
    currency = Currencies.btc
    schedule = Schedule(run_every_mins=3)


@set_code
class GetPolkadotBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.DOT
    currency = Currencies.dot
    schedule = Schedule(run_every_mins=1)


@set_code
class GetDogecoinBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.DOGE
    currency = Currencies.doge
    schedule = Schedule(run_every_mins=1)


@set_code
class GetElrondBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.EGLD
    currency = Currencies.egld
    schedule = Schedule(run_every_mins=1)


@set_code
class GetEnjinBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.ENJ
    currency = Currencies.enj
    schedule = Schedule(run_every_mins=3)


@set_code
class GetEthereumClassicBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=1)
    currency = Currencies.etc
    network = CurrenciesNetworkName.ETC


@set_code
class GetEthereumBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=1)
    currency = Currencies.eth
    network = CurrenciesNetworkName.ETH


@set_code
class GetFilecoinBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.FIL
    currency = Currencies.fil
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFlowBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.FLOW
    currency = Currencies.flow
    schedule = Schedule(run_every_mins=1)


@set_code
class GetFantomBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.FTM
    currency = Currencies.ftm
    schedule = Schedule(run_every_mins=1)


@set_code
class GetLitecoinBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.LTC
    currency = Currencies.ltc
    schedule = Schedule(run_every_mins=2)


@set_code
class GetPolygonBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.MATIC
    currency = Currencies.pol
    schedule = Schedule(run_every_mins=1)


@set_code
class GetNearBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=1)
    currency = Currencies.near
    network = CurrenciesNetworkName.NEAR


@set_code
class GetOneBlockTxsCron(GetBlockTxsCron):
    schedule = Schedule(run_every_mins=1)
    currency = Currencies.one
    network = CurrenciesNetworkName.ONE


@set_code
class GetSolanaBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.SOL
    currency = Currencies.sol
    schedule = Schedule(run_every_mins=1)


@set_code
class GetSonicBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.SONIC
    currency = Currencies.s
    schedule = Schedule(run_every_mins=1)


@set_code
class GetTronBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.TRX
    currency = Currencies.trx
    schedule = Schedule(run_every_mins=1)


@set_code
class GetMoneroBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.XMR
    currency = Currencies.xmr
    schedule = Schedule(run_every_mins=2)


@set_code
class GetTezosBlockTxsCron(GetBlockTxsCron):
    network = CurrenciesNetworkName.XTZ
    currency = Currencies.xtz
    schedule = Schedule(run_every_mins=1)
