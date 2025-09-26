import queue
import random
import signal
import sys
import traceback
from decimal import ROUND_UP, Decimal, localcontext
from threading import Thread
from time import sleep
from typing import List, NoReturn, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from exchange.accounts.models import Notification
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.connections import (
    AdaClient,
    AlgoClient,
    AptosClient,
    ArbitrumClient,
    ArbitrumHDClient,
    AtomClient,
    AvaxClient,
    AvaxOnlyHDClient,
    BaseHDClient,
    BinanceChainClient,
    BscClient,
    BscHDClient,
    DogeClient,
    DotClient,
    ElrondClient,
    EnjinClient,
    EosClient,
    EthClient,
    EthereumClassicClient,
    EthereumClassicHDClient,
    EthHDClient,
    EthOnlyHDClient,
    FilecoinClient,
    FlareClient,
    FlowClient,
    FtmClient,
    FtmOnlyHDClient,
    HarmonyClient,
    HarmonyHDClient,
    HederaClient,
    HotWalletClient,
    LndClient,
    MoneroClient,
    NearClient,
    PolygonClient,
    PolygonHDClient,
    RippleClient,
    SolanaClient,
    SonicHDClient,
    StellarClient,
    TezosClient,
    ToncoinClient,
    ToncoinHLv2Client,
    TRC20Client,
    TrxClient,
    TRXHDClient,
    TRXOnlyHDClient,
    get_bsc_geth,
    get_electron_cash,
    get_electrum,
    get_electrum_ltc,
    get_geth,
    get_parity,
    get_pmn_hotwallet,
    get_trx_hotwallet,
)
from exchange.base.formatting import f_m
from exchange.base.logging import report_event, report_exception
from exchange.base.models import ACTIVE_CRYPTO_CURRENCIES, Currencies, Settings, get_currency_codename, get_explorer_url
from exchange.blockchain.contracts_conf import (
    BASE_ERC20_contract_info,
    BEP20_contract_info,
    ERC20_contract_info,
    TRC20_contract_info,
    arbitrum_ERC20_contract_info,
    opera_ftm_contract_info,
    polygon_ERC20_contract_info,
    sol_contract_info,
    ton_contract_info,
)
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.wallet.models import AutomaticWithdraw, Transaction, WithdrawRequest
from exchange.wallet.settlement import VandarSettlement
from exchange.wallet.withdraw_commons import NobitexWithdrawException, update_auto_withdraw_status

########################################
# Blockchain Withdraw Methods
########################################


class AutomaticWithdrawMethod:
    CURRENCIES = []
    BATCH_ENABLED = False
    TESTNET_ENABLED = False
    sleep_before = 0.5
    hotwallet_index: int = 0
    running_with_queue: bool = False
    max_queue_size: int = 12
    max_multi_withdraw_size_from_queue: int = 6
    queue_initiated: bool = False

    def __init__(self, hotwallet_index: int = 0, running_with_queue: bool = False):
        self.hotwallet_index = hotwallet_index
        self.running_with_queue = running_with_queue
        if self.running_with_queue:
            self.queue_wait_time = 20  # Wait in second until we have enough withdraws in the queue
            if self.max_queue_size <= 0 or self.max_multi_withdraw_size_from_queue <= 0:
                raise NobitexWithdrawException(
                    "max_queue_size and max_multi_withdraw_size_from_queue must be greater than zero when running with queue"
                )
            self.withdraw_queue: queue = queue.Queue(maxsize=self.max_queue_size)
            self.is_running = True
            self.terminating = False
            self.queue_listener_thread = Thread(
                target=self.create_multi_transaction_from_queue,
                name=f'queue-thread-{type(self).__name__}-{self.hotwallet_index}',
                daemon=True,
            )

    def get_currencies(self):
        if not self.CURRENCIES:
            return ACTIVE_CRYPTO_CURRENCIES
        return self.CURRENCIES

    @staticmethod
    def get_withdraw_fee(currency, network, amount: Optional[Decimal] = None, contract_address=None):
        if network is None:
            network = CURRENCY_INFO[currency]['default_network']
        currency_name = get_currency_codename(currency)
        # Default value
        default_withdraw_fee = CURRENCY_INFO[currency]['network_list'][network]['withdraw_fee']
        cache_key = 'withdraw_fee_{}_{}'.format(currency_name, network.lower())
        if contract_address:
            cache_key += f'_{contract_address}'
        fee = Settings.get(
            cache_key,
            default_withdraw_fee,
        )
        if fee.endswith('%'):
            if amount is not None:
                fee_decimal = Decimal(fee.strip('%')) / Decimal('100.0')
                return amount * fee_decimal
            else:
                return None
        return Decimal(fee)

    @staticmethod
    def get_withdraw_max(currency, network=None, contract_address=None):
        if network is None:
            network = CURRENCY_INFO[currency]['default_network']
        currency_name = get_currency_codename(currency)
        # Default value
        default_withdraw_max = CURRENCY_INFO[currency]['network_list'][network]['withdraw_max']
        cache_key = 'withdraw_max_{}_{}'.format(currency_name, network.lower())
        if contract_address:
            cache_key += f'_{contract_address}'
        withdraw_max = Settings.get(
            cache_key,
            default_withdraw_max,
        )
        return Decimal(withdraw_max)

    @staticmethod
    def get_withdraw_min(currency, network=None, contract_address=None):
        if network is None:
            network = CURRENCY_INFO[currency]['default_network']
        currency_name = get_currency_codename(currency)
        # Default value
        if contract_address is not None:
            try:
                default_withdraw_min = CURRENCY_INFO[currency]['network_list'][network]['contract_addresses'][
                    contract_address
                ]['withdraw_min']
            except KeyError:
                default_withdraw_min = CURRENCY_INFO[currency]['network_list'][network]['withdraw_min']
        else:
            default_withdraw_min = CURRENCY_INFO[currency]['network_list'][network]['withdraw_min']
        cache_key = 'withdraw_min_{}_{}'.format(currency_name, network.lower())
        if contract_address:
            cache_key += f'_{contract_address}'
        withdraw_min = Settings.get(
            cache_key,
            default_withdraw_min,
        )
        return Decimal(withdraw_min)

    def validate(self, withdraw, log, a_withdraw):
        withdraw.refresh_from_db()
        if withdraw.status != WithdrawRequest.STATUS.processing:
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.failed)
            m = 'Change the status of withdraw #{} to failed'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 1
            log.save()
            raise NobitexWithdrawException(m)
        if withdraw.wallet.currency not in self.get_currencies():
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.failed)
            m = '{}: This withdraw CURRENCY not in the supported currencies: {}'.format(withdraw.pk,
                                                                                        self.get_currencies())
            print(m)
            log.description = m
            log.status = 2
            log.save()
            raise NobitexWithdrawException(m)

        # Check the transaction to be sure that the withdraw amount is deducted from balance
        if not withdraw.transaction or not withdraw.transaction.pk:
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.failed)
            m = 'Change the status of withdraw #{} to failed'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 10
            log.save()
            raise NobitexWithdrawException(m)

        # Check to be sure the withdraw is not canceled concurrently
        cancel_transaction = Transaction.objects.filter(
            wallet=withdraw.wallet,
            ref_module=Transaction.REF_MODULES['ReverseTransaction'],
            ref_id=withdraw.transaction.id,
            created_at__gt=withdraw.transaction.created_at,
        )
        if cancel_transaction.exists():
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.failed)
            m = 'Change the status of withdraw #{} to failed'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 11
            log.save()
            raise NobitexWithdrawException(m)

    def get_withdraw_value(self, withdraw, log, a_withdraw):
        amount = withdraw.amount - self.get_withdraw_fee(withdraw.wallet.currency, withdraw.network, withdraw.amount, contract_address=withdraw.contract_address)
        if amount <= 0:
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.canceled)
            m = 'Amount without fee is lower than zero'
            print(m)
            log.description = m
            log.status = 3
            log.save()
            raise NobitexWithdrawException(m)
        return amount

    def round_amount(self, value, currency, contract_address=None):
        raise NobitexWithdrawException("This should be overridden by child")

    def get_withdraw_from(self):
        raise NobitexWithdrawException("This should be overridden by child")

    def get_withdraw_client(self):
        raise NobitexWithdrawException("This should be overridden by child")

    def create_transaction(self, client, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        raise NobitexWithdrawException("This should be overridden by child")

    def create_multi_transaction(self, electrum, currency, outputs, wallet_from=None, rpc_id="curltext"):
        raise NobitexWithdrawException("This should be overridden by child")

    def batch_output_format(self, dest_addr, amount, currency, dest_tag):
        raise NobitexWithdrawException("This should be overridden by child")

    def create_multi_transaction_from_queue(self) -> NoReturn:
        currency = None
        wait_time = self.queue_wait_time
        check_time = 1  # check the queue every check_time in second
        while self.is_running:
            if wait_time <= 0 or self.withdraw_queue.qsize() >= self.max_multi_withdraw_size_from_queue:
                wait_time = self.queue_wait_time
                print(f"Current queue size is {self.withdraw_queue.qsize()}")
                if self.withdraw_queue.empty():
                    continue

                withdraws = []
                outputs = []
                tmp = self.max_multi_withdraw_size_from_queue
                while not self.withdraw_queue.empty() and tmp > 0:
                    tmp -= 1
                    withdraw_obj, output = self.withdraw_queue.get()
                    withdraws.append(withdraw_obj)
                    if output:
                        outputs.append(output)
                    self.withdraw_queue.task_done()
                client = self.get_withdraw_client()
                wallet_from = self.get_withdraw_from()
                try:
                    result = self.create_multi_transaction(client, currency, outputs, wallet_from)
                    with transaction.atomic():
                        self.done_withdraw(withdraws, result)
                        update_auto_withdraw_status(withdraws, AutomaticWithdraw.STATUS.done)
                    print(f"Sent {len(outputs)} withdraws transaction from queue to hot-wallet successfully.")
                except Exception as e:
                    report_exception()
                    update_auto_withdraw_status(withdraws, AutomaticWithdraw.STATUS.failed, error_msg=str(e)[:1000])
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_tb)
                    m = f"Wait for {self.queue_wait_time}s to decrease failed withdraws, because we have a problem in hot-wallet or database"
                    print(m)
                    sleep(self.queue_wait_time)
                    continue
            else:
                wait_time -= check_time
                sleep(check_time)

    def shutdown(self) -> NoReturn:
        print(f"--------------The service is shutting down. Please wait while all withdrawals are sent to the hot wallet-------------")
        self.withdraw_queue.join()
        self.is_running = False
        self.queue_listener_thread.join()
        print(f"--------------The service process withdraws and the queue shutdown gracefully-------------")

    def handle_sigterm(self, signum=None, frame=None):
        self.terminating = True

    def done_withdraw(self, withdraws, result):
        for withdraw_obj in withdraws:
            withdraw, log, a_withdraw = withdraw_obj
            a_withdraw.transaction_id = result
            print('[Transaction Done] {}'.format(result))
            withdraw.blockchain_url = get_explorer_url(withdraw.wallet.currency, txid=a_withdraw.transaction_id, network=withdraw.network)
            withdraw.status = WithdrawRequest.STATUS.sent
            withdraw.save(update_fields=['status', 'blockchain_url'])
            a_withdraw.save(update_fields=['transaction_id'])

            m = '[Withdraw Done] {}'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 0
            log.save()

    def initiate_queue(self):
        self.queue_listener_thread.start()
        signal.signal(signal.SIGTERM, self.handle_sigterm)

    def process_withdraw(self, withdraws: List[Tuple], currency) -> NoReturn:
        """ Send withdraw to hot wallet server

        :param currency: Corresponding currency
        :param withdraws: List of withdraws which must be send through the blockchain
        :type withdraws: List[Tuple]

        :return: None
        """
        # Initiate the queue if its running_with_queue
        if self.running_with_queue and not self.queue_initiated:
            self.queue_initiated = True
            self.initiate_queue()

        # Check if withdrawals for this coin is allowed
        currency_name = get_currency_codename(currency)
        all_network_list = CURRENCY_INFO[currency]['network_list'].keys()
        network_list = []
        for network in all_network_list:
            if CURRENCY_INFO[currency]['network_list'][network].get('withdraw_enable', True):
                network_list.append(network)

        is_withdraw_enabled = {}
        for network in network_list:
            is_withdraw_enabled[network] = Settings.get_trio_flag(
                f'withdraw_enabled_{currency_name}_{network.lower()}',
                default='yes',  # all network in network_list filter by withdraw_enable=True
                third_option_value=cache.get(f'binance_withdraw_status_{currency_name}_{network}'),
            )

        processed_withdraws = []
        # Process
        client = self.get_withdraw_client()
        wallet_from = self.get_withdraw_from()
        outputs = []
        withdraws_seen = set()
        for withdraw_obj in withdraws:
            withdraw, log, a_withdraw = withdraw_obj
            try:
                self.validate(withdraw, log, a_withdraw)
            except NobitexWithdrawException as e:
                m = 'Cancel the processing of withdraw(failed in validation): {}'.format(withdraw.pk)
                print(m)
                log.description = m
                log.status = 6
                log.save()
                update_auto_withdraw_status([withdraw_obj], AutomaticWithdraw.STATUS.failed, error_msg=str(e)[:1000])
                continue

            processed_withdraws.append(withdraw_obj)
            amount = self.round_amount(self.get_withdraw_value(withdraw, log, a_withdraw), withdraw.currency, contract_address=withdraw.contract_address)
            try:
                network_key = withdraw.network or CURRENCY_INFO[currency]['default_network']
                if withdraw.contract_address:
                    if not Settings.get_trio_flag(
                        f'withdraw_enabled_{currency_name}_{network_key.lower()}_{withdraw.contract_address}',
                        default='yes',  # all network in network_list filter by withdraw_enable=True
                        third_option_value=cache.get(f'binance_withdraw_status_{currency_name}_{network_key.lower()}')):
                        raise NobitexWithdrawException('Withdraw is disabled for currency: {}'.format(currency_name))
                elif not is_withdraw_enabled.get(network_key):
                    raise NobitexWithdrawException('Withdraw is disabled for currency: {}'.format(currency_name))
                if self.BATCH_ENABLED:
                    if not self.running_with_queue:
                        # Avoid duplicate transaction for one withdraw
                        if withdraw.pk not in withdraws_seen:
                            withdraws_seen.add(withdraw.pk)
                            outputs.append(
                                self.batch_output_format(withdraw.target_address, amount, withdraw.currency, withdraw.tag)
                            )
                    else:
                        # The output may be null, because of Avoid duplicate transaction for one withdraw
                        output = None
                        if withdraw.pk not in withdraws_seen:
                            withdraws_seen.add(withdraw.pk)
                            output = self.batch_output_format(
                                withdraw.target_address, amount, withdraw.currency, withdraw.tag
                            )
                        self.withdraw_queue.put((withdraw_obj, output))
                    continue
                if self.sleep_before is not None:
                    sleep(self.sleep_before)
                result = self.create_transaction(
                    client,
                    withdraw.currency,
                    amount,
                    withdraw.target_address,
                    withdraw.tag,
                    wallet_from,
                    withdraw.pk,
                    network=withdraw.network,
                    withdraw=withdraw,
                )
                self.done_withdraw(processed_withdraws, result)
                update_auto_withdraw_status(processed_withdraws, AutomaticWithdraw.STATUS.done)
            except NobitexWithdrawException as e:
                a_withdraw.status = AutomaticWithdraw.STATUS.failed
                a_withdraw.save(update_fields=['status'])
                m = str(e)[:1000]
                log.description = m
                log.status = 4
                log.save()
                raise NobitexWithdrawException(m)
        if self.BATCH_ENABLED:
            if not self.running_with_queue:
                result = self.create_multi_transaction(client, currency, outputs, wallet_from)
                self.done_withdraw(processed_withdraws, result)
                update_auto_withdraw_status(processed_withdraws, AutomaticWithdraw.STATUS.done)

        if self.running_with_queue and self.terminating:
            self.shutdown()
            sys.exit(0)


class BaseElectrumWithdraw(AutomaticWithdrawMethod):
    BATCH_ENABLED = True
    VERSION_ELECTRUM = 3

    def batch_output_format(self, dest_addr, amount, currency, dest_tag):
        return [dest_addr, str(amount)]

    def create_transaction(self, electrum, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        try:
            data = {
                'destination': wallet_to,
                'amount': str(amount),
                'password': electrum.password
            }
            if self.VERSION_ELECTRUM == 4 and electrum.wallet_path is not None:
                data['wallet'] = electrum.wallet_path
            response = electrum.request('payto', data, rpc_id)
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))

        signed_tx = response['result']
        try:
            response = electrum.request('broadcast', {'tx': signed_tx})
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

        return self.parse_result(response)

    def create_multi_transaction(self, electrum, currency, outputs, wallet_from=None, rpc_id="curltext"):
        try:
            data = {
                'outputs': outputs,
                'password': electrum.password
            }
            if self.VERSION_ELECTRUM == 4 and electrum.wallet_path is not None:
                data['wallet'] = electrum.wallet_path
            response = electrum.request('paytomany', data, rpc_id)
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))

        signed_tx = response['result']
        try:
            response = electrum.request('broadcast', {'tx': signed_tx})
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

        return self.parse_result(response)

    @staticmethod
    def parse_result(response):
        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Broadcast transaction has error: {}".format(response['error']))
        return response['result']


class ElectrumWithdraw(BaseElectrumWithdraw):
    CURRENCIES = [Currencies.btc]
    VERSION_ELECTRUM = 4

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_electrum()


class ElectrumLTCWithdraw(BaseElectrumWithdraw):
    CURRENCIES = [Currencies.ltc]
    VERSION_ELECTRUM = 4

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_electrum_ltc()


class ElectronCashWithdraw(BaseElectrumWithdraw):
    CURRENCIES = [Currencies.bch]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_electron_cash()

    @staticmethod
    def parse_result(response):
        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Broadcast transaction has error: {}".format(response['error']))
        return response['result'][1]


class LndWithdraw(AutomaticWithdrawMethod):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.btc]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return LndClient.get_client()

    def create_transaction(self, lnd_hotwallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext", network=None, withdraw=None):
        value = amount * Decimal('1e8')

        params = [{
            'amount': wallet_from,
            'payment_request': withdraw.invoice,
        }, lnd_hotwallet.password]
        try:
            response = lnd_hotwallet.request(
                'pay_invoice',
                params,
                rpc_id
            )
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)
        if response.get('status') != 'success':
            m = f"{response.get('code')}: {response.get('message')}"
            print(m)
            report_event(m)
            raise NobitexWithdrawException(m)
        return response['hash']


class HotWalletWithdraw(AutomaticWithdrawMethod):
    testnet_amount = Decimal('0.001')
    hotwallet_client: HotWalletClient
    create_transaction_method = 'create_transaction'
    create_multisend_transaction_method = 'create_multisend_transaction'
    TESTNET_ENABLED = False
    decimals = 8

    def round_amount(self, value, currency, contract_address=None):
        if not settings.IS_PROD and value > self.testnet_amount:
            value = self.testnet_amount
        return value.quantize(Decimal(f'1e-{self.decimals}'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return self.hotwallet_client.get_client(hw_index=self.hotwallet_index)

    def rpc_parameters(self, hot_wallet, wallet_to, amount, dest_tag, currency):
        transaction_data = {
            'to': wallet_to,
            'amount': str(amount),
        }
        if dest_tag is not None:
            transaction_data['memo'] = dest_tag
        params = [transaction_data, hot_wallet.password]
        return params

    def rpc_parameters_multisend(self, hot_wallet, outputs):
        return [{'outputs': outputs}, hot_wallet.password]

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        try:
            params = self.rpc_parameters(hot_wallet, wallet_to, amount, dest_tag, currency)

            response = hot_wallet.request(
                method=self.create_transaction_method,
                params=params,
                rpc_id='curltext',
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

    def batch_output_format(self, dest_addr, amount, contract, dest_tag=None):
        output = {'amount': str(amount), 'to': dest_addr}
        if dest_tag is not None:
            output['memo'] = dest_tag
        return output

    def create_multi_transaction(self, hot_wallet, currency, outputs, wallet_from=None, rpc_id='curltext'):
        try:
            params = self.rpc_parameters_multisend(hot_wallet, outputs)
            response = hot_wallet.request(
                method=self.create_multisend_transaction_method,
                params=params,
                rpc_id='curltext',
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get("hash") is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class HotWalletTokenWithdraw(HotWalletWithdraw):
    create_transaction_method = 'create_bep20_transaction'
    create_multisend_transaction_method = 'create_multisend_token_transaction'
    TESTNET_ENABLED = False
    sleep_before = None

    @property
    def network(self):
        return 'testnet' if self.TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'

    @property
    def contract_info_list(self):
        return BEP20_contract_info

    def get_currencies(self):
        return list(self.contract_info_list[self.network].keys())

    def decimal(self, currency):
        return self.contract_info_list[self.network][currency]['decimals']

    def contract_address(self, currency):
        return self.contract_info_list[self.network][currency]['address']

    def amount_scale(self, currency):
        return self.contract_info_list[self.network][currency].get('scale') or '1.0'

    def get_withdraw_from(self):
        return None

    def round_amount(self, value, currency, contract_address=None):
        if not settings.IS_PROD and value > self.testnet_amount:
            value = self.testnet_amount
        with localcontext() as ctx:
            ctx.prec = 999
            return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def make_rpc_output(self, wallet_to, amount, currency, dest_tag):
        if self.amount_scale(currency) != '1.0':
            amount = amount * Decimal(self.amount_scale(currency))
        transaction_data = {
            'to': wallet_to,
            'amount': str(amount),
            'contract': self.contract_address(currency),
        }
        if dest_tag is not None:
            transaction_data['memo'] = dest_tag
        return transaction_data

    def rpc_parameters(self, hot_wallet, wallet_to, amount, dest_tag, currency):
        transaction_data = self.make_rpc_output(wallet_to, amount, currency, dest_tag)
        transaction_data['password'] = hot_wallet.password
        return transaction_data

    def rpc_parameters_multisend(self, hot_wallet, outputs):
        return {'outputs': outputs, 'password': hot_wallet.password}

    def batch_output_format(self, dest_addr, amount, currency, dest_tag=None):
        output = self.make_rpc_output(dest_addr, amount, currency, dest_tag)
        return output


class AvaxWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.avax]
    TESTNET_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = AvaxClient


class AvaxOnlyHDWithdraw(AvaxWithdraw):
    hotwallet_client = AvaxOnlyHDClient


class DogeWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.doge]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('2')
    hotwallet_client = DogeClient


class BinanceChainWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.bnb]
    TESTNET_ENABLED = True
    decimals = 8
    hotwallet_client = BinanceChainClient
    sleep_before = 1


class StellarWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.xlm]
    TESTNET_ENABLED = True
    decimals = 7
    hotwallet_client = StellarClient
    testnet_amount = Decimal('2')


class EthereumClassicWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.etc]
    TESTNET_ENABLED = True
    decimals = 8
    hotwallet_client = EthereumClassicClient
    testnet_amount = Decimal('0.001')


class EthereumClassicHDWithdraw(EthereumClassicWithdraw):
    hotwallet_client = EthereumClassicHDClient


class EosWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.eos]
    TESTNET_ENABLED = True
    decimals = 4
    hotwallet_client = EosClient
    testnet_amount = Decimal('2')


class DotWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.dot]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('2')
    hotwallet_client = DotClient


class AdaWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.ada]
    BATCH_ENABLED = True
    decimals = 6
    testnet_amount = Decimal('2')
    hotwallet_client = AdaClient


class AtomWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = False
    CURRENCIES = [Currencies.atom]
    BATCH_ENABLED = False
    decimals = 6
    testnet_amount = Decimal('0.02')
    hotwallet_client = AtomClient


class EthWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.eth]
    BATCH_ENABLED = False
    decimals = 18
    testnet_amount = Decimal('0.01')
    hotwallet_client = EthClient


class EthHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.eth]
    BATCH_ENABLED = False
    decimals = 18
    testnet_amount = Decimal('0.01')
    hotwallet_client = EthHDClient


class EthOnlyHDWithdraw(EthHDWithdraw):
    hotwallet_client = EthOnlyHDClient


class BscWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.bnb]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = BscClient


class BscHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.bnb]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = BscHDClient


class SolanaWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = False
    CURRENCIES = [Currencies.sol]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('0.02')
    hotwallet_client = SolanaClient


class SolanaTokenWithdraw(HotWalletTokenWithdraw):
    TESTNET_ENABLED = True
    BATCH_ENABLED = False
    testnet_amount = Decimal('0.1')
    hotwallet_client = SolanaClient
    create_transaction_method = 'create_token_transaction'
    create_multisend_transaction_method = 'create_multisend_token_transaction'

    def rpc_parameters(self, hot_wallet, wallet_to, amount, dest_tag, currency):
        transaction_data = self.make_rpc_output(wallet_to, amount, currency, dest_tag)
        transaction_data['password'] = hot_wallet.password
        return [transaction_data]

    @property
    def contract_info_list(self):
        return sol_contract_info


class FilecoinWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.fil]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.01')
    hotwallet_client = FilecoinClient


class FlareWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.flr]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('10')
    hotwallet_client = FlareClient


class TrxWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.trx]
    BATCH_ENABLED = False
    decimals = 6
    testnet_amount = Decimal('0.1')
    hotwallet_client = TrxClient


class TrxOnlyHDWithdraw(TrxWithdraw):
    hotwallet_client = TRXOnlyHDClient


class ZTrxWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.usdt]
    BATCH_ENABLED = False
    create_transaction_method = 'transfer_to_z'
    decimals = 6
    testnet_amount = Decimal('0.1')
    hotwallet_client = TrxClient

    def rpc_parameters(self, hot_wallet, wallet_to, amount, dest_tag, currency):
        params = super().rpc_parameters(hot_wallet, wallet_to, amount, dest_tag, currency)
        params = params + [hot_wallet.password]
        return params


class RippleWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.xrp]
    TESTNET_ENABLED = True
    BATCH_ENABLED = False
    decimals = 6
    testnet_amount = Decimal('0.1')
    hotwallet_client = RippleClient


class FtmWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.ftm]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = FtmClient


class FtmOnlyHDWithdraw(FtmWithdraw):
    hotwallet_client = FtmOnlyHDClient


class PolygonWithdraw(HotWalletWithdraw):
    CURRENCIES = [Currencies.pol]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = PolygonClient


class PolygonHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.pol]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = PolygonHDClient


class HarmonyWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = False
    CURRENCIES = [Currencies.one]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('100')
    hotwallet_client = HarmonyClient


class HarmonyHDWithdraw(HarmonyWithdraw):
    hotwallet_client = HarmonyHDClient


class NearWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.near]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.2')
    hotwallet_client = NearClient


class MoneroWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.xmr]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('0.002')
    hotwallet_client = MoneroClient


class AlgoWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.algo]
    BATCH_ENABLED = False
    decimals = 6
    testnet_amount = Decimal('10')
    hotwallet_client = AlgoClient


class ArbWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.eth]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.005')
    hotwallet_client = ArbitrumClient


class ArbHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.eth]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.005')
    hotwallet_client = ArbitrumHDClient


class HederaWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.hbar]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('2')
    hotwallet_client = HederaClient


class FlowWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.flow]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('2.7')
    hotwallet_client = FlowClient


class AptosWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.apt]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.02')
    hotwallet_client = AptosClient


class ElrondWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.egld]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.02')
    hotwallet_client = ElrondClient


class EnjinWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.enj]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('10')
    hotwallet_client = EnjinClient


class ToncoinWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.ton]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('5')
    hotwallet_client = ToncoinClient


class ToncoinHLv2Withdraw(HotWalletWithdraw):
    TESTNET_ENABLED = not settings.IS_TESTNET
    CURRENCIES = [Currencies.ton]
    BATCH_ENABLED = True
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = ToncoinHLv2Client
    max_queue_size = 1000
    max_multi_withdraw_size_from_queue = 75


class ToncoinTokenHLv2Withdraw(HotWalletTokenWithdraw):
    TESTNET_ENABLED = True
    BATCH_ENABLED = True
    testnet_amount = Decimal('0.1')
    hotwallet_client = ToncoinHLv2Client
    create_transaction_method = 'create_token_transaction'

    @property
    def contract_info_list(self):
        return ton_contract_info


class TezosWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.xtz]
    BATCH_ENABLED = False
    decimals = 6
    testnet_amount = Decimal('1')
    hotwallet_client = TezosClient


class SonicHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.s]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = SonicHDClient


class BaseHDWithdraw(HotWalletWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.eth]
    BATCH_ENABLED = False
    decimals = 8
    testnet_amount = Decimal('0.1')
    hotwallet_client = BaseHDClient


class BscBep20Withdraw(AutomaticWithdrawMethod):
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = list(BEP20_contract_info[network].keys())
    sleep_before = None

    def decimal(self, currency):
        return min(BEP20_contract_info[self.network][currency]['decimals'], 8)  # we round 8 decimals at most

    def contract_address(self, currency):
        return BEP20_contract_info[self.network][currency]['address']

    def amount_scale(self, currency):
        return BEP20_contract_info[self.network][currency].get('scale') or '1.0'

    def get_withdraw_from(self):
        return None

    def round_amount(self, value, currency, contract_address=None):
        with localcontext() as ctx:
            ctx.prec = 999
            return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def get_withdraw_client(self):
        return BscClient.get_client()

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext",
                           network=None, withdraw=None):
        if self.sleep_before is not None:
            sleep(self.sleep_before)
        try:
            if self.amount_scale(currency) != '1.0':
                amount = amount * Decimal(self.amount_scale(currency))
            transaction_data = {
                'to': wallet_to,
                'amount': str(amount),
                'contract': self.contract_address(currency),
            }
            if dest_tag is not None:
                transaction_data['memo'] = dest_tag
            params = [transaction_data, hot_wallet.password]
            response = hot_wallet.request(
                method="create_bep20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class BscBep20HDWithdraw(BscBep20Withdraw):
    TESTNET_ENABLED = True

    def get_withdraw_client(self):
        return BscHDClient.get_client()


class GethWithdraw(AutomaticWithdrawMethod):
    CURRENCIES = [Currencies.eth]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return settings.GETH_ACCOUNT

    def get_withdraw_client(self):
        return get_geth()

    def create_transaction(self, geth, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext", network=None, withdraw=None):
        params = [{
            'from': wallet_from,
            'to': wallet_to,
            'value': hex(int(amount * Decimal(1e18))),
            'gas': '0xc350',
            'maxPriorityFeePerGas': '0x77359400',
            'maxFeePerGas': '0x22ecb25c00'
        }, geth.password]
        try:
            response = geth.request(
                'personal_sendTransaction',
                params,
                rpc_id
            )
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)
        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))
        return response['result']


class GethERC20Withdraw(AutomaticWithdrawMethod):
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = [Currencies.eth] + list(ERC20_contract_info[network].keys())
    gas_limit = '0x11170'

    def decimal(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('decimals')
        return ERC20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return ERC20_contract_info[self.network][currency]['address']

    def contract_gas_limit(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('gas_limit') or self.gas_limit
        return ERC20_contract_info[self.network][currency].get('gas_limit') or self.gas_limit

    def round_amount(self, value, currency, contract_address=None):
        with localcontext() as ctx:
            ctx.prec = 999
            return value.quantize(Decimal('1e{}'.format(-self.decimal(currency, contract_address))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return settings.GETH_ERC20_ACCOUNT

    def get_withdraw_client(self):
        return get_geth()

    def create_transaction(self, geth, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext", network=None, withdraw=None):
        data = '0xa9059cbb'
        if wallet_to.startswith('0x'):
            wallet_to = wallet_to[2:]
        value = hex(int(amount * Decimal('1e{}'.format(self.decimal(currency, withdraw.contract_address if withdraw else None)))))[2:]

        data = data + wallet_to.zfill(64) + value.zfill(64)
        params = [{
            'from': wallet_from,
            'to': withdraw.contract_address if withdraw and withdraw.contract_address else self.contract_address(currency),
            'data': data,
            'gas': self.contract_gas_limit(currency, withdraw.contract_address if withdraw else None),
            'maxFeePerGas': '0x22ecb25c00',
            'maxPriorityFeePerGas': '0x77359400'
        }, geth.password]
        try:
            response = geth.request(
                'personal_sendTransaction',
                params,
                rpc_id
            )
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)
        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))
        return response['result']


class GethTetherWithdraw(GethERC20Withdraw):
    CURRENCIES = [Currencies.usdt]
    TESTNET_ENABLED = False

    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'

    def get_withdraw_from(self):
        return settings.GETH_ACCOUNT


class BscGethWithdraw(GethWithdraw):
    TESTNET_ENABLED = True
    CURRENCIES = [Currencies.bnb]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return settings.BSC_GETH_ACCOUNT

    def get_withdraw_client(self):
        return get_bsc_geth()


class BscGethBEP20Withdraw(GethERC20Withdraw):
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = list(BEP20_contract_info[network].keys())
    gas_limit = '0x11170'

    def decimal(self, currency, contract_address=None):
        return BEP20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return BEP20_contract_info[self.network][currency]['address']

    def contract_gas_limit(self, currency, contract_address=None):
        return BEP20_contract_info[self.network][currency].get('gas_limit') or self.gas_limit

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return settings.BSC_GETH_BEP20_ACCOUNT

    def get_withdraw_client(self):
        return get_bsc_geth()


class PolygonERC20Withdraw(AutomaticWithdrawMethod):
    """
        This class uses new polygon hot wallet and is a general purpose class for all polygon erc20 tokens
    """
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = list(polygon_ERC20_contract_info[network].keys())
    sleep_before = None

    def decimal(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('decimals')
        return polygon_ERC20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return polygon_ERC20_contract_info[self.network][currency]['address']

    def amount_scale(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('scale', '1.0')
        return polygon_ERC20_contract_info[self.network][currency].get('scale', '1.0')

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return PolygonClient.get_client()

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext",
                           network=None, withdraw=None):
        if self.sleep_before is not None:
            sleep(self.sleep_before)
        try:
            amount *= Decimal(self.amount_scale(currency, withdraw.contract_address if withdraw is not None else None))
            contract_address = withdraw.contract_address if withdraw and withdraw.contract_address else self.contract_address(currency)
            transaction_data = {
                'to': wallet_to,
                'amount': str(amount),
                'contract': contract_address,
            }
            if dest_tag is not None:
                transaction_data['memo'] = dest_tag
            params = [transaction_data, hot_wallet.password]
            response = hot_wallet.request(
                method="create_matic_erc20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class PolygonERC20HDWithdraw(PolygonERC20Withdraw):
    TESTNET_ENABLED = True

    def get_withdraw_client(self):
        return PolygonHDClient.get_client()


class EthERC20Withdraw(AutomaticWithdrawMethod):
    """
        This class uses new eth hot wallet and is a general purpose class for all eth erc20 tokens
    """
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = [Currencies.eth] + list(ERC20_contract_info[network].keys())
    sleep_before = None

    def decimal(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('decimals')
        return ERC20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return ERC20_contract_info[self.network][currency]['address']

    def amount_scale(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('scale', '1.0')
        return ERC20_contract_info[self.network][currency].get('scale', '1.0')

    def round_amount(self, value, currency, contract_address=None):
        with localcontext() as ctx:
            ctx.prec = 999
            return value.quantize(Decimal('1e{}'.format(-self.decimal(currency, contract_address))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return EthClient.get_client()

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext",
                           network=None, withdraw=None):
        if self.sleep_before is not None:
            sleep(self.sleep_before)
        try:
            amount = amount * Decimal(self.amount_scale(currency=currency,
                                                        contract_address=withdraw.contract_address if withdraw and withdraw.contract_address else None))
            transaction_data = {
                'to': wallet_to,
                'amount': str(amount),
                'contract': withdraw.contract_address if withdraw and withdraw.contract_address else self.contract_address(currency),
            }
            if dest_tag is not None:
                transaction_data['memo'] = dest_tag
            params = [transaction_data, hot_wallet.password]
            response = hot_wallet.request(
                method="create_erc20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class EthERC20HDWithdraw(EthERC20Withdraw):
    def get_withdraw_client(self):
        return EthHDClient.get_client()


class EthERC20HDN2Withdraw(EthERC20Withdraw):
    def get_withdraw_client(self):
        return EthOnlyHDClient.get_client()


class FtmERC20Withdraw(AutomaticWithdrawMethod):
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = [Currencies.ftm] + list(opera_ftm_contract_info[network].keys())
    BATCH_ENABLED = False
    testnet_amount = Decimal('1')

    def decimal(self, currency):
        return min(opera_ftm_contract_info[self.network][currency]['decimals'], 8)

    def contract_address(self, currency):
        return opera_ftm_contract_info[self.network][currency]['address']

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def amount_scale(self, currency):
        return opera_ftm_contract_info[self.network][currency].get('scale', '1.0')

    def get_withdraw_client(self):
        return FtmClient.get_client()

    def get_withdraw_from(self):
        return None

    def create_transaction(self, client, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        amount = amount * Decimal(self.amount_scale(currency))
        params = [
                    {
                        'to': wallet_to,
                        'amount': str(amount),
                        'contract': opera_ftm_contract_info[self.network][currency]['address'],
                    },
                    client.password,
                 ]
        try:
            response = client.request(
                method='create_ftm_erc20_transaction',
                params=params,
                rpc_id='curltext',
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class ParityWithdraw(AutomaticWithdrawMethod):
    CURRENCIES = [Currencies.etc]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return settings.PARITY_ACCOUNT

    def get_withdraw_client(self):
        return get_parity()

    def create_transaction(self, parity, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        params = [{
            'from': wallet_from,
            'to': wallet_to,
            'value': hex(int(amount * Decimal(1e18))),
        }, parity.password]
        try:
            response = parity.request(
                'personal_sendTransaction',
                params,
                rpc_id
            )
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)
        if response.get('error'):
            m = '[Error] {}'.format(response['error'])
            print(m)
            raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))
        return response['result']


class TRXAPIWithdraw(AutomaticWithdrawMethod):
    CURRENCIES = [Currencies.trx]
    TESTNET_ENABLED = True

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_trx_hotwallet()

    def create_transaction(self, trx_hotwallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):

        """ sending maximum 2 TRX in testnet """
        if not settings.IS_PROD and amount > 2:
            amount = 2

        try:
            params = [{
                'to': wallet_to,
                'amount': str(amount),
            }, trx_hotwallet.password]

            response = trx_hotwallet.request(
                method="create_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = response.get('error')
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            if response.get("hash") is None:
                m = 'response hash is None'
                print(m)
                report_event(m)
                raise NobitexWithdrawException(m)
            return response.get("hash")
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class TRC20Withdraw(AutomaticWithdrawMethod):
    contract_address = ''
    decimal = 6

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e{}'.format(-self.decimal)), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_trx_hotwallet()

    def create_transaction(self, trx_hotwallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        try:
            params = [{
                'to': wallet_to,
                'amount': str(amount),
                'contract_address': self.contract_address,
            }, trx_hotwallet.password]

            response = trx_hotwallet.request(
                method="create_trc20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = response.get('error')
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get("hash") is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get("hash")
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class USDTTRC20Withdraw(TRC20Withdraw):
    CURRENCIES = [Currencies.usdt]
    contract_address = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
    decimal = 6
    sleep_before = None


class TRC20WithdrawNew(AutomaticWithdrawMethod):
    """
        This class uses new trx hot wallet and is a general purpose class for all trc20 tokens
    """
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = list(TRC20_contract_info[network].keys())
    sleep_before = None

    def decimal(self, currency):
        return TRC20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return TRC20_contract_info[self.network][currency]['address']

    def amount_scale(self, currency):
        return TRC20_contract_info[self.network][currency].get('scale', '1.0')

    def round_amount(self, value, currency, contract_address=None):
        with localcontext() as ctx:
            ctx.prec = 999
            return value.quantize(Decimal('1e{}'.format(-self.decimal(currency))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return TRC20Client.get_client()

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext",
                           network=None, withdraw=None):
        if self.sleep_before is not None:
            sleep(self.sleep_before)
        try:
            amount = amount * Decimal(self.amount_scale(currency))
            transaction_data = {
                'to': wallet_to,
                'amount': str(amount),
                'contract': self.contract_address(currency),
            }
            if dest_tag is not None:
                transaction_data['memo'] = dest_tag
            params = [transaction_data, hot_wallet.password]
            response = hot_wallet.request(
                method="create_trc20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class TrxTRC20HDWithdraw(TRC20WithdrawNew):
    def get_withdraw_client(self):
        return TRXHDClient.get_client()


class ArbERC20Withdraw(AutomaticWithdrawMethod):
    """
        This class uses arbitrum hot wallet and is a general purpose class for all arbitrum network tokens
    """
    TESTNET_ENABLED = True
    network = 'testnet' if TESTNET_ENABLED and not settings.IS_PROD else 'mainnet'
    CURRENCIES = [Currencies.eth] + list(arbitrum_ERC20_contract_info[network].keys())
    sleep_before = None

    def decimal(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('decimals')
        return arbitrum_ERC20_contract_info[self.network][currency]['decimals']

    def contract_address(self, currency):
        return arbitrum_ERC20_contract_info[self.network][currency]['address']

    def amount_scale(self, currency, contract_address=None):
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('info').get('scale', '1.0')
        return arbitrum_ERC20_contract_info[self.network][currency].get('scale', '1.0')

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e{}'.format(-self.decimal(currency, contract_address))), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return ArbitrumClient.get_client()

    def create_transaction(self, hot_wallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext",
                           network=None, withdraw=None):
        if self.sleep_before is not None:
            sleep(self.sleep_before)
        try:
            amount *= Decimal(self.amount_scale(currency, withdraw.contract_address if withdraw is not None else None))
            contract_address = withdraw.contract_address if withdraw and withdraw.contract_address else self.contract_address(currency)
            transaction_data = {
                'to': wallet_to,
                'amount': str(amount),
                'contract': contract_address,
            }
            if dest_tag is not None:
                transaction_data['memo'] = dest_tag
            params = [transaction_data, hot_wallet.password]
            response = hot_wallet.request(
                method="create_erc20_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = f"{response.get('code')}: {response.get('message')}"
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get('hash') is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get('hash')

        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)


class ArbERC20HDWithdraw(ArbERC20Withdraw):
    TESTNET_ENABLED = True

    def get_withdraw_client(self):
        return ArbitrumHDClient.get_client()


class USDTArbERC20Withdraw(ArbERC20Withdraw):
    CURRENCIES = [Currencies.usdt]
    sleep_before = None


class BaseERC20HDWithdraw(HotWalletTokenWithdraw):
    TESTNET_ENABLED = True
    BATCH_ENABLED = False
    testnet_amount = Decimal('0.1')
    hotwallet_client = BaseHDClient
    create_transaction_method = 'create_erc20_transaction'

    def rpc_parameters(self, hot_wallet, wallet_to, amount, dest_tag, currency):
        transaction_data = self.make_rpc_output(wallet_to, amount, currency, dest_tag)
        transaction_data['password'] = hot_wallet.password
        return [transaction_data]

    @property
    def contract_info_list(self):
        return BASE_ERC20_contract_info

class PMNAPIWithdraw(AutomaticWithdrawMethod):
    CURRENCIES = [Currencies.pmn]

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('.0000001'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return get_pmn_hotwallet()

    def create_transaction(self, pmn_hotwallet, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext", network=None, withdraw=None):

        """ sending maximum 2 PMN in testnet """
        if not settings.IS_PROD and amount > 2:
            amount = 2

        try:
            params = [{
                'to': wallet_to,
                'amount': str(amount),
            }, pmn_hotwallet.password]

            if dest_tag:
                params[0]['memo'] = dest_tag

            response = pmn_hotwallet.request(
                method="create_transaction",
                params=params,
                rpc_id="curltext",
            )
            if response.get('status') != 'success':
                m = response.get('error')
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            if response.get("hash") is None:
                m = 'response hash is None'
                print(m)
                report_exception()
                raise NobitexWithdrawException(m)
            return response.get("hash")
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            report_exception()
            raise NobitexWithdrawException(m)

# class OmniCoreWithdraw(AutomaticWithdrawMethod):
#     def __init__(self):
#         currencies = [Currencies.btc]
#         super(OmniCoreWithdraw, self).__init__(currencies)
#
#     def round_amount(self, value):
#         return value.quantize(Decimal('.00000001'), rounding=ROUND_UP)
#
#     def get_withdraw_from(self):
#         return settings.OMNI_ACCOUNT
#
#     def get_withdraw_client(self):
#         return get_omnicore()
#
#     def create_transaction(self, omnicore, CURRENCY, amount, wallet_to, dest_tag=None, wallet_from=None):
#         try:
#             response = omnicore.request(
#                 'omni_send',
#                 {'fromaddress': wallet_from,
#                  'toaddress': wallet_to,
#                  'amount': str(amount),
#                  'propertyid': 31,
#                  }
#             )
#         except Exception as e:
#             m = '[Exception] {}'.format(str(e))
#             print(m)
#             raise NobitexWithdrawException(m)
#
#         if response.get('error'):
#             m = '[Error] {}'.format(response['error'])
#             print(m)
#             raise NobitexWithdrawException("Creating transaction has error: {}".format(response['error']))
#
#         return response


class VandarAPIWithdraw(AutomaticWithdrawMethod):
    CURRENCIES = [Currencies.rls]
    TESTNET_ENABLED = True

    def round_amount(self, value, currency, contract_address=None):
        return value

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return None

    def create_transaction(self, vandar, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        pk = rpc_id
        withdraw = WithdrawRequest.objects.get(pk=pk)
        try:
            result = VandarSettlement(withdraw).do_settle(is_auto_withdraw=True)
        except Exception as e:
            m = '[VandarSettlementException] {}'.format(str(e))
            print(m)
            raise NobitexWithdrawException(m)
        return result[0]['transaction_id']


class FakeWithdraw(AutomaticWithdrawMethod):
    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e-8'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return None

    def create_transaction(self, fake, currency, amount, wallet_to, dest_tag=None, wallet_from=None, rpc_id="curltext", network=None, withdraw=None):
        txid = 'tx{}'.format(random.randint(100000, 999999))
        Notification.notify_admins(
            'درخواست برداشت به صورت تستی شبیه‌سازی شد:\n*Amount:* {}\n*Address:* {}\n*TXID:* {}'.format(
                f_m(amount, c=currency, show_c=True),
                wallet_to,
                txid,
            )
        )
        return txid


class FakeBatchWithdraw(AutomaticWithdrawMethod):
    BATCH_ENABLED = True

    def round_amount(self, value, currency, contract_address=None):
        return value.quantize(Decimal('1e-8'), rounding=ROUND_UP)

    def get_withdraw_from(self):
        return None

    def get_withdraw_client(self):
        return None

    def create_transaction(self, fake, currency, amount, wallet_to, dest_tag=None, wallet_from=None,
                           rpc_id="curltext", network=None, withdraw=None):
        txid = 'tx{}'.format(random.randint(100000, 999999))
        Notification.notify_admins(
            'درخواست برداشت به صورت تستی شبیه‌سازی شد:\n*Amount:* {}\n*Address:* {}\n*TXID:* {}'.format(
                f_m(amount, c=currency, show_c=True),
                wallet_to,
                txid,
            )
        )
        return txid

    def batch_output_format(self, dest_addr, amount, currency, dest_tag):
        return [dest_addr, str(amount)]

    def create_multi_transaction(self, fake, currency, outputs, wallet_from=None, rpc_id="curltext"):
        txid = 'tx{}'.format(random.randint(100000, 999999))

        Notification.notify_admins(
            'درخواست برداشت دستی به صورت تستی شبیه‌سازی شد:\n*Output:* {}\n*TXID:* {}'.format(
                outputs,
                txid,
            )
        )
        return txid
