from binascii import hexlify
from decimal import Decimal

from django.conf import settings

from exchange.base.models import SUPPORTED_INVOICE_CURRENCIES, Currencies
from exchange.blockchain.constants import BitcoinMainnet, BitcoinTestnet
from exchange.blockchain.lnaddr import lndecode


def decode_btc_invoice(invoice):
    try:
        net = BitcoinMainnet if settings.IS_PROD else BitcoinTestnet
        addr = lndecode(invoice, net=net)
    except Exception as e:
        print(e)
        return None
    return {
        'address': hexlify(addr.pubkey.serialize()).decode('utf-8'),
        'network': 'BTCLN',
        'amount': addr.amount,
        'date': addr.date,
    }


invoice_decoder = {
    Currencies.btc: decode_btc_invoice
}


def decode_invoice(invoice, currency):
    if currency not in SUPPORTED_INVOICE_CURRENCIES:
        return None
    return invoice_decoder.get(currency)(invoice)
