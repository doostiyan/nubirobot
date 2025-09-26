import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from pytz import UTC

from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.filecoin.filecoin_explorer_interface import FilecoinExplorerInterface
from exchange.blockchain.api.filecoin.filecoin_filscan import FilecoinFilscanApi


@pytest.mark.slow
class TestFilscanFilecoinApiCalls(TestCase):
    api = FilecoinFilscanApi
    general_api = FilecoinExplorerInterface.get_api()

    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                            'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna']
    # edit hash because the transactions were old
    hash_of_transactions = ['bafy2bzaced6uqepc62ih7uyalmv3rmzjs3oqynbtxpiqwz3cr4zox5vt2mqws',
                            'bafy2bzaced4vjqvjy6eh6ne64czr6xilplpogehc33og362334lztxxcn57d2']
    # height 3085955
    block_hashes = ['bafy2bzacedtwqndikvo3klgzs6gq3evsql5qt7d7g6dbiamecq2btcybls63w',
                    'bafy2bzacebrtkr5pwasrd2cjqifaympzncplw47l2h5etkq2taksisfeivv5w',
                    'bafy2bzacebuqhd7ptk7svjbc32fpy3e3xy2nclla7kygwqagcvo43jx2sknau']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):
        first_layer_keys = {'account_type', 'account_info','epoch'}
        keys = {'account_id', 'account_address', 'account_type', 'account_balance', 'nonce', 'code_cid',
                'create_time', 'latest_transfer_time', 'eth_address'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result.get('result'), first_layer_keys)
            assert self.check_general_response(
                get_balance_result.get('result').get('account_info').get('account_basic'), keys)
            assert isinstance(get_balance_result, dict)
            assert isinstance(
                get_balance_result.get('result').get('account_info').get('account_basic').get('account_balance'), str)

    def test_get_address_txs_api(self):

        address_keys = {'messages_by_account_id_list', 'total_count','epoch'}
        transaction_keys = {'cid', 'height', 'block_time', 'from', 'to', 'value', 'method_name', 'exit_code'}
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response.get('result'), address_keys)
            assert len(get_address_txs_response) > 0
            if get_address_txs_response.get('result').get('messages_by_account_id_list') is None:
                continue
            for transaction in get_address_txs_response.get('result').get('messages_by_account_id_list'):
                assert self.check_general_response(transaction, transaction_keys)

    def test_get_block_head_api(self):

        blockhead_keys = {'height', 'block_time','base_fee'}
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response.get('result'), blockhead_keys)
        assert type(get_block_head_response.get('result').get('height')) == int
        assert type(get_block_head_response.get('result').get('block_time')) == int

    def test_get_tx_details_api(self):
        first_layer_keys = {'message_basic', 'blk_cids', 'consume_list', 'version', 'nonce', 'gas_fee_cap',
                            'gas_premium', 'gas_limit', 'gas_used', 'base_fee', 'all_gas_fee', 'params_detail',
                            'returns_detail', 'eth_message'}
        transaction_keys = {'cid', 'height', 'block_time', 'from', 'to', 'value', 'method_name', 'exit_code'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert len(get_tx_details_response) != 0
            if get_tx_details_response.get('result').get('MessageDetails') is None:
                continue
            assert self.check_general_response(get_tx_details_response.get('result').get('MessageDetails'),
                                               first_layer_keys)
            assert self.check_general_response(
                get_tx_details_response.get('result').get('MessageDetails').get('message_basic'), transaction_keys)

    def test_get_block_txs_api(self):
        transaction_keys = {'cid', 'height', 'block_time', 'from', 'to', 'value', 'method_name', 'exit_code'}
        for block_hash in self.block_hashes:
            get_block_txs_response = self.api.get_block_txs(block_hash)
            assert len(get_block_txs_response) != 0
            assert len(get_block_txs_response[0].get('result')) != 0
            if get_block_txs_response[0].get('result').get('message_list'):
                for transaction in get_block_txs_response[0].get('result').get('message_list'):
                    assert self.check_general_response(transaction, transaction_keys)


class TestFilscanFilecoinFromExplorer(TestCase):
    api = FilecoinFilscanApi
    currency = Currencies.fil
    addresses_of_account = ['f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy']
    hash_of_transactions = ['bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2',
                            'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye',
                            'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms'
                            ]
    address_txs = ['f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
                   'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq']

    def test_get_balance(self):
        balance_mock_response = [{'result': {'account_type': 'account', 'account_info': {
            'account_basic': {'account_id': 'f01067288', 'account_address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                              'account_type': 'account', 'account_balance': '299045108706312384', 'nonce': 1639,
                              'code_cid': 'bafk2bzacealnlr7st6lkwoh6wxpf2hnrlex5sknaopgmkr2tuhg7vmbfy45so',
                              'create_time': 1684402860, 'latest_transfer_time': 1691140560}}}}]
        self.api.request = Mock(side_effect=balance_mock_response)
        FilecoinExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'FIL': self.addresses_of_account}, Currencies.fil)
        expected_balances = {Currencies.fil: [{'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                                               'balance': Decimal('0.299045108706312384'),
                                               'received': Decimal('0.299045108706312384'),
                                               'sent': Decimal('0'),
                                               'rewarded': Decimal('0')}]}
        assert self.currency in balances.keys()
        expected_values = expected_balances.values()
        expected_merged_list = []
        for sublist in expected_values:
            expected_merged_list.extend(sublist)
        for balance, expected_balance in zip(balances.get(Currencies.fil), expected_merged_list):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {'result': {'block_time': 1691239530, 'height': 3097771}},
            {'result': {'MessageDetails': {'message_basic': {'height': 2349511, 'block_time': 1668791730,
                                                             'cid': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2',
                                                             'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y',
                                                             'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji',
                                                             'value': '1600000000000000000', 'exit_code': 'Ok',
                                                             'method_name': 'Send'}, 'blk_cids': [
                'bafy2bzacedgp6a7dv76dfx5yi2vqaefyg5qaqqf46u3arxyai7byigyhw4z5q',
                'bafy2bzaceciscaefmreqhsqhti2moe45u63msegv5rnh5zxurcaoqto2jaxjk',
                'bafy2bzaceap7i4rzkmsxlfuu7rpsdtx25dv6jwvo4ormzdbte76sesukvfens'], 'consume_list': [
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'to': 'f01245980', 'value': '87326800948',
                 'consume_type': 'MinerTip'},
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'to': 'f099', 'value': '127748553369528',
                 'consume_type': 'BaseFeeBurn'},
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji',
                 'value': '1600000000000000000', 'consume_type': 'Transfer'}], 'version': 0, 'nonce': 112,
                                           'gas_fee_cap': '529990634', 'gas_premium': '164002', 'gas_limit': 532474,
                                           'gas_used': '490568', 'base_fee': '260409471',
                                           'all_gas_fee': '127835880170476', 'params_detail': None,
                                           'returns_detail': None,
                                           'eth_message': '0xda6f6755152e28e757bafa7e707fe2275a9efe015a45be9229d01fa0111346fd'}}},

            {'result': {'block_time': 1691239530, 'height': 3097771}},
            {'result': {'MessageDetails': {'message_basic': {'height': 2349569, 'block_time': 1668793470,
                                                             'cid': 'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye',
                                                             'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                                                             'to': 'f01156883', 'value': '1944530995624041453',
                                                             'exit_code': 'Ok',
                                                             'method_name': 'ProveReplicaUpdates'}, 'blk_cids': [
                'bafy2bzacea6677pkhqexwfufl3q36jocjyepl5h2fm66fihzgogt2tmrr3i6u'], 'consume_list': [
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'to': 'f0126478', 'value': '32605831858704', 'consume_type': 'MinerTip'},
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'to': 'f099', 'value': '37984409005033920', 'consume_type': 'BaseFeeBurn'},
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'to': 'f01156883', 'value': '1944530995624041453', 'consume_type': 'Transfer'}], 'version': 0,
                                           'nonce': 20422, 'gas_fee_cap': '375721897', 'gas_premium': '163343',
                                           'gas_limit': 199615728, 'gas_used': '159983071', 'base_fee': '229045245',
                                           'all_gas_fee': '38017014836892624', 'params_detail': {'Updates': [
                    {'SectorID': 3637, 'Deadline': 2, 'Partition': 0,
                     'NewSealedSectorCID': 'bagboea4b5abca3hsvqr72zalqfrtchlsuoxk4m6z3o7d34yqksvtwwwu2u2yuvb2',
                     'Deals': [16280616], 'UpdateProofType': 3,
                     'ReplicaProof': '0xa44623af884d0a852bd5cc52ee3fcd2dd2f61eea020f8d6d23194758d00e69ff8dc89e81fcef75f73cd0a609e68b2e8983eda78e8a5eb843b7466c91924dcdd931dfa4421f8b60ed1b845409055bddac3df6e7dacb0c0d72e3c7450ba8b2be0a0ce86dd6f1f14f5ea9fddfaf28d44efc98cb265bfc9bd8a202d84dc9381487f333545e0e05d742478a456efdacfebc579077aa5cc790019d168abefc7163343954cd7bec44d43a61c90b00e68f31e2906d4c5a30c91ac44fcdab012ce95fbff6a30df5da159dee8236b1928dcd4d33def75f23b07ad9b0d10483f770c14370bef4b6169e41255c6c02943172dc63e1f9b8edbaab427e3740492c6470ae704620ed2b3878c3bb7d3311461402b9e06d6fb519f21db1a633dc5ad5bbf9a1efe8ec15b0e1b99514193bbf7d2289c26c2df1ee02d750538f7e7f5bb32cfa7a870c720070efd67acc1e1edb361094ccbc87a88fc1ab844abe0a1f41ad51e3e5ca1b20be4a293f0aa9dfc7a13224442a0a4b71a5d61241090c00d343bd5082982b71f78861baac6785b202f4a77461d373804165cde64a4281b272c489df051d3449c93c541bbbf02468fa19e898d7adf056ad9963a618438fe6dbf55cbaf56ce8fdb6245becf09d488b22fc0812764622790765591c1f8684dfbe18c2b6e1d4af65380035bcb010deda452fd5dc88edb92ea384d46ea4f126623190e5b0568d52a2095f6d33f81beba1c41fe252c823752511894bd3072427f2015fc0a533149a3ea203a3f66bfd09347d1e3fcb92bdd4c800a0955d9cec9785daeeefc08248938f0282246728ac5180b5469cbd3d4e87d4e40e75f01fd16f91129e01862a784236443217eb23b856a271057dd8e00dda2e36b19157490919d9c311d06abdc40c99a9a7a3a04d8bc58c2f2fa41456aa8093cba2528c3f39730d6e84da0e66105ff2cf0753d8b57b1a295498c64a4dc2c52eea238b3a996de458392c874bb524724ce8351713e4cbbed2b384341eed7fd2b39988214d943b2ce05cd20bfd45f3bd7206b5c4ce7ed85434637ef5baf947c881d0316d3bbae5ef5887619ed51d03cba960aab3f0524657948154e33a01867f7b7c6733be12f0c85a16c194d91e30f0ba54601066d85babfaf4c612d885e0cb24ef8df22b095b95909a3cb3237a315b64b0025acccf9077c3e978bb9d94a61bf6084035c0cc840f630708db3942cd760a740978b44de3398ae07881dd592b60dcb9fc704e5cf5ec2da3b5a217b79168771beb6c870f8ace44867387b72d57f0206596944dc5ce71581ddacc305cf6d9e7884e6b30dc764bb226e4eee1d285eb44966549f868b3904b229b255ea409287e1383a74ec8710d48872f85aec4fa6a2f5b23a90e7f218d123bbb08b739a43f482f3a9f0209383e1a65d50cf05bb9a1cd5bb936729c61621ceaa585c02c89dd6efb9910e56206d4baa7c7115474dbe68129f0aa02c16ad87f8f93977f7d95281b871496178dc5dddf4d9b8cb86bb17f6c2a5698a407173a93549b63b7966bd74c49a4315b3ce4b0d27e4a20da7dbbc098309666913d7d41218913818c23591e89ef7213a661088b2cc254654af72c463acc1df24eaab391f3548f70bd214e3cc7cea24eba6ad87892bcf9270c7659e34dc79277df4362cb24dc61eb9ea402d16e2b9085c2d5994e862144efdfe9e0102f4db6cb4c86a91d19f0ba7dda477f48a32386a09c9d981a99f76a4a1ef322d1965bd7a05a5cfcf9d64c9a5cebefbff47a5d151f57fa226faed5d43b8e8400f2c43385d9358cd3a128dd227134696327476a19101afca5c3b768ddec2e85bbcb1f12a9bb650cf8e53b5f379fe6f23bfadf6443b835a2b7aa3799d7d2a6ca40b383b47237fa17cbbc2c0945d1b19606574e69aa60be4bd51bad7bd74b22381fdd899e8e5a19c12769af5a7df0858cbc89ebd1395ef02318abb738546f00a5a119fa37b900c546a1d8249b4a3cdddb82032f5ea31507ed23e2353a3f8b703a1e550233611479546c150776e3cbfb629093578608d8ea24fcfc7e7761686c0b9f98b6596c5ee0d7b89651f102b88809faa74b3d0a7bd4a8b35bc80de230c851f8376ce68819d53e6fba8837a7eb48f27bcb22621e74850ccbc87e51bbe0e762f2f111abc77090490bfa5565f7bdc21a08db17a4ab5a5458ee94b11d49b06ec90474615117194e3453fc549c97a20a668f20619a5101fd7c1c3d1c9bfcdfb666d94c09eb929caee8fef68d96ad3addf51bffb68d9fa21aad2b2ddaa26c4e8405500299aa84e3533c7c29f57d577415700fb3ba6d0587e492f343ec3913ddc81f1633b119730ea3805ebb28b85eab0b6636d23fd03948792271b06270d5904a548349f37387e7eccdbbfe0148d14282fb7bcbbb91e375db1e87bc8227419e84504c26696d0a7b893dd67b18d1dd2d5a054acf5c61b9b904ca2da5f72bcd537e16c45cad84da2adb5ba2f47aa48f97daf183897374dfcf08b8909d91e8e998ecd5a6b9d927b5c6fb36d388c90d0e3c886c930734c783552d50070db0592e7f0464b48d4faacc94c6d8ae2c5a8de3a5fbc464d185981814af8c8284e48583071af4d9aa48d6cdf0761411fa160b4373dfd9e827dd577b9c3e14d86d833e331565245194b9be964c4bcd7f82f2e8762bb61e82e05a6252201f3a3d8fc3cb2e7ec025d1cc575a21f8d1e8891ddea738e1ba725862c3fba8de5698fd28b6db5ccbce262903b711bde92e867b6834c7855c132355e7c91d90adfc8bebbc5e1ba7faaca6228ef730a2222417bb714d7652a34430e9e93de4484af7bdd88697b2a6e31f0780157b15060d71ed3251c84edfd7a1d4b2ad01bf034cd0ca1bd01c9f5bc571a0aaf8c51237b3f23bc838fd7a3d6f9bd535ddfb94be94e34916a3f16c861298a2abf1a21ba1d7b940192b0f3750d50460444ac2ee438e7141a5ba6a5bca9b750d0bb801f6450ac5a4ece46d2ae2e4e26962bf3fc787a9a3e75e544c668b156f5ead0dfb441260e7617584b534fde3ecf703ca15dd9261fade27436e4599077eb789797fa5af86c1b619eb93facadda1f6db394859eef502cb218608a0fb25cc4bc5bb04518be6a80e4c08fde87b423b8766d2a6ae02b9942bea9daf83ea9fb5aea2a058680ea9dbeba7d48ea4044a5b75c88363c6ff322f9832d2d801cd0fb8b6764c0405ac97751ac0eafc82c6fe1de9c6b84e39d9bff442620dc1c5274196a81817ef02331a4743a8408cdaa986470e90c394c298648da38fefc7dcffb669bd66e2eff0de622e131eb9721bc576bb1c9714b8b98a42d0a965a6d435307e9380e70630b196952f9dbcf4751af4d10069e144573f89fdcc33e2d628038c041ba2b2ee8f4f7e569f6d92f7c189b08e54196255a42010d27dc722a18b4739cb2e7094031693adbd7437366624c3c41a07302baf078a6edd9f32ab4264305c0e4d07cb3e3da1aec9a23c67f7b75a82caa911dd7adbe3271f86db69b329d137b55aeb979d625981e1c9e2745a06c96ea8aaca23fffd05856dd27ea946fccb4ca67a9debc0cef3fa56f0cc9ee2fe99656ea7f6c109919d014cb3d917d9204e2a7edb03178d11b88689d230c6aee8b95b344e31dfbf485461915cec6a46ed41d33e48819fef85c7ebde36d9d045ed4cd669a12f663fb8ce1849edc6d6f0eef9247d88b4140ccc7e30d6f90b8a1df9c13f68e526958f400184939b2ca0bd4130422fda906b947eb28a789d96d40ec461e0ecf890b6290a5cebf76c0fbe336f4a68ab9161157ed2715891339597f8a632361463bb5adc2dfab299c69caac847a1406e242371928e1a7d59c726ed60e77471ce31bbfd3abe9f65bbfabbd255930e6b63bb4ea0dcf12da6f793a7c11841d9a3239a9523a58c6b874dc868b3a1daab9e8cdd96f4949dc9f22a5f9dca41fb8a659fcfb80ce8b9fb124edda8889695a61d2b18efe67e42da25359c02f89ab16fd8cb13b8423dda4d87e1470639d869874092298abc3c411cad11520df19a5e575f6d5343b739ffc075fcf6f799b0c5c02b4cab4b4418fe2a625dda0803f769d54af5692407e45e5d966b9f8861484f84e045c49d9494b1561a10c19fb31b8bcfa5653a6bd9b6afe290ba4134eff84e24569254ab4bf2bbab9823f58aece62f00548bb457cf5c0e4821c35c66a85d3a75753105741927adaa24fa26ad518aa268f542d9c593dbf9a60084e4bc961d9fed96ec4503e25f3250bec2560dd56f0f92992e38e67ebf7daf37cc5693dd522dfbcc6a00d943056bdea371fdd1ac552572ecb7c27c0eea00a4de25b237830da1a71bace3f012d78e4d7873dedb6d33de6555302816c46e94ea'}]},
                                           'returns_detail': '3637',
                                           'eth_message': '0x21ae0a94f5291b4df80ecb8657e1a454a5f221af74c8a39af9ab96207db5e182'}}},

            {'result': {'block_time': 1691239530, 'height': 3097771}},
            {'result': {'MessageDetails': {'message_basic': {'height': 2268538, 'block_time': 1666362540,
                                                             'cid': 'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms',
                                                             'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                                                             'to': 'f3qvhtg33nq56e4qunx5cvnj5rzykfwszl6kuvetbd7jqngmf4uzgmlcbxqxbqqy5etuw23dvdbodhgamogdra',
                                                             'value': '5000000000000000000',
                                                             'exit_code': 'SysErrInsufficientFunds(6)',
                                                             'method_name': 'Send'}, 'blk_cids': [
                'bafy2bzaceclq7ns2qhskpotjqmmfwzleoa256heicqwkghelhqcrxkgvigstu',
                'bafy2bzaceammlbygtphzogvxl2okewawglorbs5bj6snfgtxjxoevsqp7265g',
                'bafy2bzaceczkdyq7xfadxnhjbg5dhli6s5yqsvnhiirgxw74iyumwtwdhw7zo'], 'consume_list': [
                {'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                 'to': 'f01086808', 'value': '168309652225', 'consume_type': 'MinerTip'},
                {'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                 'to': 'f099', 'value': '22675406759535', 'consume_type': 'BaseFeeBurn'},
                {'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                 'to': 'f3qvhtg33nq56e4qunx5cvnj5rzykfwszl6kuvetbd7jqngmf4uzgmlcbxqxbqqy5etuw23dvdbodhgamogdra',
                 'value': '5000000000000000000', 'consume_type': 'Transfer'}], 'version': 0, 'nonce': 10223,
                                           'gas_fee_cap': '2029397450', 'gas_premium': '285835', 'gas_limit': 588835,
                                           'gas_used': '477568', 'base_fee': '46054059',
                                           'all_gas_fee': '22843716411760', 'params_detail': None,
                                           'returns_detail': None,
                                           'eth_message': '0xd2ddeecf3a70f5816f58ccb6c86e0d0fa99c26756d37d951b24549fa9cef18c9'}}}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        FilecoinExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.hash_of_transactions, 'FIL')
        expected_txs_details = [{'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2': {
            'hash': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2', 'success': True, 'block': 2349511,
            'date': datetime.datetime(2022, 11, 18, 20, 45, 30, tzinfo=UTC), 'fees': Decimal(
                '0.000127835880170476'), 'memo': None, 'confirmations': 748261, 'raw': None, 'inputs': [],
            'outputs': [], 'transfers': [
                {'type': 'MainCoin', 'symbol': 'FIL', 'currency': Currencies.fil,
                 'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y',
                 'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji', 'value': Decimal('1.600000000000000000'),
                 'is_valid': True, 'token': None}]}},
            {'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye': {'success': False}},
            {'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms': {'success': False}}]

        for expected_tx_details, tx_hash in zip(expected_txs_details, self.hash_of_transactions):
            assert txs_details[tx_hash].get('success') == expected_tx_details[tx_hash].get('success')
        if txs_details[tx_hash].get('success'):
            txs_details[tx_hash]['confirmations'] = expected_tx_details[tx_hash]['confirmations']
        assert txs_details[tx_hash] == expected_tx_details[tx_hash]

    def test_get_address_txs(self):
        address_txs_mock_responses = [
            {'result': {'block_time': 1691239530, 'height': 3097771}},
            {'result': {'messages_by_account_id_list': None, 'total_count': 0}},
            {'result': {'block_time': 1691239530, 'height': 3097771}},
            {'result': {'messages_by_account_id_list': [{'height': 3071983, 'block_time': 1690465890,
                                                         'cid': 'bafy2bzacebtfuwy7s2s23jv3xai2zixrdgteuysl2ilvthklygbjothfkyo22',
                                                         'from': 'f3xcunsu54moxra5ltoteyzu2td5y7nllgqcgz5wn3rjzplsgywcdtiv4j2kpfjioz3js3w5c356aniwsvlwmq',
                                                         'to': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'value': '1000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 3036360, 'block_time': 1689397200,
                                                         'cid': 'bafy2bzacebozv6xekmwf7emayej2kgx2xwthfz7mpp33ewudqawl37mue4emk',
                                                         'from': 'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna',
                                                         'to': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'value': '7500000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 3031947, 'block_time': 1689264810,
                                                         'cid': 'bafy2bzaceawp557ibrih7pjcexg4m7gay2fimsynnaiu6c2twd34dhyfgjukc',
                                                         'from': 'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna',
                                                         'to': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'value': '5000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 3028679, 'block_time': 1689166770,
                                                         'cid': 'bafy2bzacedxucijsr7runk3m6qgc2oarwh7wijyod34ab2ls5ls4td3dkf33k',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f1f3n6kaqpvdenbprg2oikh6mnkv6oekbjhyj3yii',
                                                         'value': '10000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 3025912, 'block_time': 1689083760,
                                                         'cid': 'bafy2bzaceb5m2uwuq22csuypjsa5cm2r3fa57chl4pn4ke45rag3asqpoopbq',
                                                         'from': 'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna',
                                                         'to': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'value': '4800000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2944747, 'block_time': 1686648810,
                                                         'cid': 'bafy2bzaceajy35pobupeschsyoeiwmzlakefwhurbd2qeancxxymmezv7mbl4',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'value': '500000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2937940, 'block_time': 1686444600,
                                                         'cid': 'bafy2bzacebana7jkfsxq4wn63dapefauhxdsnye2yfbmdw2n6ni63odecet6o',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'value': '3000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2937896, 'block_time': 1686443280,
                                                         'cid': 'bafy2bzacea4hyztobpxhmmqjxr5fdq3qycl4btfckomhtjbky3gnpkrttime4',
                                                         'from': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'to': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'value': '3000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2935165, 'block_time': 1686361350,
                                                         'cid': 'bafy2bzacebmiqehbeef5vodizyylsdrquv4rbijguefn6me7o5iqcb32j73ji',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'value': '200000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2916196, 'block_time': 1685792280,
                                                         'cid': 'bafy2bzaced3lwnimrz7fm6yzniklsj76v5goqqcei5y7ncf26wbzx5ftbs53c',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'value': '2000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'},
                                                        {'height': 2885326, 'block_time': 1684866180,
                                                         'cid': 'bafy2bzacecdflqklq6krfnlkr2ph2hjffx6eovqsbgpxnps5psc5nqimnshcs',
                                                         'from': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
                                                         'to': 'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q',
                                                         'value': '3000000000000000000000', 'exit_code': 'Ok',
                                                         'method_name': 'Send'}], 'total_count': 11}}
        ]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        FilecoinExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [],
            [{'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 3071983, 'confirmations': 25789,
              'details': {},
              'from_address': [
                  'f3xcunsu54moxra5ltoteyzu2td5y7nllgqcgz5wn3rjzplsgywcdtiv4j2kpfjioz3js3w5c356aniwsvlwmq'],
              'hash': 'bafy2bzacebtfuwy7s2s23jv3xai2zixrdgteuysl2ilvthklygbjothfkyo22',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 7, 27, 13, 51, 30, tzinfo=UTC),
              'value': Decimal('1000.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 3036360,
              'confirmations': 61412,
              'details': {},
              'from_address': [
                  'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna'],
              'hash': 'bafy2bzacebozv6xekmwf7emayej2kgx2xwthfz7mpp33ewudqawl37mue4emk',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 7, 15, 5, 0, tzinfo=UTC),
              'value': Decimal('7500.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 3031947,
              'confirmations': 65825,
              'details': {},
              'from_address': [
                  'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna'],
              'hash': 'bafy2bzaceawp557ibrih7pjcexg4m7gay2fimsynnaiu6c2twd34dhyfgjukc',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 7, 13, 16, 13, 30, tzinfo=UTC),
              'value': Decimal('5000.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 3028679,
              'confirmations': 69093,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzacedxucijsr7runk3m6qgc2oarwh7wijyod34ab2ls5ls4td3dkf33k',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 7, 12, 12, 59, 30, tzinfo=UTC),
              'value': Decimal('-10.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 3025912,
              'confirmations': 71860,
              'details': {},
              'from_address': [
                  'f3xgy3nwdgp7amsyhxlxippvf6irdbc43emcrb2wck6g7hp2fcddz3teteto6gpynbavwbzacglcdrqu4xgtna'],
              'hash': 'bafy2bzaceb5m2uwuq22csuypjsa5cm2r3fa57chl4pn4ke45rag3asqpoopbq',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 7, 11, 13, 56, tzinfo=UTC),
              'value': Decimal('4800.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2944747,
              'confirmations': 153025,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzaceajy35pobupeschsyoeiwmzlakefwhurbd2qeancxxymmezv7mbl4',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 6, 13, 9, 33, 30, tzinfo=UTC),
              'value': Decimal('-500.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2937940,
              'confirmations': 159832,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzacebana7jkfsxq4wn63dapefauhxdsnye2yfbmdw2n6ni63odecet6o',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 6, 11, 0, 50, tzinfo=UTC),
              'value': Decimal('-3000.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2937896,
              'confirmations': 159876,
              'details': {},
              'from_address': [
                  'f3vn37ckukoekacrpxobhip6zbykfh2hx6syxiic7oun7ktrwhwqwktheuqbsqqub4zjf4fsi3rzaxikr3ty5q'],
              'hash': 'bafy2bzacea4hyztobpxhmmqjxr5fdq3qycl4btfckomhtjbky3gnpkrttime4',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 6, 11, 0, 28, tzinfo=UTC),
              'value': Decimal('3000.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2935165,
              'confirmations': 162607,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzacebmiqehbeef5vodizyylsdrquv4rbijguefn6me7o5iqcb32j73ji',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 6, 10, 1, 42, 30, tzinfo=UTC),
              'value': Decimal('-200.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2916196,
              'confirmations': 181576,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzaced3lwnimrz7fm6yzniklsj76v5goqqcei5y7ncf26wbzx5ftbs53c',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 6, 3, 11, 38, tzinfo=UTC),
              'value': Decimal('-2000.000000000000000000')},
             {'address': 'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq',
              'block': 2885326,
              'confirmations': 212446,
              'details': {},
              'from_address': [
                  'f3qehbsnsnyie332jnf4xoaudgo2exgjetghx6knl3rg6i5q2qvkhm5ocvruhsp353kzatqx7gmcpnz4v3bswq'],
              'hash': 'bafy2bzacecdflqklq6krfnlkr2ph2hjffx6eovqsbgpxnps5psc5nqimnshcs',
              'huge': False,
              'invoice': None,
              'contract_address': None,
              'is_double_spend': False,
              'tag': None,
              'timestamp': datetime.datetime(2023, 5, 23, 18, 23, tzinfo=UTC),
              'value': Decimal('-3000.000000000000000000')},

             ]
        ]

        for address, expected_address_txs in zip(self.address_txs, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.fil, 'FIL')
            assert len(expected_address_txs) == len(address_txs.get(Currencies.fil))
            if len(expected_address_txs) == 0 and len(address_txs.get(Currencies.fil)) == 0:
                continue
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.fil)):
                assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx

    def test_get_block_txs(self):
        cache.delete('latest_block_height_processed_fil')
        block_txs_mock_responses = [
            {'result': {'block_time': 1691307090, 'height': 3100023}},
            {'result': {'tipset_list': [{'height': 3100019, 'block_basic': [
                {'height': 3100019, 'cid': 'bafy2bzaceaeshro3hpeanoedtz4kn4gg4o3l6dmwfmmqynqlxybksqdj2juwg',
                 'block_time': 1691306970, 'miner_id': 'f01228000', 'messages_count': 70,
                 'reward': '13076150748278489029'},
                {'height': 3100019, 'cid': 'bafy2bzacebiiw7j5g5ykaunh3mvezx72j2jeauwxdcw2opqfzouy2k3q4qw3e',
                 'block_time': 1691306970, 'miner_id': 'f01245980', 'messages_count': 57,
                 'reward': '13082140058179474859'},
                {'height': 3100019, 'cid': 'bafy2bzacebzmpjmnrbyjatjya655add2iujrffu55utqvjyo66ipas5jcifhk',
                 'block_time': 1691306970, 'miner_id': 'f0144528', 'messages_count': 71,
                 'reward': '13090135566209766454'},
                {'height': 3100019, 'cid': 'bafy2bzacedkdpvvtxjbrn4jkhth4xiqfkh6b7etw6nvz24fe6z7eui7q3tcgw',
                 'block_time': 1691306970, 'miner_id': 'f01680940', 'messages_count': 83,
                 'reward': '13072845074818532735'},
                {'height': 3100019, 'cid': 'bafy2bzaceaj5qhmv4lwgzrgrlkqhzmsh2eeyk563c2icrbsxhciailu3srluc',
                 'block_time': 1691306970, 'miner_id': 'f01775037', 'messages_count': 86,
                 'reward': '13084988486361627033'},
                {'height': 3100019, 'cid': 'bafy2bzacebfvnzokys2fgsnqbpfjtvdrgfsxgl227tqlau7zyk64ldxtql2b6',
                 'block_time': 1691306970, 'miner_id': 'f01860256', 'messages_count': 96,
                 'reward': '13073378830102859807'},
                {'height': 3100019, 'cid': 'bafy2bzaceas6mhsbblzg37swa3aquhqrwqxbm53d3axn6oa5zxfhukji3wkhu',
                 'block_time': 1691306970, 'miner_id': 'f01869529', 'messages_count': 81,
                 'reward': '13075253563535638396'},
                {'height': 3100019, 'cid': 'bafy2bzacebfdf3ysh3mfhbhc45akd3ztvuopcrfgqslbfyfjxl2m3drz2jyk6',
                 'block_time': 1691306970, 'miner_id': 'f01914977', 'messages_count': 70,
                 'reward': '13074324285499571691'},
                {'height': 3100019, 'cid': 'bafy2bzacecwj4lzaig26d74s4g4yhch4jnr5ho753wg2rsbjsc23562vkooam',
                 'block_time': 1691306970, 'miner_id': 'f021525', 'messages_count': 64,
                 'reward': '13073218081263182051'},
                {'height': 3100019, 'cid': 'bafy2bzaced32mtgwxtf7k472hofwrinbnb7fv74rl6sxx2wgavmyk7wzs5pq6',
                 'block_time': 1691306970, 'miner_id': 'f083729', 'messages_count': 65,
                 'reward': '13075271993652224643'}],
                                         'min_ticket_block': 'bafy2bzaceaeshro3hpeanoedtz4kn4gg4o3l6dmwfmmqynqlxybksqdj2juwg'}],
                        'total_count': 1}},
            {'result': {'message_list': [{'height': 3100019, 'block_time': 1691306970,
                                          'cid': 'bafy2bzacea52fayacxy7s5fglzq2yyfuehutdnfjoq7fhbot6lmfvdmjchtzs',
                                          'from': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'to': 'f1oalx3iozffplpg2nsredumgo3nmmld4zklvtndy',
                                          'value': '189199000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 1}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            #
            {'result': {'tipset_list': [{'height': 3100020, 'block_basic': [
                {'height': 3100020,
                 'cid': 'bafy2bzacedx4mgqy6lclcggepvfbdpzz45ytpfkakowrhd75cinmbpp7rlfmq',
                 'block_time': 1691307000, 'miner_id': 'f01693299', 'messages_count': 111,
                 'reward': '13077244820026267639'}, {'height': 3100020,
                                                     'cid': 'bafy2bzacecfqj6tt75v4wjyv5mv6ansnt7gio4xf5ktqojli25u45nkqmyaqs',
                                                     'block_time': 1691307000,
                                                     'miner_id': 'f01698807',
                                                     'messages_count': 109,
                                                     'reward': '13072952237835877713'},
                {'height': 3100020,
                 'cid': 'bafy2bzacedkooboxijxercuemlw6xchfafnlk4dmphe3uwut542xziolnls6i',
                 'block_time': 1691307000, 'miner_id': 'f01985775', 'messages_count': 74,
                 'reward': '13089440457411835822'}],
                                         'min_ticket_block': 'bafy2bzacedx4mgqy6lclcggepvfbdpzz45ytpfkakowrhd75cinmbpp7rlfmq'}],
                        'total_count': 1}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100020, 'block_time': 1691307000,
                                          'cid': 'bafy2bzaceatr6d7twviu7a2dexgrumfjgmbr6cxvcviqyru5uyjclckcq6jns',
                                          'from': 'f1ybp6crbyfjm3umeecyqbj5d3uvgxktecw6h7wwa',
                                          'to': 'f1fgrzwz6e4hvohnom4gvtqbt2rqrdupikwlkucfy',
                                          'value': '8720000000000000000', 'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 1}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'tipset_list': [{'height': 3100021, 'block_basic': [
                {'height': 3100021,
                 'cid': 'bafy2bzaced57arz5c2ahkgetanezuliyefrrftfkuz3lapbxshhsyow4qwyb4',
                 'block_time': 1691307030, 'miner_id': 'f01852023', 'messages_count': 91,
                 'reward': '13072879313299894973'}, {'height': 3100021,
                                                     'cid': 'bafy2bzacecwqi7ozgge2pc3hlmmrx4swhs7btahvakbvseqihmqrklzd6o3es',
                                                     'block_time': 1691307030,
                                                     'miner_id': 'f01566485',
                                                     'messages_count': 97,
                                                     'reward': '13074186869687861767'},
                {'height': 3100021,
                 'cid': 'bafy2bzacealonj4si7bsme2zbt7b2onuyqmhee3jb7442fbhvzsknyimuqhk6',
                 'block_time': 1691307030, 'miner_id': 'f01662887', 'messages_count': 125,
                 'reward': '13081987327968948300'}, {'height': 3100021,
                                                     'cid': 'bafy2bzacedchcixsaguz3r7lmygxq4zpppaosjujbo5ve6aqitspt3e77oob6',
                                                     'block_time': 1691307030,
                                                     'miner_id': 'f01909705',
                                                     'messages_count': 85,
                                                     'reward': '13078140398883802170'},
                {'height': 3100021,
                 'cid': 'bafy2bzacebjndjbndk7ssr5pjt3spchd3atkggorjgs6ggi7hrugehup3qr2y',
                 'block_time': 1691307030, 'miner_id': 'f01989888', 'messages_count': 120,
                 'reward': '13076617150506648017'}, {'height': 3100021,
                                                     'cid': 'bafy2bzacedwxfdnyyqnqu2zt734ikwuvdplcwcfxmqbxhlzykhnsndiqtfxok',
                                                     'block_time': 1691307030,
                                                     'miner_id': 'f020522',
                                                     'messages_count': 106,
                                                     'reward': '13076140797965123463'},
                {'height': 3100021,
                 'cid': 'bafy2bzacebvkzaryahvob6tetradueqjzs7yp2st7u4kblgmwicln2clrmyyy',
                 'block_time': 1691307030, 'miner_id': 'f02052510', 'messages_count': 94,
                 'reward': '13091055608655801959'}, {'height': 3100021,
                                                     'cid': 'bafy2bzaceco3v2sv5hjzbuaqumcsdsu4ehnmxrziakv6pkxl2ly5uwdm32ede',
                                                     'block_time': 1691307030,
                                                     'miner_id': 'f0835180',
                                                     'messages_count': 112,
                                                     'reward': '13073006555920016553'}],
                                         'min_ticket_block': 'bafy2bzaced57arz5c2ahkgetanezuliyefrrftfkuz3lapbxshhsyow4qwyb4'}],
                        'total_count': 1}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                                                   'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '107469614033901198742',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                          'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                          'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'value': '1836544371471789005446', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 3}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacebn4fygpspxwe7y4cqg7qyxpqbcnp5yiwc2gnejypiiotphybjjwa',
                                                                   'from': 'f1pxfh43a7vgctpmkqvaiydgelkiqfkpfkzq23y6y',
                                                                   'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                                                   'value': '103999980500000000000',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                          'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                          'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'value': '107469614033901198742', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                                                   'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '1836544371471789005446',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 4}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                                                   'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '1836544371471789005446',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 2}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                                                   'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '107469614033901198742',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                          'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                          'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'value': '1836544371471789005446', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 3}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                                                   'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '107469614033901198742',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                          'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                          'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'value': '1836544371471789005446', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 3}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                                          'from': 'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                          'to': 'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                          'value': '300000000000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                                                   'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '107469614033901198742',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 2}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100021, 'block_time': 1691307030,
                                          'cid': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                                          'from': 'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                          'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                          'value': '107469614033901198742', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100021, 'block_time': 1691307030,
                                                                   'cid': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                                                                   'from': 'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                                                   'to': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                                   'value': '1836544371471789005446',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 2}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'tipset_list': [{'height': 3100022, 'block_basic': [
                {'height': 3100022,
                 'cid': 'bafy2bzaceboq47rvbnukbdvo5mqff2b3ehz3mhgs7qxd2pe442hb65c42dxha',
                 'block_time': 1691307060, 'miner_id': 'f01874748', 'messages_count': 30,
                 'reward': '13091032978346381978'}, {'height': 3100022,
                                                     'cid': 'bafy2bzacedkd2o3m2qjuhe5of5caz45gwtxegli6mmhoz4c3kjihvqk6ftfza',
                                                     'block_time': 1691307060,
                                                     'miner_id': 'f01415710',
                                                     'messages_count': 91,
                                                     'reward': '13081715142451774443'},
                {'height': 3100022,
                 'cid': 'bafy2bzaceb4v4nrgwr3ivlar7acm4tkybxm7xqvvezxd36pazulnnemwhpagq',
                 'block_time': 1691307060, 'miner_id': 'f01889512', 'messages_count': 105,
                 'reward': '13073097807393776129'}],
                                         'min_ticket_block': 'bafy2bzaceboq47rvbnukbdvo5mqff2b3ehz3mhgs7qxd2pe442hb65c42dxha'}],
                        'total_count': 1}},
            {'result': {'message_list': [{'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacebq4wxl3olin4iujegs3f5pdo6rxne3lwsrwyfqgpt2qdxin2jwim',
                                          'from': 'f1arv62ala37lytdxyjoexdom7j3mmnvswgqqt2aq',
                                          'to': 'f1hs2uamvby6xeijnbx4x6rbyelhl3w6w6q2k7fsa',
                                          'value': '34920851467094855844', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecdhaeqro6zin5dhjz2jbynfvvh36n5r5vlhriik275quymkdsc2w',
                                          'from': 'f1wg7cxxg7zvwm7bdmfytw6mejs2p27qma5r6opwq',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '37998905220000000000', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecllci3dxkzqy6ovk6maxzocfeylkysr7qztl6zl5k5htrgz7q4hk',
                                          'from': 'f1bqdyj4a5pehaf4sgw7pgzckbwvulvnpjcwxfzni',
                                          'to': 'f13sb4pa34qzf35txnan4fqjfkwwqgldz6ekh5trq',
                                          'value': '25535262927388841428', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacedxb34pnmw5tkbi543cqgseyfvs6oq5duvkjt4antxmgq4s7kh3e2',
                                          'from': 'f1k56woowxbbjx2dxycw46g2yoztt7yrv3m3zmraa',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '99999401060000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 4}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacebq4wxl3olin4iujegs3f5pdo6rxne3lwsrwyfqgpt2qdxin2jwim',
                                          'from': 'f1arv62ala37lytdxyjoexdom7j3mmnvswgqqt2aq',
                                          'to': 'f1hs2uamvby6xeijnbx4x6rbyelhl3w6w6q2k7fsa',
                                          'value': '34920851467094855844', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecdhaeqro6zin5dhjz2jbynfvvh36n5r5vlhriik275quymkdsc2w',
                                          'from': 'f1wg7cxxg7zvwm7bdmfytw6mejs2p27qma5r6opwq',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '37998905220000000000', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecllci3dxkzqy6ovk6maxzocfeylkysr7qztl6zl5k5htrgz7q4hk',
                                          'from': 'f1bqdyj4a5pehaf4sgw7pgzckbwvulvnpjcwxfzni',
                                          'to': 'f13sb4pa34qzf35txnan4fqjfkwwqgldz6ekh5trq',
                                          'value': '25535262927388841428', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacedxb34pnmw5tkbi543cqgseyfvs6oq5duvkjt4antxmgq4s7kh3e2',
                                          'from': 'f1k56woowxbbjx2dxycw46g2yoztt7yrv3m3zmraa',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '99999401060000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 4}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacebq4wxl3olin4iujegs3f5pdo6rxne3lwsrwyfqgpt2qdxin2jwim',
                                          'from': 'f1arv62ala37lytdxyjoexdom7j3mmnvswgqqt2aq',
                                          'to': 'f1hs2uamvby6xeijnbx4x6rbyelhl3w6w6q2k7fsa',
                                          'value': '34920851467094855844', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecdhaeqro6zin5dhjz2jbynfvvh36n5r5vlhriik275quymkdsc2w',
                                          'from': 'f1wg7cxxg7zvwm7bdmfytw6mejs2p27qma5r6opwq',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '37998905220000000000', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacecllci3dxkzqy6ovk6maxzocfeylkysr7qztl6zl5k5htrgz7q4hk',
                                          'from': 'f1bqdyj4a5pehaf4sgw7pgzckbwvulvnpjcwxfzni',
                                          'to': 'f13sb4pa34qzf35txnan4fqjfkwwqgldz6ekh5trq',
                                          'value': '25535262927388841428', 'exit_code': 'Ok', 'method_name': 'Send'},
                                         {'height': 3100022, 'block_time': 1691307060,
                                          'cid': 'bafy2bzacedxb34pnmw5tkbi543cqgseyfvs6oq5duvkjt4antxmgq4s7kh3e2',
                                          'from': 'f1k56woowxbbjx2dxycw46g2yoztt7yrv3m3zmraa',
                                          'to': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                          'value': '99999401060000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 4}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'tipset_list': [{'height': 3100023, 'block_basic': [
                {'height': 3100023,
                 'cid': 'bafy2bzaceb2xf4ymyjehgj6spsfh62vrdzhb7pvbmvjqwnzfmy7mmkwpgcfkk',
                 'block_time': 1691307090, 'miner_id': 'f02173949', 'messages_count': 130,
                 'reward': '13076715774265710205'}, {'height': 3100023,
                                                     'cid': 'bafy2bzacedxm53lnj6p6ftbszurwrsipmuj3j3usnghbn5valqrmsck7qmruu',
                                                     'block_time': 1691307090,
                                                     'miner_id': 'f01605773',
                                                     'messages_count': 23,
                                                     'reward': '13072817302379081467'},
                {'height': 3100023,
                 'cid': 'bafy2bzacecsxydumggzyt767xrcan7hmunu5uqi5uiljfxb3vsrqe7ppjr77e',
                 'block_time': 1691307090, 'miner_id': 'f01852023', 'messages_count': 120,
                 'reward': '13088583167569622572'}, {'height': 3100023,
                                                     'cid': 'bafy2bzaceciulcdhnhs24jwjjzlkw2sdrd3wi42wrobadf5275iqmlttu3kw2',
                                                     'block_time': 1691307090,
                                                     'miner_id': 'f01997673',
                                                     'messages_count': 95,
                                                     'reward': '13075089347780452963'}],
                                         'min_ticket_block': 'bafy2bzaceb2xf4ymyjehgj6spsfh62vrdzhb7pvbmvjqwnzfmy7mmkwpgcfkk'}],
                        'total_count': 1}},
            {'result': {'message_list': [{'height': 3100023, 'block_time': 1691307090,
                                          'cid': 'bafy2bzacechkfhi7i2tjugozbq4n657wltzggoqzfqfs34eznfpytrpbban6c',
                                          'from': 'f1h4ssetvnj2vpugsuzptl4swlgfunw7oa3eik54a',
                                          'to': 'f1i5fdnws5kufiyketew3sdc2dvs2pdzyaroqugjy',
                                          'value': '1661945390000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}, {'height': 3100023, 'block_time': 1691307090,
                                                                   'cid': 'bafy2bzacedud26q5rmgzfgvjmi25ntujnsvnjk56eryjmeewaee33wmlp5rf2',
                                                                   'from': 'f3qc5njnb3cjjueyej4tyy6w7ly33ggabfycp7p7m7ssxqdcjdutdf3whtfl6u6lwbklf23gdudoydb3bem7aa',
                                                                   'to': 'f1rqseyjytqgnj2x5v6dn35xsyxyy2akhreuv3tzi',
                                                                   'value': '18390000000000000568',
                                                                   'exit_code': 'Ok', 'method_name': 'Send'}],
                        'total_count': 2}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': [{'height': 3100023, 'block_time': 1691307090,
                                          'cid': 'bafy2bzacechkfhi7i2tjugozbq4n657wltzggoqzfqfs34eznfpytrpbban6c',
                                          'from': 'f1h4ssetvnj2vpugsuzptl4swlgfunw7oa3eik54a',
                                          'to': 'f1i5fdnws5kufiyketew3sdc2dvs2pdzyaroqugjy',
                                          'value': '1661945390000000000000', 'exit_code': 'Ok',
                                          'method_name': 'Send'}], 'total_count': 1}},
            {'result': {'message_list': None, 'total_count': 0}},
            {'result': {'message_list': None, 'total_count': 0}},

        ]
        self.api.request = Mock(side_effect=block_txs_mock_responses)
        settings.USE_TESTNET_BLOCKCHAINS = False
        FilecoinExplorerInterface.block_txs_apis[0] = self.api
        expected_txs_addresses = {'input_addresses': {'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                      'f1k56woowxbbjx2dxycw46g2yoztt7yrv3m3zmraa',
                                                      'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq',
                                                      'f1pxfh43a7vgctpmkqvaiydgelkiqfkpfkzq23y6y',
                                                      'f1bqdyj4a5pehaf4sgw7pgzckbwvulvnpjcwxfzni',
                                                      'f1wg7cxxg7zvwm7bdmfytw6mejs2p27qma5r6opwq',
                                                      'f1h4ssetvnj2vpugsuzptl4swlgfunw7oa3eik54a',
                                                      'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy',
                                                      'f1arv62ala37lytdxyjoexdom7j3mmnvswgqqt2aq',
                                                      'f1ybp6crbyfjm3umeecyqbj5d3uvgxktecw6h7wwa',
                                                      'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq',
                                                      'f3qc5njnb3cjjueyej4tyy6w7ly33ggabfycp7p7m7ssxqdcjdutdf3whtfl6u6lwbklf23gdudoydb3bem7aa'},
                                  'output_addresses': {'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q',
                                                       'f1i5fdnws5kufiyketew3sdc2dvs2pdzyaroqugjy',
                                                       'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy',
                                                       'f1rqseyjytqgnj2x5v6dn35xsyxyy2akhreuv3tzi',
                                                       'f1oalx3iozffplpg2nsredumgo3nmmld4zklvtndy',
                                                       'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q',
                                                       'f1hs2uamvby6xeijnbx4x6rbyelhl3w6w6q2k7fsa',
                                                       'f1fgrzwz6e4hvohnom4gvtqbt2rqrdupikwlkucfy',
                                                       'f13sb4pa34qzf35txnan4fqjfkwwqgldz6ekh5trq'}}
        expected_txs_info = {
            'outgoing_txs': {
                'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacea52fayacxy7s5fglzq2yyfuehutdnfjoq7fhbot6lmfvdmjchtzs',
                     'value': Decimal('189.199000000000000000'),
                     'block_height': 3100019, 'symbol':'FIL'}]},
                'f1ybp6crbyfjm3umeecyqbj5d3uvgxktecw6h7wwa': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceatr6d7twviu7a2dexgrumfjgmbr6cxvcviqyru5uyjclckcq6jns',
                     'value': Decimal('8.720000000000000000'),
                     'block_height': 3100020, 'symbol':'FIL'}]},
                'f1pxfh43a7vgctpmkqvaiydgelkiqfkpfkzq23y6y': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebn4fygpspxwe7y4cqg7qyxpqbcnp5yiwc2gnejypiiotphybjjwa',
                     'value': Decimal('103.999980500000000000'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f1ksncdvchghqazbxjyxfnpet2vzymekwgrkvksdy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                     'value': Decimal('1836.544371471789005446'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f1bko4of3o6r2mqzqm7xdpwluiqhsnbjbjtkvfpzq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                     'value': Decimal('300.000000000000000000'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f124lee77pbzzmznheuqfrq3k7f3xjelmnw6rfkhq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                     'value': Decimal('107.469614033901198742'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f1bqdyj4a5pehaf4sgw7pgzckbwvulvnpjcwxfzni': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecllci3dxkzqy6ovk6maxzocfeylkysr7qztl6zl5k5htrgz7q4hk',
                     'value': Decimal('25.535262927388841428'),
                     'block_height': 3100022, 'symbol':'FIL'}]},
                'f1wg7cxxg7zvwm7bdmfytw6mejs2p27qma5r6opwq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecdhaeqro6zin5dhjz2jbynfvvh36n5r5vlhriik275quymkdsc2w',
                     'value': Decimal('37.998905220000000000'),
                     'block_height': 3100022, 'symbol':'FIL'}]
                },
                'f1arv62ala37lytdxyjoexdom7j3mmnvswgqqt2aq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebq4wxl3olin4iujegs3f5pdo6rxne3lwsrwyfqgpt2qdxin2jwim',
                     'value': Decimal('34.920851467094855844'),
                     'block_height': 3100022, 'symbol':'FIL'}
                ]},
                'f1k56woowxbbjx2dxycw46g2yoztt7yrv3m3zmraa':
                    {Currencies.fil: [
                        {'contract_address': None,
                         'tx_hash': 'bafy2bzacedxb34pnmw5tkbi543cqgseyfvs6oq5duvkjt4antxmgq4s7kh3e2',
                         'value': Decimal('99.999401060000000000'),
                         'block_height': 3100022, 'symbol':'FIL'}
                    ]},
                'f1h4ssetvnj2vpugsuzptl4swlgfunw7oa3eik54a':
                    {Currencies.fil: [
                        {'contract_address': None,
                         'tx_hash': 'bafy2bzacechkfhi7i2tjugozbq4n657wltzggoqzfqfs34eznfpytrpbban6c',
                         'value': Decimal('1661.945390000000000000'),
                         'block_height': 3100023, 'symbol':'FIL'}
                    ]},
                'f3qc5njnb3cjjueyej4tyy6w7ly33ggabfycp7p7m7ssxqdcjdutdf3whtfl6u6lwbklf23gdudoydb3bem7aa':
                    {Currencies.fil: [
                        {'contract_address': None,
                         'tx_hash': 'bafy2bzacedud26q5rmgzfgvjmi25ntujnsvnjk56eryjmeewaee33wmlp5rf2',
                         'value': Decimal('18.390000000000000568'),
                         'block_height': 3100023, 'symbol':'FIL'}
                    ]}

            },

            'incoming_txs': {
                'f1oalx3iozffplpg2nsredumgo3nmmld4zklvtndy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacea52fayacxy7s5fglzq2yyfuehutdnfjoq7fhbot6lmfvdmjchtzs',
                     'value': Decimal('189.199000000000000000'),
                     'block_height': 3100019, 'symbol':'FIL'}]},
                'f1fgrzwz6e4hvohnom4gvtqbt2rqrdupikwlkucfy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceatr6d7twviu7a2dexgrumfjgmbr6cxvcviqyru5uyjclckcq6jns',
                     'value': Decimal('8.720000000000000000'),
                     'block_height': 3100020, 'symbol':'FIL'}]},
                'f1dbm3hibu77kcxyoinqn3x7mdwx6jhlysyce6f2q': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebf4gfvc5ch3ggvb2kcnezy3ftygfz42jxk2xjy5pyw565obtd6qw',
                     'value': Decimal('300.000000000000000000'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecfplueozkrnvr5m3g3ms5xzo4nbwjdseql4oak64obesodhdtqw6',
                     'value': Decimal('107.469614033901198742'),
                     'block_height': 3100021, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedkywc6ndyt7whfvcpv34rjtsuroq4fmqespmki2ys4mvzsbdteig',
                     'value': Decimal('1836.544371471789005446'),
                     'block_height': 3100021, 'symbol':'FIL'}]},
                'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebn4fygpspxwe7y4cqg7qyxpqbcnp5yiwc2gnejypiiotphybjjwa',
                     'value': Decimal('103.999980500000000000'),
                     'block_height': 3100021, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecdhaeqro6zin5dhjz2jbynfvvh36n5r5vlhriik275quymkdsc2w',
                     'value': Decimal('37.998905220000000000'),
                     'block_height': 3100022, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedxb34pnmw5tkbi543cqgseyfvs6oq5duvkjt4antxmgq4s7kh3e2',
                     'value': Decimal('99.999401060000000000'),
                     'block_height': 3100022, 'symbol':'FIL'},
                ]},
                'f13sb4pa34qzf35txnan4fqjfkwwqgldz6ekh5trq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecllci3dxkzqy6ovk6maxzocfeylkysr7qztl6zl5k5htrgz7q4hk',
                     'value': Decimal('25.535262927388841428'),
                     'block_height': 3100022, 'symbol':'FIL'}]},
                'f1hs2uamvby6xeijnbx4x6rbyelhl3w6w6q2k7fsa': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebq4wxl3olin4iujegs3f5pdo6rxne3lwsrwyfqgpt2qdxin2jwim',
                     'value': Decimal('34.920851467094855844'),
                     'block_height': 3100022, 'symbol':'FIL'}]},
                'f1rqseyjytqgnj2x5v6dn35xsyxyy2akhreuv3tzi': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedud26q5rmgzfgvjmi25ntujnsvnjk56eryjmeewaee33wmlp5rf2',
                     'value': Decimal('18.390000000000000568'),
                     'block_height': 3100023, 'symbol':'FIL'}]},
                'f1i5fdnws5kufiyketew3sdc2dvs2pdzyaroqugjy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacechkfhi7i2tjugozbq4n657wltzggoqzfqfs34eznfpytrpbban6c',
                     'value': Decimal('1661.945390000000000000'),
                     'block_height': 3100023, 'symbol':'FIL'}]}
            }
        }
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('FIL', None, None, True, True)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
