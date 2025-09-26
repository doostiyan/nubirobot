"""
The classes in this module process each new transaction detected on
Nobitex hot wallets. Processing is done on receiving webhooks from
sites like blockcypher that we have configured to watch our wallets.
"""
import datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils.timezone import now

from exchange.audit.models import ExternalWallet, ExternalWithdraw
from exchange.accounts.models import Notification
from exchange.base.logging import report_event
from exchange.base.parsers import parse_iso_date
from exchange.base.models import get_currency_codename, get_explorer_url, Currencies
from exchange.base.money import money_is_close
from exchange.wallet.models import AvailableHotWalletAddress, WithdrawRequest, AutomaticWithdraw
from exchange.wallet.withdraw_process import withdraw_method


class WebhookParser:
    """ Base class for processing blockchain transactions received by webhook
    """

    def __init__(self, currency):
        self.currency = currency

    def get_status(self, tx_info):
        raise NotImplementedError

    def get_hash(self, tx_info):
        raise NotImplementedError

    def get_time(self, tx_info):
        received_time = tx_info.get('received')
        if not received_time:
            return None
        return parse_iso_date(received_time)

    def get_inputs(self, tx_info, tx_hash):
        """ Return the input address for the given transaction

            The transaction is currently assumed to only have one input address,
            so this method return that single input address as a string.
        """
        raise NotImplementedError

    def get_outputs(self, tx_info, tx_hash):
        """ Return a list of output addresses and amount transferred to them for the given transaction

            Response is a list of dicts: [{'address': '1...', 'value': Decimal(..)}]
        """
        raise NotImplementedError

    def validate_inputs(self, tx_info, tx_hash):
        """ Check if the input address is a valid hot wallet address and return it.
            In case of any error, None is returned.
        """
        try:
            input_address = self.get_inputs(tx_info, tx_hash)
        except ValueError:
            return None
        if not input_address:
            msg = "[Webhook Parse]: inputs is not available"
            report_event(msg)
            raise ValueError(msg)
        if not AvailableHotWalletAddress.objects.filter(address=input_address, currency=self.currency).exists():
            return None
        return input_address

    def process_outputs(self, tx_info, tx_hash, hot_wallet_address):
        """ Process every output of the transaction
        """
        for output in self.get_outputs(tx_info, tx_hash):
            currency = output.get('currency') or self.currency
            output_address = output.get('address')
            if not output_address:
                Notification.notify_admins('*Address:* {}\n*Currency:* {}\n*Explorer URL:* {}'.format(
                    hot_wallet_address,
                    get_currency_codename(currency),
                    get_explorer_url(currency, txid=tx_hash),
                ), title='⛔️ *تراکنش با خروجی بدون آدرس از هات ولت!!*', channel='critical')
                continue

            # Usually the remaining amount of input is returned to the same address
            if output_address == hot_wallet_address:
                continue

            # Log the external withdraw
            tx_time = self.get_time(tx_info) or now()
            amount = output.get('value')
            tag = output.get('tag')
            external_withdraw = self.create_external_withdraw_log(
                currency, amount, tx_hash, hot_wallet_address, output_address, tx_time, tag=tag)
            if not external_withdraw:
                continue

            self.match_external_withdraw(external_withdraw)
            # if not matched_request:
            #     Notification.notify_admins('*Address:* {}\n*Value:* {}\n*Currency:* {}\n*Explorer URL:* {}'.format(
            #         output_address,
            #         output.get('value'),
            #         get_currency_codename(currency),
            #         get_explorer_url(currency, txid=tx_hash),
            #     ), title='⛔️ *تراکنش مشکوک هات ولت!!*', channel='critical')
            #     return False
        return True

    def create_external_withdraw_log(self, currency, amount, tx_hash, from_addr, to_addr, created_at,
                                     tag=None, reprocess=False):
        """ Create the external withdraw record for the withdraw with given parameters, or return
             None if no already exists
        """
        try:
            external_withdraw = ExternalWithdraw.objects.get(currency=currency, tx_hash=tx_hash, destination=to_addr)
            if not reprocess:
                return None
            already_finalized = external_withdraw.tp == ExternalWithdraw.TYPES.user_withdraw \
                and external_withdraw.user_withdraw
            if already_finalized:
                return None
            return external_withdraw
        except ExternalWithdraw.DoesNotExist:
            return ExternalWithdraw.objects.create(
                created_at=created_at,
                source=ExternalWallet.objects.get_or_create(
                    name='Hot {} {}'.format(get_currency_codename(currency).upper(), from_addr),
                    currency=currency,
                    tp=ExternalWallet.TYPES.hot,
                )[0],
                destination=to_addr,
                tx_hash=tx_hash,
                tag=tag,
                currency=currency,
                amount=amount,
            )

    def match_external_withdraw(self, external_withdraw, reprocess=False):
        """ Find matching withdraw request for the given ExternalWithdraw and update them """
        if not reprocess:
            already_finalized = external_withdraw.tp == ExternalWithdraw.TYPES.user_withdraw \
                and external_withdraw.user_withdraw
            if already_finalized:
                return None

        withdraw_requests = WithdrawRequest.objects.filter(
            wallet__currency=external_withdraw.currency,
            target_address=external_withdraw.destination,
            status=WithdrawRequest.STATUS.sent,
            auto_withdraw__status=AutomaticWithdraw.STATUS.done,
            auto_withdraw__created_at__gte=external_withdraw.created_at - datetime.timedelta(hours=12),
            auto_withdraw__created_at__lte=external_withdraw.created_at,
            auto_withdraw__binance_id__isnull=True,
            auto_withdraw__transaction_id=external_withdraw.tx_hash,
        ).select_related('auto_withdraw')

        # Filter by tag for tagged addresses
        if external_withdraw.tag:
            withdraw_requests = withdraw_requests.filter(tag=external_withdraw.tag)

        # Check for matching internal withdraw request
        matched_request = None
        for withdraw in withdraw_requests:
            auto_withdraw = withdraw.auto_withdraw
            auto_withdraw_method = withdraw_method[AutomaticWithdraw.get_type_codename(auto_withdraw.tp)]
            withdraw_amount = auto_withdraw_method.round_amount(auto_withdraw_method.get_withdraw_value(withdraw, None, None), withdraw.currency)
            if money_is_close(withdraw_amount, external_withdraw.amount):
                matched_request = withdraw
                break

        # Update withdraw and matched request
        if not matched_request:
            return None
        external_withdraw.tp = ExternalWithdraw.TYPES.user_withdraw
        external_withdraw.user_withdraw = matched_request
        external_withdraw.save(update_fields=['tp', 'user_withdraw'])
        matched_request.status = WithdrawRequest.STATUS.done
        matched_request.save(update_fields=['status'])
        return matched_request

    def webhook_parse(self, tx_info):
        """ Parse webhook response

            Note: The webhook is processed when the transaction is not confirmed yet.
        """
        tx_hash = self.get_hash(tx_info)
        try:
            hot_wallet_address = self.validate_inputs(tx_info, tx_hash)
            if not hot_wallet_address:
                return HttpResponse(status=200)
        except ValueError:
            return HttpResponse(status=400)
        self.process_outputs(tx_info, tx_hash, hot_wallet_address)
        return HttpResponse(status=200)


class BTCBlocknativeWebhookParser(WebhookParser):
    def get_status(self, tx_info):
        return tx_info.get('status')

    def get_hash(self, tx_info):
        if not tx_info.get('txid'):
            msg = "[Webhook Parse]: hash is not available"
            report_event(msg)
            raise ValueError(msg)
        return tx_info.get('txid')

    def get_inputs(self, tx_info, tx_hash):
        input_addresses = tx_info.get("inputs", [{}])
        if len(input_addresses) != 1:
            Notification.notify_admins('*Currency:* {}\n*Explorer URL:* {}'.format(
                get_currency_codename(self.currency),
                get_explorer_url(self.currency, txid=tx_hash),
            ), title='⛔️ *تراکنش غیر نرمال از هات ولت!!*', channel='critical')
            raise ValueError()
        return input_addresses[0].get("address")

    def get_outputs(self, tx_info, tx_hash):
        outputs = tx_info.get("outputs", [])
        result = []
        for output in outputs:
            output_res = {
                "address": output.get('address'),
                "value": Decimal(output.get('value', 0))
            }
            result.append(output_res)
        return result


class BTCBlockcypherWebhookParser(WebhookParser):
    """ Blockcypher BTC Webhook Parser

        Sample Hook Data: https://requestbin.com/r/enjsljzxzxo9f/ (also in tests)
        To Create:
          curl -d '{"event": "unconfirmed-tx", "address": "bc1...", "url": "https://..."}'
            'https://api.blockcypher.com/v1/btc/main/hooks?token=TOKEN
    """

    def get_status(self, tx_info):
        status = "pending" if tx_info.get('confirmations') == 0 else "confirmed"
        return status

    def get_hash(self, tx_info):
        if not tx_info.get('hash'):
            msg = "[Webhook Parse]: hash is not available"
            report_event(msg)
            raise ValueError(msg)
        return tx_info.get('hash')

    def get_inputs(self, tx_info, tx_hash):
        input_addresses = tx_info.get("inputs", [{}])[0].get("addresses")

        if len(input_addresses) != 1:
            Notification.notify_admins('*Currency:* {}\n*Explorer URL:* {}'.format(
                get_currency_codename(self.currency),
                get_explorer_url(self.currency, txid=tx_hash),
            ), title='⛔️ *تراکنش غیر نرمال از هات ولت!!*', channel='critical')
            raise ValueError()
        return input_addresses[0]

    def get_outputs(self, tx_info, tx_hash):
        result = []
        for output in tx_info.get('outputs', []):
            output_addresses = output.get('addresses') or []
            if len(output_addresses) != 1:
                Notification.notify_admins('*Currency:* {}\n*Explorer URL:* {}'.format(
                    get_currency_codename(self.currency),
                    get_explorer_url(self.currency, txid=tx_hash),
                ), title='⛔️ *تراکنش غیر نرمال از هات ولت!!*', channel='critical')
                continue
            result.append({
                'address': output_addresses[0],
                'value': Decimal(output.get('value', 0)) * Decimal('1e-8')
            })
        return result


class ETHBlocknativeWebhookParser(WebhookParser):
    def get_status(self, tx_info):
        return tx_info.get('status')

    def get_hash(self, tx_info):
        if not tx_info.get('hash'):
            msg = "[Webhook Parse]: hash is not available"
            report_event(msg)
            raise ValueError(msg)
        return tx_info.get('hash')

    def get_inputs(self, tx_info, tx_hash):
        return tx_info.get('from')

    def get_outputs(self, tx_info, tx_hash):
        if tx_info.get("asset") == 'ETH':
            currency = Currencies.eth
            address = tx_info.get('to')
            value = Decimal(tx_info.get('value')) * Decimal('1e-18')
        elif tx_info.get("asset") == 'USDT':
            currency = Currencies.usdt
            contract_params = tx_info.get('contractCall', {}).get('params', {})
            address = contract_params.get('_to')
            if not address:
                Notification.notify_admins('*Currency:* {}\n*Explorer URL:* {}'.format(
                    get_currency_codename(currency),
                    get_explorer_url(currency, txid=tx_hash),
                ), title='⛔️ *تراکنش غیر نرمال از هات ولت!!*', channel='critical')
            value = Decimal(contract_params.get('_value')) * Decimal('1e-6')
        else:
            Notification.notify_admins('*Currency:* {}\n*Explorer URL:* {}'.format(
                tx_info.get("asset"),
                get_explorer_url(Currencies.eth, txid=tx_hash),
            ), title='⛔️ *تراکنش غیر نرمال از هات ولت!!*', channel='critical')
            return []
        result = [{
            "address": address,
            "value": value,
            "currency": currency,
        }]
        return result


class XRPLWebhookParser(WebhookParser):
    def get_status(self, tx_info):
        return "pending"

    def get_hash(self, tx_info):
        if not tx_info.get('transaction', {}).get('hash'):
            msg = "[Webhook Parse]: hash is not available"
            report_event(msg)
            raise ValueError(msg)
        return tx_info.get('transaction', {}).get('hash')

    def get_inputs(self, tx_info, tx_hash):
        return tx_info.get('transaction', {}).get('Account')

    def get_outputs(self, tx_info, tx_hash):
        destination = tx_info.get('transaction', {}).get('Destination', [])
        tag = tx_info.get('transaction', {}).get('DestinationTag')
        value = Decimal(tx_info.get('meta', {}).get('delivered_amount')) * Decimal('1e-6')

        result = [{
            "address": destination,
            "value": value,
            "tag": tag,
        }]
        return result


def change_hotwallet(old_addr, new_addr, currency, network):
    AvailableHotWalletAddress.objects.filter(address=old_addr, currency=currency, network=network).update(active=False)
    new_hotwallet, created = AvailableHotWalletAddress.objects.get_or_create(address=new_addr, currency=currency, network=network)
    if created:
        new_hotwallet.active = True
        new_hotwallet.save(update_fields=["active"])
