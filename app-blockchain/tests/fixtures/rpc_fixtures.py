import pytest


@pytest.fixture
def block_head() -> dict:
    return {
        "result": "0x46e782",
    }


@pytest.fixture
def block_addresses() -> dict:
    return {
        3700579: {
            "result": {
                "number": "0x387763",
                "timestamp": "0x6784b585",
                "hash": "0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801",
                "epoch": "0x1914",
                "transactions": [
                    {
                        "blockHash": "0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801",
                        "blockNumber": "0x387763",
                        "from": "0x20ddb3c73982af3ccc0fbf38e2640aa575e66ca8",
                        "gas": "0x4c7ef",
                        "gasPrice": "0x147d35700",
                        "hash": "0xbc9638daa46ec30a86ec09b131bcdd810bf33af6b902c227c190239c87324fa9",
                        "input": "0x",
                        "to": "0x12e66c8f215ddd5d48d150c8f46ad0c6fb0f4406",
                        "value": "0x0",
                    }
                ],
                "size": "0x51f",
            }
        },
        3700580: {
            "result": {
                "number": "0x387764",
                "timestamp": "0x6784b586",
                "hash": "0x23c2dc8aeae32035952551109aeb5133176a505a6e8d5d324d20841ffd1e6f90",
                "epoch": "0x1914",
                "transactions": [
                    {
                        "blockHash": "0x23c2dc8aeae32035952551109aeb5133176a505a6e8d5d324d20841ffd1e6f90",
                        "blockNumber": "0x387764",
                        "from": "0xf310b07583a5515d25384a82df027124d54aaf26",
                        "gas": "0x7530",
                        "gasPrice": "0x174876e80",
                        "hash": "0x8d0824748421d68dbee29a9b930249fa773ce7df5ce24360d261feb3c6cd8f2a",
                        "input": "0x",
                        "to": "0xdf2f7f7306f90879901371461c47b3ae7ed3daf1",
                        "value": "0x75ced824c0800",
                    }
                ],
                "size": "0x286",
            }
        },
    }


@pytest.fixture
def transactions_details() -> dict:
    return {
        "0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83": {
            "result": {
                "blockHash": "0x562da2f3b9229af7ca559ba2417b8d1a1451ab76b1321730b564de2348458801",
                "blockNumber": "0x387763",
                "from": "0xf310b07583a5515d25384a82df027124d54aaf26",
                "gas": "0x7530",
                "gasPrice": "0x174876e80",
                "hash": "0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83",
                "input": "0x",
                "to": "0x0b31836b57cb2f5af83f4eb6560cc1b4eb655123",
                "value": "0x75ced824c0800",
            }
        }
    }


@pytest.fixture
def transaction_receipt() -> dict:
    return {
        "0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83": {
            "result": {
                "blockHash": "0x2871b36076aa51fdc3cafad7283823f77a8403eba63495884fda4b1275e843d9",
                "blockNumber": "0x35f072",
                "from": "0x77e109ed6d3facc5eb5ba444e48554769f88384e",
                "status": "0x1",
                "to": "0xee7eda8736f5d44af6650db5e2815af87f49c9cf",
                "transactionHash": "0x8c182a49755263b0a0541124e8e7a69fa4631a27aead7e5acc019c95c862d629",
                "transactionIndex": "0x0",
                "type": "0x0"
            }
        }
    }
