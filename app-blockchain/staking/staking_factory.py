from exchange.blockchain.staking.bnb_staking import BnbStaking
from exchange.blockchain.staking.ftm_staking import FtmStaking
from exchange.blockchain.staking.matic_staking import MaticStaking
from exchange.blockchain.staking.ada_staking import AdaStaking
from exchange.blockchain.staking.atom_staking import AtomStaking
from exchange.blockchain.staking.trx_staking import TrxStaking
from exchange.blockchain.staking.dot_staking import DotStaking
from exchange.blockchain.staking.sol_interface import SolStaking
from exchange.blockchain.utils import UnsupportedStaking


class StakingFactory:
    # Add networks in alphabetical order
    staking_dict = {
        'ADA': AdaStaking,
        'ATOM': AtomStaking,
        'DOT': DotStaking,
        'FTM': FtmStaking,
        'MATIC': MaticStaking,
        'SOL': SolStaking,
        'TRX': TrxStaking,
        'BNB': BnbStaking,
    }

    @classmethod
    def get_staking(cls, network, currency, platform):
        try:
            return cls.staking_dict[network]
        except KeyError:
            raise UnsupportedStaking(
                f'Staking for currency: {currency} on network: {network} using platform: {platform} is not supported yet!')
        except Exception:
            pass
