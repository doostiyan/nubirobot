import pytest


@pytest.fixture
def tx_hash():
    return '7c8c8088108ebaf9a6fcfc9273e52e68e4d5e089eeb4007e6149b414c8bb4b9a'


@pytest.fixture
def tx_hash_aggregation():
    return '4494d6be3168ff70c6538c273f925446b477c1b4752d1fd7f076c2da6c2d3d10'


@pytest.fixture
def tx_details_tx_hash_aggregation_mock_response():
    return {'hash': '4494d6be3168ff70c6538c273f925446b477c1b4752d1fd7f076c2da6c2d3d10',
            'vin': [{'scriptSig': {
                'asm': '3044022038d38bc82870e3950f1d0188fe10889758b99a7663d7218da8168b13b7e24aef02200e4f3cebf72da85e513f3c23c6e331aa104406c344fe310bf4238fe2e05f5744[ALL] 0308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40',
                'hex': '473044022038d38bc82870e3950f1d0188fe10889758b99a7663d7218da8168b13b7e24aef02200e4f3cebf72da85e513f3c23c6e331aa104406c344fe310bf4238fe2e05f574401210308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40'},
                'txid': 'd1a190f4b7225ad1aff5097c03f8ddc82de1f05307603735339e70e5f3a90f4b',
                'vout': 2}], 'vout': [{'n': 0, 'scriptPubKey': {
            'addresses': ['DBEYazMywpqaFUt4su2vxjPGhRVPkGGP7U'],
            'asm': 'OP_DUP OP_HASH160 42d893d8fa6e1269628942f5d109b93b266250e2 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a91442d893d8fa6e1269628942f5d109b93b266250e288ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                       'value': 244964}, {'n': 1, 'scriptPubKey': {
            'addresses': ['D67kvFnJnJxxHxnNyDhMghC1bfZ74922XA'],
            'asm': 'OP_DUP OP_HASH160 0ab754cd22f7f999cb90245b6f7c8409b2a45213 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a9140ab754cd22f7f999cb90245b6f7c8409b2a4521388ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                                          'value': 54213}, {'n': 2,
                                                                            'scriptPubKey': {
                                                                                'addresses': [
                                                                                    'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'],
                                                                                'asm': 'OP_DUP OP_HASH160 6100ff1d8c47cbaae0fc96957aea720568657bf1 OP_EQUALVERIFY OP_CHECKSIG',
                                                                                'hex': '76a9146100ff1d8c47cbaae0fc96957aea720568657bf188ac',
                                                                                'reqSigs': 1,
                                                                                'type': 'pubkeyhash'},
                                                                            'value': 1612852.06414584}]}


@pytest.fixture
def tx_details_tx_hash_aggregation_from_address_mock_response():
    return {
        'hash': 'd1a190f4b7225ad1aff5097c03f8ddc82de1f05307603735339e70e5f3a90f4b', 'vin': [{'scriptSig': {
            'asm': '3045022100df2d2010fc557767cb27ee1486cbd2205fd2d7012ce34e8b02a35dcac34411b602205ac175db7b29ea0bbeb5191f14afb35b3c126155304d2e15d24cedb82ecdc87d[ALL] 0308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40',
            'hex': '483045022100df2d2010fc557767cb27ee1486cbd2205fd2d7012ce34e8b02a35dcac34411b602205ac175db7b29ea0bbeb5191f14afb35b3c126155304d2e15d24cedb82ecdc87d01210308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40'},
            'txid': '31cfd0b88b33c317425ec2e3076a01fe070d5f56096d3c4bcee24ab7568e21b6',
            'vout': 2}], 'vout': [{'n': 0, 'scriptPubKey': {
            'addresses': ['DGXvmXMdx4AUE7SqMtof8xfPbMm2zdsiXd'],
            'asm': 'OP_DUP OP_HASH160 7cfacb4967dc152aa99a268038ac69fceb0f7749 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a9147cfacb4967dc152aa99a268038ac69fceb0f774988ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                   'value': 109.237821}, {'n': 1, 'scriptPubKey': {
            'addresses': ['D8Xrja5S4vLZeY5UEfXHDaNL9v33QXUrBF'],
            'asm': 'OP_DUP OP_HASH160 25366bb17ebbfba5d53eb89cdf07570ea08db500 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a91425366bb17ebbfba5d53eb89cdf07570ea08db50088ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                                          'value': 1996}, {'n': 2,
                                                                           'scriptPubKey': {
                                                                               'addresses': [
                                                                                   'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'],
                                                                               'asm': 'OP_DUP OP_HASH160 6100ff1d8c47cbaae0fc96957aea720568657bf1 OP_EQUALVERIFY OP_CHECKSIG',
                                                                               'hex': '76a9146100ff1d8c47cbaae0fc96957aea720568657bf188ac',
                                                                               'reqSigs': 1,
                                                                               'type': 'pubkeyhash'},
                                                                           'value': 1912029.19171484}]}


@pytest.fixture
def tx_details_tx_hash_mock_response():
    return {'hash': '7c8c8088108ebaf9a6fcfc9273e52e68e4d5e089eeb4007e6149b414c8bb4b9a',
            'vin': [{'scriptSig': {
                'asm': '3045022100adf277f82a1b7a2f3de41b32e0a7031d098891541dda9a67c0a625b4d9f429aa022027263b49470dd418fc4a636e719dec5ca415b5b39faf29450cfe8c3f5a069ca7[ALL] 0349fea1f0c0f6d1c28b4ddd7bb1e21cbd4a425b1503ba479e2ebb8cd3a65c7c62',
                'hex': '483045022100adf277f82a1b7a2f3de41b32e0a7031d098891541dda9a67c0a625b4d9f429aa022027263b49470dd418fc4a636e719dec5ca415b5b39faf29450cfe8c3f5a069ca701210349fea1f0c0f6d1c28b4ddd7bb1e21cbd4a425b1503ba479e2ebb8cd3a65c7c62'},
                'txid': 'faaf86f605e9ea98031967a4d792fa74a9f80deb5d30875f231501ad4a56dab5',
                'vout': 0}], 'vout': [{'n': 0, 'scriptPubKey': {
            'addresses': ['DDdQHoebn7uhvuUCgaoDGLrvCFp4dy5c48'],
            'asm': 'OP_DUP OP_HASH160 5d1b788807c8a0f51170979328a447083e468b5b OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a9145d1b788807c8a0f51170979328a447083e468b5b88ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                       'value': 145.331}]}


@pytest.fixture
def tx_details_tx_hash_from_address_mock_response():
    return {
        'hash': 'faaf86f605e9ea98031967a4d792fa74a9f80deb5d30875f231501ad4a56dab5', 'vin': [{'scriptSig': {
            'asm': '304402207905cc9e9721d90ef7ec7fabf66bb208a26d18ffc221b1406cfdac2b4f6db06d0220210ba1f3c251baefabcd730629eda77480ab3027cab75685e4667a0175d53663[ALL] 03e6356467a8b542a08981d0922af3e5d1b60b7196beee65fd2f6fa396bd78ff3d',
            'hex': '47304402207905cc9e9721d90ef7ec7fabf66bb208a26d18ffc221b1406cfdac2b4f6db06d0220210ba1f3c251baefabcd730629eda77480ab3027cab75685e4667a0175d53663012103e6356467a8b542a08981d0922af3e5d1b60b7196beee65fd2f6fa396bd78ff3d'},
            'txid': 'b05f9aafa64c3db5dc4a7eccdb759c88b328b0f90e6d2f48ed841760a84c4ce4',
            'vout': 1}], 'vout': [{'n': 0, 'scriptPubKey': {
            'addresses': ['DJ4byAYWH6BuSx8ReLzkUr7ThSwzdvhQ93'],
            'asm': 'OP_DUP OP_HASH160 8dc01f304dc5a7dbfc95bcc082a1ce7ff9b62782 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a9148dc01f304dc5a7dbfc95bcc082a1ce7ff9b6278288ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                   'value': 145.40124555}, {'n': 1, 'scriptPubKey': {
            'addresses': ['DCgEJNYBGR6gjBSWHatPuBb22AkPu3X6Fs'],
            'asm': 'OP_DUP OP_HASH160 52ac40e5f5e69abeec0b2277f3733f8278c940f0 OP_EQUALVERIFY OP_CHECKSIG',
            'hex': '76a91452ac40e5f5e69abeec0b2277f3733f8278c940f088ac', 'reqSigs': 1, 'type': 'pubkeyhash'},
                                                            'value': 55698.61799775}]}
