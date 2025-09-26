import base64
import codecs
import os
from decimal import Decimal

import exchange.blockchain.ws.rpc_pb2 as lnrpc
import exchange.blockchain.ws.rpc_pb2_grpc as rpcstub
from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import BlockchainUtilsMixin
if settings.IS_EXPLORER_SERVER:
    INHERITANCE_CLASSES = (BlockchainUtilsMixin,)
else:
    from exchange.wallet.block_processing import NobitexBlockProcessing
    from exchange.wallet.deposit import save_deposit_from_blockchain_transaction_invoice
    INHERITANCE_CLASSES = (BlockchainUtilsMixin, NobitexBlockProcessing)

lnd_readonly_macaroon_path = os.path.join(settings.DATA_DIR, 'readonly.macaroon')
lnd_tls_cert_path = os.path.join(settings.DATA_DIR, 'tls.cert')


class LndWS(*INHERITANCE_CLASSES):
    """
    coins:
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    currency = Currencies.btc
    currencies = [Currencies.btc]

    lnd_url = settings.LND_URL

    PRECISION = 8
    USE_PROXY = False
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'

    ws = None
    blockchain_ws = None
    keep_alive_interval = 25
    block_latest_number = 2

    def __init__(self, network=None):
        if network is not None:
            self.network = network
        self.macaroon = codecs.encode(open(lnd_readonly_macaroon_path, 'rb').read(), 'hex')

    @classmethod
    def get_ws(cls, *args, **kwargs):
        if cls.blockchain_ws is None:
            cls.blockchain_ws = cls(*args, **kwargs)
        return cls.blockchain_ws

    def run(self):
        import grpc
        os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
        cert = open(lnd_tls_cert_path, 'rb').read()
        ssl_creds = grpc.ssl_channel_credentials(cert)
        channel = grpc.secure_channel(self.lnd_url, ssl_creds)
        stub = rpcstub.LightningStub(channel)
        request = lnrpc.InvoiceSubscription()
        for response in stub.SubscribeInvoices(request, metadata=[('macaroon', self.macaroon)]):
            tx_invoice = response.payment_request
            tx_state = response.state
            print(f'Receive {tx_invoice} event with state {tx_state}')
            tx_hash = base64.b64encode(response.r_hash).decode()
            if response.state != 1:
                continue
            tx_value = response.amt_paid_sat * Decimal('1e-8')
            print(f'Deposit value: {tx_value}')

            transaction = Transaction(
                hash=tx_hash,
                invoice=tx_invoice,
                value=tx_value,
                timestamp=response.settle_date,
                confirmations=1,
            )
            save_deposit_from_blockchain_transaction_invoice(transaction, currency=Currencies.btc, network='BTCLN')
