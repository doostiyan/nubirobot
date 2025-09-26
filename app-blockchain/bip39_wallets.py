from exchange.base.models import Currencies
from exchange.blockchain.doge import DogeBlockchainWallet
from exchange.blockchain.eth import EthereumBlockchainWallet
from exchange.blockchain.trx import TronBlockchainWallet

BLOCKCHAIN_WALLET_CLASS = {
    Currencies.trx: TronBlockchainWallet(),
    Currencies.doge: DogeBlockchainWallet(),
    Currencies.eth: EthereumBlockchainWallet(),
}
