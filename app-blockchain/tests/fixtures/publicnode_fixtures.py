import pytest
from hexbytes import HexBytes
from web3.datastructures import AttributeDict


@pytest.fixture
def block_head() -> int:
    return 4646786


@pytest.fixture
def block_addresses() -> dict:
    return {
        3700579: AttributeDict({
            'epoch': '0x1914',
            'hash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801'),
            'number': 3700579,
            'timestamp': 1736750469,
            'transactions': [
                {
                    'blockHash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801'),
                    'blockNumber': 3700579,
                    'from': '0x20ddb3c73982af3ccc0fbf38e2640aa575e66ca8',
                    'gas': 313327,
                    'gasPrice': 5500000000,
                    'hash': HexBytes('0xbc9638daa46ec30a86ec09b131bcdd810bf33af6b902c227c190239c87324fa9'),
                    'input': HexBytes('0x'),
                    'to': '0x12e66c8f215ddd5d48d150c8f46ad0c6fb0f4406',
                    'value': 2072500000000000,
                }
            ],
        }),
        3700580: AttributeDict({
            'epoch': '0x1914',
            'hash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2341238801'),
            'number': 3700580,
            'timestamp': 1736750470,
            'transactions': [
                {
                    'blockHash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2341238801'),
                    'blockNumber': 3700580,
                    'from': '0x20ddb3c73982af3ccc0fbf38e2640aa575e66ca8',
                    'gas': 313327,
                    'gasPrice': 5500000000,
                    'hash': HexBytes('0xbc9638daa46ec30a86ec09b131bcdd810bf33af6b902c227c750239c87324fa9'),
                    'input': HexBytes('0x'),
                    'to': '0x12e66c8f215ddd5d48d150c8f46ad0c6fb0f4406',
                    'value': 2072500000000000,
                }
            ],
        }),
    }


@pytest.fixture
def transactions_details() -> dict:
    return {
        "0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83": {
            'blockHash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801'),
            'blockNumber': 3700579,
            'from': '0xf310b07583a5515d25384a82df027124d54aaf26',
            'gas': 30000,
            'gasPrice': 6250000000,
            'hash': HexBytes('0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83'),
            'input': HexBytes('0x'),
            'to': '0x0b31836b57cb2f5af83f4eb6560cc1b4eb655123',
            'value': 2072500000000000,
        }
    }


@pytest.fixture
def tx_receipt() -> dict:
    return {
        'blockHash': HexBytes('0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801'),
        'blockNumber': 3700579,
        'contractAddress': None,
        'from': '0xf310b07583a5515d25384a82df027124d54aaf26',
        'gasUsed': 21900,
        'status': 1,
        'to': '0x0b31836b57cb2f5af83f4eb6560cc1b4eb655123',
        'transactionHash': HexBytes('0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83'),
    }
