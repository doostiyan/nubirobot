from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache
from django_cron import CronJobBase, Schedule

from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.apis_conf import APIS_CLASSES, APIS_CONF
from exchange.blockchain.metrics import (latest_block_height_mined, latest_block_height_processed,
                                         block_height_difference)
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService, NetworkService
from exchange.explorer.networkproviders.services.auto_switch_provider import AutoSwitchProviderService

BLOCK_TXS_AUTO_SWITCH_NETWORKS = []


class UpdateBlockHeadDiffCron(CronJobBase):
    RUN_EVERY_MINS = 60
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = None
    network = None

    def do(self):
        network = self.network
        api_names = APIS_CONF[network]['block_head_apis']

        with ThreadPoolExecutor(max_workers=len(api_names)) as executor:
            results = list(executor.map(lambda api_name: self.get_block_head(api_name), api_names))

        # Filter out None values
        results = [r for r in results if r]
        if not results:
            return
        max_block_head = max(results)

        provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network,
            Operation.BLOCK_TXS
        ).provider.name

        # set metrics
        latest_block_height_mined.labels(network=network, provider=provider).set(max_block_head)
        latest_processed_block = (
            cache.get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{network.lower()}'))
        latest_block_height_processed.labels(network=network, provider=provider).set(latest_processed_block)
        block_height_difference.labels(network=network, provider=provider).set(max_block_head - latest_processed_block)

        # Check provider's health status
        if network in BLOCK_TXS_AUTO_SWITCH_NETWORKS:
            block_diff_limit = NetworkService.get_number_of_blocks_given_time(network_name=network, time_s=15 * 60)  # 15 min
            if max_block_head - latest_processed_block > block_diff_limit:
                AutoSwitchProviderService.update_default_provider(network=network, operation=Operation.BLOCK_TXS)

    def get_block_head(self, api_name):
        try:
            api_class = APIS_CLASSES[api_name].get_api()
            if api_name.endswith('interface'):
                # for apis that implement in new structure
                block_head = api_class.get_max_block_head_of_apis()
            else:
                # for apis that implement in old structure
                block_head = api_class.get_block_head()
        except:
            return None
        return block_head


def set_code(cls):
    cls.code = 'update_{}_block_head_diff'.format(cls.network.lower())
    return cls


# sorted by alphabet, keep the arrangement please.
@set_code
class UpdateCardanoBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.ADA


@set_code
class UpdateAlgorandBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.ALGO


@set_code
class UpdateAptosBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.APT


@set_code
class UpdateArbitrumBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.ARB


@set_code
class UpdateAvalancheBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.AVAX


@set_code
class UpdateBaseBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.BASE


@set_code
class UpdateBitcoinCashBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.BCH


@set_code
class UpdateBinanceCoinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=60)
    network = CurrenciesNetworkName.BNB


@set_code
class UpdateBinanceSmartChainBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.BSC


@set_code
class UpdateBitcoinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=9)
    network = CurrenciesNetworkName.BTC


@set_code
class UpdateDogecoinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.DOGE


@set_code
class UpdatePolkadotBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.DOT


@set_code
class UpdateElrondBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.EGLD


@set_code
class UpdateEnjinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.ENJ


@set_code
class UpdateEthereumClassicBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.ETC


@set_code
class UpdateEthereumBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.ETH


@set_code
class UpdateFilecoinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.FIL


@set_code
class UpdateFlowBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.FLOW


@set_code
class UpdateFantomBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.FTM


@set_code
class UpdateLitecoinBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.LTC


@set_code
class UpdatePolygonBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.MATIC


@set_code
class UpdateNearBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.NEAR


@set_code
class UpdateOneBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.ONE


@set_code
class UpdateSolanaBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.SOL


@set_code
class UpdateSonicBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.SONIC


@set_code
class UpdateTronBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=1)
    network = CurrenciesNetworkName.TRX


@set_code
class UpdateStellarBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.XLM


@set_code
class UpdateMoneroBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.XMR


@set_code
class UpdateRippleBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.XRP


@set_code
class UpdateTezosBlockHeadDiffCron(UpdateBlockHeadDiffCron):
    schedule = Schedule(run_every_mins=4)
    network = CurrenciesNetworkName.XTZ
