import datetime
from functools import partial

import pytz
from django_cron import Schedule
from django.db import transaction

from exchange.blockchain.models import CurrenciesNetworkName, Currencies
from exchange.explorer.blocks.utils.metrics import min_available_block_height
from exchange.explorer.networkproviders.models import Network, Operation
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.utils.cron import CronJob, set_cron_code
from exchange.explorer.utils.blockchain import high_transaction_networks
from exchange.explorer.blocks.models import GetBlockStats
from exchange.blockchain.explorer import BlockchainExplorer


code_fmt = 'delete_{}_block_txs'

set_code = partial(set_cron_code, code_fmt=code_fmt)


class DeleteBlockTxsCron(CronJob):

    def run(self):
        with transaction.atomic():
            network = Network.objects.get(name=self.network)
            if network.name in high_transaction_networks:
                days = 0.5
            elif network.name in BlockchainExplorer.WALLET_TXS_TESTED_NETWORKS:
                days = 5
            else:
                days = 2

            hours = days * 24
            delete_before_datetime = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(hours=hours)
            transfers_to_delete = (
                Transfer.objects
                .for_network(network.name)
                .filter(network_id=network.id)
                .filter(source_operation=Operation.BLOCK_TXS)
                .filter(created_at__lt=delete_before_datetime)
            )

            # Get the minimum block height in one query without loading the entire queryset
            min_available_block_queryset = (
                transfers_to_delete
                .filter(block_height__isnull=False)
                .values_list('block_height', flat=True)
            )

            min_available_block = min(min_available_block_queryset) if min_available_block_queryset else None


            # Add 1 to min_available_block if a result is found
            if min_available_block is not None:
                min_available_block += 1

                with transaction.atomic():
                    transfers_to_delete.delete()
                    GetBlockStats.objects.filter(network_id=network.id).update(min_available_block=min_available_block)

                provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
                    network.name,
                    Operation.BLOCK_TXS
                ).provider.name
                min_available_block_height.labels(network=network.name, provider=provider).set(min_available_block)


# sorted by alphabet, keep the arrangement please.
@set_code
class DeleteCardanoBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ADA
    currency = Currencies.ada
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteAlgorandBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ALGO
    currency = Currencies.algo
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteAptosBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.APT
    currency = Currencies.apt
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteArbitrumBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ARB
    currency = Currencies.arb
    schedule = Schedule(run_every_mins=29)


@set_code
class DeleteAvalancheBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.AVAX
    currency = Currencies.avax
    schedule = Schedule(run_every_mins=55)


class DeleteBaseBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.BASE
    currency = Currencies.eth
    schedule = Schedule(run_every_mins=55)


class DeleteBitcoinCashBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.BCH
    currency = Currencies.bch
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteBinanceSmartChainBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.BSC
    currency = Currencies.bnb
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteBitcoinBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.BTC
    currency = Currencies.btc
    schedule = Schedule(run_every_mins=14)


@set_code
class DeleteDogecoinBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.DOGE
    currency = Currencies.doge
    schedule = Schedule(run_every_mins=55)


@set_code
class DeletePolkadotBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.DOT
    currency = Currencies.dot
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteElrondBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.EGLD
    currency = Currencies.egld
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteEnjinBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ENJ
    currency = Currencies.enj
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteEthereumClassicBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ETC
    currency = Currencies.etc
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteEthereumBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ETH
    currency = Currencies.eth
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteFilecoinBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.FIL
    currency = Currencies.fil
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteFlowBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.FLOW
    currency = Currencies.flow
    schedule = Schedule(run_every_mins=29)


@set_code
class DeleteFantomBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.FTM
    currency = Currencies.ftm
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteLitecoinBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.LTC
    currency = Currencies.ltc
    schedule = Schedule(run_every_mins=55)


@set_code
class DeletePolygonBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.MATIC
    currency = Currencies.pol
    schedule = Schedule(run_every_mins=14)


@set_code
class DeleteNearBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.NEAR
    currency = Currencies.near
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteOneBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.ONE
    currency = Currencies.one
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteSolanaBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.SOL
    currency = Currencies.sol
    schedule = Schedule(run_every_mins=4)


@set_code
class DeleteSonicBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.SONIC
    currency = Currencies.s
    schedule = Schedule(run_every_mins=1)


@set_code
class DeleteTronBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.TRX
    currency = Currencies.trx
    schedule = Schedule(run_every_mins=9)


@set_code
class DeleteMoneroBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.XMR
    currency = Currencies.xmr
    schedule = Schedule(run_every_mins=55)


@set_code
class DeleteTezosBlockTxsCron(DeleteBlockTxsCron):
    network = CurrenciesNetworkName.XTZ
    currency = Currencies.xtz
    schedule = Schedule(run_every_mins=55)
