import pytest


@pytest.fixture
def block_head() -> dict:
    return {
        'code': '0',
        'data': [
            {
                'chainFullName': 'BNB Chain',
                'chainShortName': 'BSC',
                'blockList': [
                    {
                        'height': '4646786',
                    }
                ]
            }
        ]
    }


@pytest.fixture
def bsc_babydoge_transaction() -> dict:
    return {
        'code': '0',
        'data':
            [{
                'chainFullName': 'BNB Chain',
                'chainShortName': 'BSC',
                'limit': '20',
                'page': '1',
                'totalPage': '3',
                'transactionLists': [
                    {
                        'amount': '47400000',
                        'blockHash': '0x614124e3a00a00e0e95f3841107268f60532a187766441a307a9630cfabb6641',
                        'from': '0xe2fc31f816a9b94326492132018c3aecc4a93ae1',
                        'height': '49941287',
                        'isFromContract': False,
                        'isToContract': False,
                        'methodId': '',
                        'state': 'success',
                        'to': '0x7d403942336a95fd31cbbf24ff7ad82529519861',
                        'tokenContractAddress': '0xc748673057861a797275cd8a068abb95a902e8de',
                        'transactionSymbol': 'BabyDoge',
                        'transactionTime': '1747655308000',
                        'txId': '0xf4137cca336c7ec4df464a92a9338734669bf28ee7e407019dc74c07bb56b60f',
                        'challengeStatus': '',
                    }],
                'msg': ''
            }]}


@pytest.fixture
def bsc_usdt_transaction() -> dict:
    return {'code': '0', 'data': [
        {'chainFullName': 'BNB Chain', 'chainShortName': 'BSC', 'limit': '20', 'page': '1', 'totalPage': '13',
         'transactionLists': [
             {'amount': '2.27', 'blockHash': '0x0282f282ab2c182eb555a82a5ea846af49b03dd306b1bb19cdb9351710200937',
              'challengeStatus': '', 'from': '0xa86628d6e021f42f41c989b618286a00878f67bb', 'height': '49938037',
              'isFromContract': False, 'isToContract': False, 'l1OriginHash': '', 'methodId': '', 'state': 'success',
              'to': '0xc195143bc42909274c1bc1696989876d53d74aba',
              'tokenContractAddress': '0x55d398326f99059ff775485246999027b3197955', 'tokenId': '',
              'transactionSymbol': 'USDT', 'transactionTime': '1747650432000', 'txFee': '',
              'txId': '0x31263bd9eb3da2ff8d7a4c584f4c2f4ca3128a0194d1c52f13f1891724b8af6e'}]}], 'msg': ''}


@pytest.fixture
def bsc_native_transaction() -> dict:
    return {
        'code': '0',
        'data':
            [
                {
                    'chainFullName': 'BNB Chain',
                    'chainShortName': 'BSC',
                    'limit': '20',
                    'page': '1',
                    'totalPage': '500',
                    'transactionLists': [
                        {
                            'amount': '0.000425117490378252',
                            'blockHash': '0xb61660422ad6ce1de6aea7ff11b064d5281202da225d1110cc397a466ec132c8',
                            'challengeStatus': '',
                            'from': '0x4848489f0b2bedd788c696e2d79b6b69d7484848',
                            'height': '49943753',
                            'isFromContract': False,
                            'isToContract': False,
                            'l1OriginHash': '',
                            'methodId': '',
                            'state': 'success',
                            'to': '0x18dd8c2f3ebef1948a07ece5c72f4ea43f2e6cd9',
                            'tokenContractAddress': '',
                            'tokenId': '',
                            'transactionSymbol': 'BNB',
                            'transactionTime': '1747659007000',
                            'txFee': '0',
                            'txId': '0xccec618a117649a19645fbcb3547b56a0e0e9f2a6fc987c181fc0f1a1bb715b6',
                        }]}],
        'msg': ''
    }
