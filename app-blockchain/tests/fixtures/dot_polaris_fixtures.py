import pytest


@pytest.fixture
def tx_hash_successful_transfer_all():
    return '0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97'


@pytest.fixture
def tx_hash_successful_transfer_allow_death():
    return '0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670'


@pytest.fixture
def tx_hash_successful_transfer_keep_alive():
    return '0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb'

@pytest.fixture
def tx_hash_successful_utility_batch_all():
    return '0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f'


@pytest.fixture
def tx_hash_fail():
    return '0x661f5c72ce96312e2cac6915d4761c57ee039b779a35e8053dfd82f5535a6b88'


@pytest.fixture
def address_txs_address():
    return '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW'


@pytest.fixture
def from_block():
    return 25771582


@pytest.fixture
def to_block():
    return 25771592


@pytest.fixture
def tx_details_tx_hash_transfer_all_mock_response():
    return {
        "data": {
            "transfers": [
                {
                    "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                    "module": "balances",
                    "function": "transferAll",
                    "isFinalized": True,
                    "blockNumber": 25771671,
                    "fromAddress": "12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx",
                    "toAddress": "1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7",
                    "amount": None,
                    "fee": "153293982",
                    "tip": "0",
                    "events": [
                        {
                            "module": "balances",
                            "function": "Withdraw",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 0,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\",\"153293982\"]"
                        },
                        {
                            "module": "system",
                            "function": "KilledAccount",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 1,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Transfer",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 2,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\",\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"3176963933818\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 3,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"122635185\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 4,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"123VugBRFMqUEFviSYrG3ewdZ46ZmqxjmRaGY6BvakfdPVaG\",\"30658797\"]"
                        },
                        {
                            "module": "transactionPayment",
                            "function": "TransactionFeePaid",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 5,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\",\"153293982\",\"0\"]"
                        },
                        {
                            "module": "system",
                            "function": "ExtrinsicSuccess",
                            "extrinsicHash": "0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97",
                            "extrinsicIdx": 6,
                            "blockNumber": 25771671,
                            "isTransferEvent": True,
                            "attributes": "[{\"weight\":{\"refTime\":\"289145000\",\"proofSize\":\"3593\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                        }
                    ]
                }
            ]
        }
    }


@pytest.fixture
def tx_details_tx_hash_transfer_allow_death_mock_response():
    return {
        "data": {
            "transfers": [
                {
                    "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                    "module": "balances",
                    "function": "transferAllowDeath",
                    "isFinalized": True,
                    "blockNumber": 25772140,
                    "fromAddress": "1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7",
                    "toAddress": "16eQrUMFZKyFXqYh4Ntdf8HZfUFYbJekcJuZLEjny11PqLDT",
                    "amount": "250000000000",
                    "fee": "161305248",
                    "tip": "0",
                    "events": [
                        {
                            "module": "balances",
                            "function": "Withdraw",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 0,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"161305248\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Transfer",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 1,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"16eQrUMFZKyFXqYh4Ntdf8HZfUFYbJekcJuZLEjny11PqLDT\",\"250000000000\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 2,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"129044198\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 3,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[\"16Jh21ThTh2tW98NuN2gM7Q3KaYiuJLbxCNbuBkFpwcDkRqx\",\"32261050\"]"
                        },
                        {
                            "module": "transactionPayment",
                            "function": "TransactionFeePaid",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 4,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"161305248\",\"0\"]"
                        },
                        {
                            "module": "system",
                            "function": "ExtrinsicSuccess",
                            "extrinsicHash": "0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670",
                            "extrinsicIdx": 5,
                            "blockNumber": 25772140,
                            "isTransferEvent": True,
                            "attributes": "[{\"weight\":{\"refTime\":\"290565000\",\"proofSize\":\"3593\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                        }
                    ]
                }
            ]
        }
    }


@pytest.fixture
def tx_details_tx_hash_transfer_keep_alive_mock_response():
    return {
        "data": {
            "transfers": [
                {
                    "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                    "module": "balances",
                    "function": "transferKeepAlive",
                    "isFinalized": True,
                    "blockNumber": 25772000,
                    "fromAddress": "12nr7GiDrYHzAYT9L8HdeXnMfWcBuYfAXpgfzf3upujeCciz",
                    "toAddress": "12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx",
                    "amount": "2581292828000",
                    "fee": "162203062",
                    "tip": "0",
                    "events": [
                        {
                            "module": "balances",
                            "function": "Withdraw",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 0,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"12nr7GiDrYHzAYT9L8HdeXnMfWcBuYfAXpgfzf3upujeCciz\",\"162203062\"]"
                        },
                        {
                            "module": "system",
                            "function": "NewAccount",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 1,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Endowed",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 2,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\",\"2581292828000\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Transfer",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 3,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"12nr7GiDrYHzAYT9L8HdeXnMfWcBuYfAXpgfzf3upujeCciz\",\"12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx\",\"2581292828000\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 4,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"129762449\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 5,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"15BeWFXGDfrbZLMjuLoC6DmFvbS5rM3EHpUW9CwaAa5itYua\",\"32440613\"]"
                        },
                        {
                            "module": "transactionPayment",
                            "function": "TransactionFeePaid",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 6,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[\"12nr7GiDrYHzAYT9L8HdeXnMfWcBuYfAXpgfzf3upujeCciz\",\"162203062\",\"0\"]"
                        },
                        {
                            "module": "system",
                            "function": "ExtrinsicSuccess",
                            "extrinsicHash": "0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb",
                            "extrinsicIdx": 7,
                            "blockNumber": 25772000,
                            "isTransferEvent": True,
                            "attributes": "[{\"weight\":{\"refTime\":\"277685000\",\"proofSize\":\"3593\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                        }
                    ]
                }
            ]
        }
    }

@pytest.fixture
def tx_details_tx_hash_utility_batch_all_mock_response():
    return {
    "data": {
        "transfers": [
            {
                "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                "module": "utility",
                "function": "batchAll",
                "isFinalized": True,
                "blockNumber": 25899774,
                "fromAddress": "1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7",
                "toAddress": "1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u",
                "amount": "78000000000",
                "fee": "207759772",
                "tip": "0",
                "events": [
                    {
                        "module": "balances",
                        "function": "Withdraw",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 0,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 1,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u\",\"78000000000\"]"
                    },
                    {
                        "module": "utility",
                        "function": "ItemCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 2,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 3,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP\",\"12350851819400\"]"
                    },
                    {
                        "module": "utility",
                        "function": "BatchCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 5,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "balances",
                        "function": "Deposit",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 6,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"166207817\"]"
                    },
                    {
                        "module": "transactionPayment",
                        "function": "TransactionFeePaid",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 8,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\",\"0\"]"
                    },
                    {
                        "module": "system",
                        "function": "ExtrinsicSuccess",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 9,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[{\"weight\":{\"refTime\":\"473900558\",\"proofSize\":\"7186\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                    },
                    {
                        "module": "balances",
                        "function": "Withdraw",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 0,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 1,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u\",\"78000000000\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 3,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP\",\"12350851819400\"]"
                    },
                    {
                        "module": "utility",
                        "function": "BatchCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 5,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "system",
                        "function": "ExtrinsicSuccess",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 9,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[{\"weight\":{\"refTime\":\"473900558\",\"proofSize\":\"7186\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                    }
                ]
            },
            {
                "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                "module": "utility",
                "function": "batchAll",
                "isFinalized": True,
                "blockNumber": 25899774,
                "fromAddress": "1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7",
                "toAddress": "15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP",
                "amount": "12350851819400",
                "fee": "207759772",
                "tip": "0",
                "events": [
                    {
                        "module": "balances",
                        "function": "Withdraw",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 0,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 1,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u\",\"78000000000\"]"
                    },
                    {
                        "module": "utility",
                        "function": "ItemCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 2,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 3,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP\",\"12350851819400\"]"
                    },
                    {
                        "module": "utility",
                        "function": "BatchCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 5,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "balances",
                        "function": "Deposit",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 6,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"166207817\"]"
                    },
                    {
                        "module": "transactionPayment",
                        "function": "TransactionFeePaid",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 8,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\",\"0\"]"
                    },
                    {
                        "module": "system",
                        "function": "ExtrinsicSuccess",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 9,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[{\"weight\":{\"refTime\":\"473900558\",\"proofSize\":\"7186\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                    },
                    {
                        "module": "balances",
                        "function": "Withdraw",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 0,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 1,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u\",\"78000000000\"]"
                    },
                    {
                        "module": "balances",
                        "function": "Transfer",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 3,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP\",\"12350851819400\"]"
                    },
                    {
                        "module": "utility",
                        "function": "BatchCompleted",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 5,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[]"
                    },
                    {
                        "module": "balances",
                        "function": "Deposit",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 6,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"166207817\"]"
                    },
                    {
                        "module": "transactionPayment",
                        "function": "TransactionFeePaid",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 8,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[\"1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7\",\"207759772\",\"0\"]"
                    },
                    {
                        "module": "system",
                        "function": "ExtrinsicSuccess",
                        "extrinsicHash": "0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f",
                        "extrinsicIdx": 9,
                        "blockNumber": 25899774,
                        "isTransferEvent": True,
                        "attributes": "[{\"weight\":{\"refTime\":\"473900558\",\"proofSize\":\"7186\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                    }
                ]
            }
        ]
    }
}


@pytest.fixture
def tx_details_tx_hash_fail_mock_response():
    return {
        "data": {
            "transfers": []
        }
    }


@pytest.fixture
def address_txs_mock_response():
    return {
        "data": {
            "transfers": [
                {
                    "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                    "module": "balances",
                    "function": "transferAllowDeath",
                    "isFinalized": True,
                    "blockNumber": 25773048,
                    "fromAddress": "14KVE545ypr51NFAZqPXFhWALqqJSXXaS7PQ4bPXPT8m5sLz",
                    "toAddress": "12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW",
                    "amount": "19899830694752",
                    "fee": "159305248",
                    "tip": "0",
                    "events": [
                        {
                            "module": "balances",
                            "function": "Withdraw",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 0,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[\"14KVE545ypr51NFAZqPXFhWALqqJSXXaS7PQ4bPXPT8m5sLz\",\"159305248\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Transfer",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 1,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[\"14KVE545ypr51NFAZqPXFhWALqqJSXXaS7PQ4bPXPT8m5sLz\",\"12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW\",\"19899830694752\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 2,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"127444198\"]"
                        },
                        {
                            "module": "balances",
                            "function": "Deposit",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 3,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[\"12Yo8LQiJLoviSS6tWV98pvNVnhfjtQ1cqjE94q6Dn1d4e3F\",\"31861050\"]"
                        },
                        {
                            "module": "transactionPayment",
                            "function": "TransactionFeePaid",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 4,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[\"14KVE545ypr51NFAZqPXFhWALqqJSXXaS7PQ4bPXPT8m5sLz\",\"159305248\",\"0\"]"
                        },
                        {
                            "module": "system",
                            "function": "ExtrinsicSuccess",
                            "extrinsicHash": "0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522",
                            "extrinsicIdx": 5,
                            "blockNumber": 25773048,
                            "isTransferEvent": True,
                            "attributes": "[{\"weight\":{\"refTime\":\"290565000\",\"proofSize\":\"3593\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                        }
                    ]
                },

            ]
        }
    }


@pytest.fixture
def block_head_mock_response():
    return {
        "data": {
            "latestBlock": {
                "blockHash": "0x38f01595fdf7d2585d5e75297c7a965dc06fdab44a05b053dcf4e5e2d16a569a",
                "blockNumber": 25773105,
                "timestamp": "2025-04-28 11:36:54"
            }
        }
    }


@pytest.fixture
def block_txs_mock_response():
    return {
        "data": {
            "blockRange": [
                {
                    "blockHash": "0xb5cf971d67fe0516aad0786d124c29aed53719bf0f472cd4fd75f44165e3f62f",
                    "blockNumber": 25771587,
                    "timestamp": "2025-04-28 09:04:30",
                    "transfers": [
                        {
                            "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                            "module": "balances",
                            "function": "transferAllowDeath",
                            "isFinalized": True,
                            "blockNumber": 25771587,
                            "fromAddress": "134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj",
                            "toAddress": "124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR",
                            "amount": "10115234416900",
                            "fee": "161305248",
                            "tip": "0",
                            "events": [
                                {
                                    "module": "balances",
                                    "function": "Withdraw",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 0,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj\",\"161305248\"]"
                                },
                                {
                                    "module": "system",
                                    "function": "NewAccount",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 1,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR\"]"
                                },
                                {
                                    "module": "balances",
                                    "function": "Endowed",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 2,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR\",\"10115234416900\"]"
                                },
                                {
                                    "module": "balances",
                                    "function": "Transfer",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 3,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj\",\"124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR\",\"10115234416900\"]"
                                },
                                {
                                    "module": "balances",
                                    "function": "Deposit",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 4,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"13UVJyLnbVp9RBZYFwFGyDvVd1y27Tt8tkntv6Q7JVPhFsTB\",\"129044198\"]"
                                },
                                {
                                    "module": "balances",
                                    "function": "Deposit",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 5,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"12YFWxpS32wTZq4HcH28HMR5atkGhxzfD7aNjhTCu5Vyz9J9\",\"32261050\"]"
                                },
                                {
                                    "module": "transactionPayment",
                                    "function": "TransactionFeePaid",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 6,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[\"134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj\",\"161305248\",\"0\"]"
                                },
                                {
                                    "module": "system",
                                    "function": "ExtrinsicSuccess",
                                    "extrinsicHash": "0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac",
                                    "extrinsicIdx": 7,
                                    "blockNumber": 25771587,
                                    "isTransferEvent": True,
                                    "attributes": "[{\"weight\":{\"refTime\":\"290565000\",\"proofSize\":\"3593\"},\"class\":\"Normal\",\"paysFee\":\"Yes\"}]"
                                }
                            ]
                        }
                    ]
                },
                {
                    "blockHash": "0x9068211e51651251fa912c607e33d869b0424a0c360276103bfff02765ce3633",
                    "blockNumber": 25771588,
                    "timestamp": "2025-04-28 09:04:36",
                    "transfers": []
                }
            ]
        }
    }
