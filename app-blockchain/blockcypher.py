import random
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.models import Transaction


def blockcypher_parse_tp(currency):
    if currency == Currencies.ltc:
        return 'ltc'
    if currency == Currencies.btc:
        return 'btc'
    if currency == Currencies.eth:
        return 'eth'
    raise ValueError('Unsupported Currency: {}'.format(currency))


def blockcypher_get_token():
    if not settings.IS_PROD:
        return ''
    return random.choice(settings.BLOCKCYPHER_API_KEYS)


def fetch_transaction_outputs(txid, currency, start=0, page_size=300, network='main'):
    tp = blockcypher_parse_tp(currency)
    endpoint = 'https://api.blockcypher.com/v1/{}/{}/txs/{}?instart=1000&outstart={}&limit={}&token={}'.format(
        tp, network, txid, start, page_size, blockcypher_get_token()
    )
    try:
        outputs_info = requests.get(endpoint, timeout=60, proxies=settings.DEFAULT_PROXY)
        outputs_info.raise_for_status()
    except Exception as e:
        err = 'BlockcypherAPI: tx'
        return None
    outputs_info = outputs_info.json()
    return outputs_info['outputs']


def blockcypher_inspect(address, currency, after_block=None, before_block=None, limit=20, network='mainnet'):
    network_url = 'main' if network == 'mainnet' else 'test3'
    BLOCKCYPHER_BUGGED_TXS = [
        '910f4107e7e4126d8351161da1b6a29feb51805d2120815d26aa73b8fbc34144',
        'a7ffe28698b538508e0038d7edd5776d292c90cf9853f3b38c30746e94488c35',
    ]
    # API Call
    tp = blockcypher_parse_tp(currency)
    block_filter = '&after={}'.format(after_block) if after_block else ''
    block_filter += '&before={}'.format(before_block) if before_block else ''
    endpoint = 'https://api.blockcypher.com/v1/{}/{}/addrs/{}/full?limit={}&txlimit=10000{}&token={}'.format(
        tp, network_url, address, limit, block_filter, blockcypher_get_token()
    )
    try:
        address_info = requests.get(endpoint, timeout=60, proxies=settings.DEFAULT_PROXY)
        address_info.raise_for_status()
    except Exception as e:
        return None
    address_info = address_info.json()
    txs = address_info.get('txs', [])

    transactions = []
    for tx in txs:
        txid = tx.get('hash')
        if txid in BLOCKCYPHER_BUGGED_TXS:
            continue
        value = Decimal('0')
        outputs = tx.get('outputs', [])
        inputs = tx.get('inputs', [])
        from_addresses = set()
        next_outputs = tx.get('next_outputs')
        pages_to_check = 8
        huge = False
        for i in range(pages_to_check + 1):
            for output in outputs:
                if not output or not output.get('addresses'):
                    # Sometimes no address is specified in output, for example when the script
                    #   type is pay-to-witness-pubkey-hash
                    continue
                if output['addresses'][0] == address and output['script_type'] in ['pay-to-pubkey-hash', 'pay-to-witness-script-hash', 'pay-to-witness-pubkey-hash']:
                    value += output.get('value', 0)

            for input in inputs:
                if not input or not input.get('addresses'):
                    continue
                from_addresses.update(input['addresses'])
                if input['addresses'][0] == address and input['script_type'] in ['pay-to-pubkey-hash', 'pay-to-witness-script-hash', 'pay-to-witness-pubkey-hash']:
                    value -= input.get('output_value')

            if value > Decimal('0'):
                # Found, it is improbable that an address is included in multiple outputs
                break
            if not next_outputs:
                # Transaction seems small
                break
            if i == pages_to_check:
                # Huge transaction, address not seen in the first 2020 outputs
                huge = True
                break
            # Fetch next output batch
            outputs = fetch_transaction_outputs(txid, currency, start=20 + i * 1000, page_size=1000, network=network_url)
            if outputs is None:
                return None
            if not outputs:
                break

        value = Decimal(str(round(value))) / Decimal('1e8')
        transactions.append(Transaction(
            address=address,
            from_address=list(from_addresses),
            hash=txid,
            block=tx.get('block_height'),
            timestamp=parse_iso_date(tx.get('confirmed', tx.get('received'))),
            value=value,
            confirmations=int(tx.get('confirmations', 0)),
            is_double_spend=bool(tx.get('double_spend')),
            details=tx,
            huge=huge,
        ))
    return transactions
