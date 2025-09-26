import pytest


@pytest.fixture
def tx_hash_successful():
    return '0x1a4c7dabdd839bf2147cbf626e9397fec472605723f4bb4cd83efac13f7060e0'


@pytest.fixture
def token_tx_hash_successful():
    return '0x6c5fdd3c2de57ed259c7fecf564d1760ac24b972264f2b9d16f56c59896df00a'


@pytest.fixture
def batch_token_tx_hash_successful():
    return '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783'


@pytest.fixture
def tx_hash_failed():
    return '0x08407def182c668e2f0328d5282b3d181a284861d81320ca127810a4809bb562'


@pytest.fixture
def tx_detail_block_head_successful_mock_response():
    return 22153991


@pytest.fixture
def batch_tx_detail_block_head_successful_mock_response():
    return 22225480


@pytest.fixture
def token_tx_detail_block_head_successful_mock_response():
    return 22218204


@pytest.fixture
def tx_detail_block_head_failed_response():
    return 22153986


@pytest.fixture
def tx_details_tx_hash_successful_mock_response():
    return {'accessList': [], 'blockHash': '0x5127caf663cc49937887a1781f6fc0556030428dd8f5cc81420c0a302ab42fbb',
            'blockNumber': 22153400, 'chainId': 1, 'contractAddress': None,
            'from': '0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97', 'gas': 21000,
            'gasPrice': '405389995', 'gasUsed': 21000,
            'hash': '0x1a4c7dabdd839bf2147cbf626e9397fec472605723f4bb4cd83efac13f7060e0', 'input': '0x', 'logs': [],
            'nonce': 1443327, 'status': True,
            'to': '0xf84aab3d91b251b468ac3d7536d5beaa1c1f61d2',
            'transactionHash': '0x1a4c7dabdd839bf2147cbf626e9397fec472605723f4bb4cd83efac13f7060e0', 'type': 2,
            'value': '18625826777595028', }


@pytest.fixture
def token_tx_details_tx_hash_successful_mock_response():
    return {'accessList': [], 'blockHash': '0x7aacb62b6bd8dd710f429559c1f1d2204adfe153d2aa2da04a7177997b98ebc7',
            'blockNumber': 22217753, 'chainId': 1, 'contractAddress': None,
            'from': '0xa6ab3b345598ff5705de7863e622589732362149', 'gas': 80000,
            'gasPrice': '10271980614', 'gasUsed': 63209,
            'hash': '0x6c5fdd3c2de57ed259c7fecf564d1760ac24b972264f2b9d16f56c59896df00a',
            'input': '0xa9059cbb00000000000000000000000042b26a7a2cb08f5fa24a06620859f697fe0241b7000000000000000000000000000000000000000000000000000000000ee6b280',
            'logs': [{'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                      'blockHash': '0x7aacb62b6bd8dd710f429559c1f1d2204adfe153d2aa2da04a7177997b98ebc7',
                      'blockNumber': 22217753,
                      'data': '0x000000000000000000000000000000000000000000000000000000000ee6b280',
                      'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                 '0x000000000000000000000000a6ab3b345598ff5705de7863e622589732362149',
                                 '0x00000000000000000000000042b26a7a2cb08f5fa24a06620859f697fe0241b7'],
                      'transactionHash': '0x6c5fdd3c2de57ed259c7fecf564d1760ac24b972264f2b9d16f56c59896df00a'}],
            'nonce': 86, 'status': True,
            'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'transactionHash': '0x6c5fdd3c2de57ed259c7fecf564d1760ac24b972264f2b9d16f56c59896df00a',
            'type': 2, 'value': '0', }


@pytest.fixture
def tx_details_tx_hash_failed_mock_response():
    return {'accessList': [], 'blockHash': '0xfa089213b49cc19789a98f59c971213478f553b8387ba1d3a4958a40890ebdc2',
            'blockNumber': 22153982, 'chainId': 1, 'contractAddress': None,
            'from': '0x1a1c87d9a6f55d3bbb064bff1059ad37b6bdc097', 'gas': 100000,
            'gasPrice': '1517462188', 'gasUsed': 99035,
            'hash': '0x08407def182c668e2f0328d5282b3d181a284861d81320ca127810a4809bb562',
            'input': '0x23b872dd000000000000000000000000057ea0fda51359d1eaf16e46e63a1bcd90059cec000000000000000000000000ab782bc7d4a2b306825de5a7730034f8f63ee1bc00000000000000000000000000000000000000000000000029d89b470dbcb000',
            'logs': [], 'nonce': 690249, 'status': False,
            'to': '0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f',
            'transactionHash': '0x08407def182c668e2f0328d5282b3d181a284861d81320ca127810a4809bb562',
            'type': 2, 'value': '0'}


@pytest.fixture
def batch_tx_details_tx_hash_successful_mock_response():
    return {'accessList': [], 'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
            'blockNumber': 21474469, 'chainId': 1, 'contractAddress': None,
            'from': '0xce0d2213a0eaff4176d90b39879b7b4f870fa428', 'gas': 924529,
            'gasPrice': '6841403743', 'gasUsed': 359651,
            'hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
            'input': '0xe6930a220000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000000000018000000000000000000000000000000000000000000000000000000000000002a00000000000000000000000000000000000000000000000000000000000000008000000000000000000000000467bccd9d29f223bce8043b84e8c8b282827790f0000000000000000000000005a98fcbea516cf06857215779fd812ca3bef1b320000000000000000000000006982508145454ce325ddbe47a25d4ec3d231193300000000000000000000000095ad61b0a150d79219dcf64e1e6cc01f0b64c4ce000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec7000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec7000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec70000000000000000000000000000000000000000000000000000000000000008000000000000000000000000c7db188e23d029dedf0d596c0731ff6d3c131cdb000000000000000000000000deee5f8d867340bf6e56e9ae069a790ef537d40000000000000000000000000052c5233d3d12e9d5522759ace8b551d926b797d10000000000000000000000008cd7fea8630a030ea16009914b6f8a79bea05c3000000000000000000000000045dcec86a1eded2af0858396f26619be801677aa000000000000000000000000af2a7f37df0fcad99db3714e6283ff10a56db09200000000000000000000000066a9e3db3bac9a4fc151bcbab4dde98f7b3932e100000000000000000000000023f6cd8c3e6f5defd7aeecfbad1f8462b92717f70000000000000000000000000000000000000000000000000000000000000008000000000000000000000000000000000000000000000000000000000011f67300000000000000000000000000000000000000000000000f83e3b538d3b80000000000000000000000000000000000000000000010089c54f545b59fd4370000000000000000000000000000000000000000000000037d72c7dff11239c88c00000000000000000000000000000000000000000000000000000000004483e0840000000000000000000000000000000000000000000000000000000001a29c1000000000000000000000000000000000000000000000000000000004faf77d10000000000000000000000000000000000000000000000000000000001dcd6500',
            'logs': [{'address': '0x467bccd9d29f223bce8043b84e8c8b282827790f',
                      'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                      'blockNumber': 21474469,
                      'data': '0x000000000000000000000000000000000000000000000000000000000011f673',
                      'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                 '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                                 '0x000000000000000000000000c7db188e23d029dedf0d596c0731ff6d3c131cdb'],
                      'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                      }, {'address': '0x5a98fcbea516cf06857215779fd812ca3bef1b32',
                          'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                          'blockNumber': 21474469,
                          'data': '0x00000000000000000000000000000000000000000000000f83e3b538d3b80000',
                          'topics': [
                              '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                              '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                              '0x000000000000000000000000deee5f8d867340bf6e56e9ae069a790ef537d400'],
                          'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                          },
                     {'address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',
                      'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                      'blockNumber': 21474469,
                      'data': '0x000000000000000000000000000000000000000010089c54f545b59fd4370000',
                      'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                 '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                                 '0x00000000000000000000000052c5233d3d12e9d5522759ace8b551d926b797d1'],
                      'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                      }, {'address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                          'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                          'blockNumber': 21474469,
                          'data': '0x000000000000000000000000000000000000000000037d72c7dff11239c88c00',
                          'topics': [
                              '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                              '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                              '0x0000000000000000000000008cd7fea8630a030ea16009914b6f8a79bea05c30'],
                          'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                          },
                     {'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                      'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                      'blockNumber': 21474469,
                      'data': '0x000000000000000000000000000000000000000000000000000000004483e084',
                      'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                 '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                                 '0x00000000000000000000000045dcec86a1eded2af0858396f26619be801677aa'],
                      'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                      }, {'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                          'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                          'blockNumber': 21474469,
                          'data': '0x0000000000000000000000000000000000000000000000000000000001a29c10',
                          'topics': [
                              '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                              '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                              '0x000000000000000000000000af2a7f37df0fcad99db3714e6283ff10a56db092'],
                          'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                          },
                     {'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                      'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                      'blockNumber': 21474469,
                      'data': '0x00000000000000000000000000000000000000000000000000000004faf77d10',
                      'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                 '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                                 '0x00000000000000000000000066a9e3db3bac9a4fc151bcbab4dde98f7b3932e1'],
                      'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                      }, {'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                          'blockHash': '0x78b27b8398e950321fb3fc8d3729d96e102c40e9d1e599d07bdf442c8cf5fab8',
                          'blockNumber': 21474469,
                          'data': '0x000000000000000000000000000000000000000000000000000000001dcd6500',
                          'topics': [
                              '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                              '0x000000000000000000000000d91efec7e42f80156d1d9f660a69847188950747',
                              '0x00000000000000000000000023f6cd8c3e6f5defd7aeecfbad1f8462b92717f7'],
                          'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                          }],
            'maxFeePerGas': 13935589678, 'maxPriorityFeePerGas': 1000000000, 'nonce': 214310, 'status': True,
            'to': '0xd91efec7e42f80156d1d9f660a69847188950747',
            'transactionHash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
            'type': 2, 'value': '0', }
