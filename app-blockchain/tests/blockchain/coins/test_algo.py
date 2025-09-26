from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from django.core.cache import cache

from exchange.blockchain.api.algorand.algo_rpc import RandLabsRPC, AlgoNodeRPC, PureStakeRPC, BloqCloudRPC
from exchange.blockchain.algo import AlgoBlockchainInspector
from exchange.blockchain.validators import validate_algo_address


class TestAlgorandBlockchainInspector(TestCase):

    dummy_address = 'GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE'

    def test_validate_addresses(self):
        result = validate_algo_address(self.dummy_address)
        self.assertTrue(result)

        bad_length_address = self.dummy_address[1:]
        result = validate_algo_address(bad_length_address)
        self.assertFalse(result)

        bad_checksum_address = self.dummy_address[:-1] + 'U'
        result = validate_algo_address(bad_checksum_address)
        self.assertFalse(result)

        bad_b32_address = self.dummy_address[:-1] + '1'
        result = validate_algo_address(bad_b32_address)
        self.assertFalse(result)

    def test_get_api(self):
        apis = {'rand_labs': RandLabsRPC, 'algo_node': AlgoNodeRPC,
                'pure_stake': PureStakeRPC, 'bloq_cloud': BloqCloudRPC}

        for api in apis.keys():
            res = AlgoBlockchainInspector.get_algo_api(api)
            self.assertEqual(res, apis.get(api).get_api())

    def test_get_balance(self):
        dummy_resp = {"account":{"address":"GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE","amount":500000,"amount-without-pending-rewards":500000,"created-at-round":21298441,"deleted":False,"pending-rewards":0,"reward-base":218288,"rewards":0,"round":21299595,"sig-type":"sig","status":"Offline","total-apps-opted-in":0,"total-assets-opted-in":0,"total-created-apps":0,"total-created-assets":0},"current-round":21299595}

        api = PureStakeRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallets_balance_algo_rpc([self.dummy_address])

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        AlgoBlockchainInspector.USE_EXPLORER_BALANCE_ALGO = 'algo_node'

        api = AlgoNodeRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallets_balance_algo_rpc([self.dummy_address])
        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        AlgoBlockchainInspector.USE_EXPLORER_BALANCE_ALGO = 'rand_labs'

        api = RandLabsRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallets_balance_algo_rpc([self.dummy_address])

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        AlgoBlockchainInspector.USE_EXPLORER_BALANCE_ALGO = 'bloq_cloud'

        api = BloqCloudRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallets_balance_algo_rpc([self.dummy_address])

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

    def test_get_transactions(self):
        dummy_resp = {"current-round":21299941,"next-token":"fAFFAQAAAAAjAAAA","transactions":[{"close-rewards":0,"closing-amount":0,"confirmed-round":21299580,"fee":1000,"first-valid":21299578,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","id":"5JI6E6UKBFDDE2GOMATHEGBQGKOUKLYG7VI6N4RQKLS6KRAWALQQ","intra-round-offset":35,"last-valid":21300578,"note":"Y29tbWl0","payment-transaction":{"amount":39499000,"close-amount":0,"receiver":"6BFMCUY4NBARUYMWVNK5THL5QYDQFX7BYZB2X7Q3T37WKOP3WFN4EPKJPY"},"receiver-rewards":0,"round-time":1653848175,"sender":"GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE","sender-rewards":0,"signature":{"sig":"HCnYaRnoDGtxVQyGrjxyivl8sai7KFYCzslsPGYOR7bwUZXWx068jm/DYU654h6tRWL6EQFhOjoWeVF6EXfRAw=="},"tx-type":"pay"}]}

        api = AlgoNodeRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallet_transactions_algo_rpc(self.dummy_address)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        AlgoBlockchainInspector.USE_EXPLORER_TRANSACTION_ALGO = 'pure_stake'

        api = PureStakeRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallet_transactions_algo_rpc(self.dummy_address)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        AlgoBlockchainInspector.USE_EXPLORER_TRANSACTION_ALGO = 'rand_labs'

        api = RandLabsRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallet_transactions_algo_rpc(self.dummy_address)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        AlgoBlockchainInspector.USE_EXPLORER_TRANSACTION_ALGO = 'bloq_cloud'

        api = BloqCloudRPC().get_api()
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = AlgoBlockchainInspector.get_wallet_transactions_algo_rpc(self.dummy_address)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

    def test_get_block(self):
        cache.delete('latest_block_height_processed_algo')
        dummy_block_resp = {"current-round":21308796,"next-token":"ciVFAQAAAAArAAAA","transactions":[{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":1000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","group":"H3RbUbFtMJBpMTKFgnjNBwdi3OhX8hpnv7e7wYolYWU=","id":"6EXU4PA3DHUKNGUEA6VPTV7WE7F7VNBYPKQYVYWWVML6FZYRSJ6Q","intra-round-offset":11,"last-valid":21308788,"note":"E0ko8xcpWzdlKCVpRXQq0IRfcLqGxMorufQJyaSaofc=","payment-transaction":{"amount":2000,"close-amount":0,"receiver":"2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},"receiver-rewards":0,"round-time":1653888146,"sender":"MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE","sender-rewards":0,"signature":{"sig":"mvXLYGyF/l8bli50NAZ1nTwTtMHDEWCnk+DW4jKYNV1CGQ1v5QlOY9+XdSvHM4usfykcNnghF6y0rHDJvE2RDQ=="},"tx-type":"pay"},{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":1000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","group":"j8pRocnYhmj8gO6b5btkveYaEsNqvEvD4l36h8Eo+kU=","id":"4C43VJ2AAZUH3ZFCG4I6GUGILERPU542CBYX5JWHML4V62N57ECQ","intra-round-offset":15,"last-valid":21308788,"note":"qPprK8Y6BNl5GTpW20E1wyTPsE5J/fSgBOlccyaIREk=","payment-transaction":{"amount":2000,"close-amount":0,"receiver":"L6ENK7LD47SJZX6VQOHDZFM7PK6ZHI5436ELEVVEULQ5OAPYI3SSFXYLSY"},"receiver-rewards":0,"round-time":1653888146,"sender":"MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE","sender-rewards":0,"signature":{"sig":"AM9uML1kdj8VHO4axdwLUlVlaE5oU+6UXpxes0gOU4ftVtbj6HYN32HcymJqRwhFIz1UPsgHNwPB5yxk2me/Aw=="},"tx-type":"pay"},{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":1000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","group":"OL80f0YK+N4tk02wkarElpq+u8OPtGj4y0EkRjBSBcM=","id":"YYGC7ISQBZNARODKOS6WJWFV2HY5LGIZB7H7PBXI732VULOUSAVA","intra-round-offset":19,"last-valid":21308788,"note":"35Wphzb4Mktfl6mpqo29+TqXyFMR8ZKV+YJbKoBrFCY=","payment-transaction":{"amount":2000,"close-amount":0,"receiver":"2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},"receiver-rewards":0,"round-time":1653888146,"sender":"MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE","sender-rewards":0,"signature":{"sig":"Ruu2LQI56+9oM2m/OlPwYZaI6m3knrQK0NxKPlu5OqgHln2ed2DXW/YA6tJIM9nn7UQzmFE7TEHP9Em5iyV3Ag=="},"tx-type":"pay"},{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":1000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","group":"kuTuMOxOcP+nBdxI5GTCtRGECuqknpgQlPdIvgN2X8M=","id":"U6RVXYDSS2CWY3R3P4RPDIANRGCV22CVM7OWIQCPQUJ5O2UUEKMQ","intra-round-offset":22,"last-valid":21308788,"note":"406nv5M0DVDsl83qapeqLiyY6BEu+iJOH6Qxp5HRpS4=","payment-transaction":{"amount":2000,"close-amount":0,"receiver":"2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},"receiver-rewards":0,"round-time":1653888146,"sender":"MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE","sender-rewards":0,"signature":{"sig":"y3zCiwx+BPomyNQjDCNShooROo+po+zpjZ+lr9nTZMBVW1Qx9evrm83OXLmkMsHSg18b7FUWojxAh236StCmAA=="},"tx-type":"pay"},{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":247000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","id":"UYBO35UI4MUJGPFG6H2ACJXTABQIYRXF3YF7SKL2S2J76WPYVRAA","intra-round-offset":36,"last-valid":21309784,"payment-transaction":{"amount":1000000,"close-amount":0,"receiver":"M2LCDSDNVYUPN2BBCKHBTCKREV7J4DGJSLZDJLYINGKIQ4EVOO5HZ2ZH54"},"receiver-rewards":0,"round-time":1653888146,"sender":"JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I","sender-rewards":0,"signature":{"sig":"UFHZKt/vN/MAY5oVX3eMIo8JTgZhMbhw3XakUtuO1Rhxnyl3+n3U2nVE49P0izDxJ2ARsjq5rw3VUxriGc9IDQ=="},"tx-type":"pay"},{"close-rewards":0,"closing-amount":0,"confirmed-round":21308786,"fee":247000,"first-valid":21308784,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","id":"Q4A4N5DWHVZJLSHWW3KGVUFGBWAPYJLLEIQALJV2RM62SH6OYSIA","intra-round-offset":43,"last-valid":21309784,"payment-transaction":{"amount":100000,"close-amount":0,"receiver":"G3H5USFI3OJ25IEVM6GED5EBMUJDXMZPYMJ44BSSJHJTUQKOAAVSA3N43U"},"receiver-rewards":0,"round-time":1653888146,"sender":"JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I","sender-rewards":0,"signature":{"sig":"xXxTQO3cXEHA07LrHrs6qRZJnI/kKv0ldO5csrbwMn+upi35KPbQ7B28rqIVS6gMpoI3pws1G1ONHWLMihRZAA=="},"tx-type":"pay"}]}
        dummy_block_head_resp = {"current-round":21308825,"next-token":"lyVFAQAAAAAcAAAA","transactions":[{"close-rewards":0,"closing-amount":0,"confirmed-round":21308823,"fee":1000,"first-valid":21308821,"genesis-hash":"wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=","genesis-id":"mainnet-v1.0","id":"NWTZDWUG4OAYEDFVCFHTALOO5Q7XZO4PFKVNO533EUZDQFS4QIHQ","intra-round-offset":28,"last-valid":21309821,"payment-transaction":{"amount":403000,"close-amount":0,"receiver":"VBZEOQ3VDD73BBK3KLPLI2QPNQN55FFNB4IM3UFNUJRZBKHXOLHIMX55Z4"},"receiver-rewards":0,"round-time":1653888305,"sender":"RDKDV7CVOXLHO2OXBJCSLFDNJBTENDVT3LMFRYTZS7EKIAMAXZKBL42KHA","sender-rewards":0,"signature":{"sig":"4A6IoJ8drs3kWP1eKXkQd0fjJH2IYBxOX7atiNKk//VJCmNLoqx0mNA7AH78OZYOibmEgDuWszLaiYnLDTvBAQ=="},"tx-type":"pay"}]}

        expected_input_addresses = {'JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I'}
        expected_output_addresses = {'M2LCDSDNVYUPN2BBCKHBTCKREV7J4DGJSLZDJLYINGKIQ4EVOO5HZ2ZH54'}

        chosen_address_for_tx_info = 'JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I'
        expected_tx_info_for_chosen_address = {103: [{'tx_hash': 'UYBO35UI4MUJGPFG6H2ACJXTABQIYRXF3YF7SKL2S2J76WPYVRAA', 'value': Decimal('1')}]}

        api = RandLabsRPC().get_api()
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        tx_address, tx_info, _ = AlgoBlockchainInspector.get_latest_block_addresses()

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        AlgoBlockchainInspector.USE_EXPLORER_BLOCKS = 'pure_stake'

        api = PureStakeRPC().get_api()
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = AlgoBlockchainInspector.get_latest_block_addresses()

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        AlgoBlockchainInspector.USE_EXPLORER_BLOCKS = 'algo_node'

        api = AlgoNodeRPC().get_api()
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = AlgoBlockchainInspector.get_latest_block_addresses()

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        AlgoBlockchainInspector.USE_EXPLORER_BLOCKS = 'bloq_cloud'

        api = BloqCloudRPC().get_api()
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = AlgoBlockchainInspector.get_latest_block_addresses()

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)





