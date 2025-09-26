import pytest

BLOCK_HEAD_FIXTURE_VALUE: int = 116119851
ADDRESS_TXS_CHECKPOINT_VALUE: int = 92880720

@pytest.fixture
def block_head() -> dict:
    return {
        'result': f'{BLOCK_HEAD_FIXTURE_VALUE}',
    }


@pytest.fixture
def block_addresses() -> dict:
    return {
        'result': {
            'data': [
                {
                    'transactions': [
                        '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt'
                    ]
                }
            ]
        }
    }



@pytest.fixture
def batch_tx_details() -> dict:
    return {
        'result': [
            {
                'digest': '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt',
                'transaction': {
                    'data': {
                        'transaction': {
                            'kind': 'ProgrammableTransaction',
                            'transactions': [
                                {
                                    'TransferObjects': [
                                        [
                                            {
                                                'NestedResult': [
                                                    0,
                                                    0
                                                ]
                                            }
                                        ],
                                        {
                                            'Input': 1
                                        }
                                    ]
                                }
                            ],
                        },
                        'sender': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384',
                    }},
                'effects': {
                    'status': {
                        'status': 'success'
                    }
                },
                'balanceChanges': [
                    {
                        'owner': {'AddressOwner': '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'},
                        'amount': '500000000000',
                        'coinType': '0x2::sui::SUI',
                    },
                    {
                        'owner': {'AddressOwner': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'},
                        'amount': '-500001747880',
                        'coinType': '0x2::sui::SUI',
                    }],
                'timestampMs': '1740405479642',
                'checkpoint': '116119851',
            }
        ]
    }



@pytest.fixture
def tx_details() -> dict:
    return {
        'result': {
                'digest': '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt',
                'transaction': {
                    'data': {
                        'transaction': {
                            'kind': 'ProgrammableTransaction',
                            'transactions': [
                                {
                                    'TransferObjects': [
                                        [
                                            {
                                                'NestedResult': [
                                                    0,
                                                    0
                                                ]
                                            }
                                        ],
                                        {
                                            'Input': 1
                                        }
                                    ]
                                }
                            ],
                        },
                        'sender': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384',
                    }},
                'effects': {
                    'status': {
                        'status': 'success'
                    }
                },
                'balanceChanges': [
                    {
                        'owner': {'AddressOwner': '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'},
                        'amount': '500000000000',
                        'coinType': '0x2::sui::SUI',
                    },
                    {
                        'owner': {'AddressOwner': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'},
                        'amount': '-500001747880',
                        'coinType': '0x2::sui::SUI',
                    }],
                'timestampMs': '1740405479642',
                'checkpoint': '116119851',
            }
    }


@pytest.fixture
def address_transactions() -> dict:
    return {
        'result': {
            'data': [
                {
                    'digest': '9H7LgfoSC5NrduQijjw6DBFdHxyEgKPHr3eYAgFK5GcM',
                    'transaction': {
                        'data': {
                            'messageVersion': 'v1',
                            'transaction': {
                                'kind': 'ProgrammableTransaction',
                                'transactions': [
                                    {
                                        'TransferObjects': [
                                            [
                                                {
                                                    'NestedResult': [
                                                        0,
                                                        0
                                                    ]
                                                }
                                            ],
                                            {
                                                'Input': 1
                                            }
                                        ]
                                    }
                                ],
                            },
                            'sender': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384',
                        },
                    },
                    'effects': {
                        'status': {
                            'status': 'success'
                        },
                        'gasUsed': {
                            'computationCost': '750000',
                            'storageCost': '1976000',
                            'storageRebate': '978120',
                            'nonRefundableStorageFee': '9880'
                        },
                        'gasObject': {
                            'owner': {
                                'AddressOwner': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'
                            },
                        },
                    },
                    'balanceChanges': [
                        {
                            'owner': {
                                'AddressOwner': '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
                            },
                            'coinType': '0x2::sui::SUI',
                            'amount': '500000000000'
                        },
                        {
                            'owner': {
                                'AddressOwner': '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'
                            },
                            'coinType': '0x2::sui::SUI',
                            'amount': '-500001747880'
                        }
                    ],
                    'timestampMs': '1734790514554',
                    'checkpoint': f'{ADDRESS_TXS_CHECKPOINT_VALUE}'
                }]}}
