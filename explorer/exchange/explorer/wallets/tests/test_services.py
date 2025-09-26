import datetime
from decimal import Decimal

import pytest

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.explorer.wallets.dtos import WalletBalanceDTO
from exchange.explorer.wallets.services import WalletExplorerService
from exchange.explorer.wallets.utils.exceptions import AddressNotFoundException


@pytest.mark.skip
@pytest.mark.service
@pytest.mark.django_db
def test_get_wallet_balances_dtos_service(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_wallets_balance',
                 return_value={
                     18: [
                         {
                             'address': 'DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX',
                             'received': Decimal('7001050117.284460190000000000'),
                             'sent': Decimal(0),
                             'balance': Decimal('7001050117.284460190000000000'),
                             'rewarded': Decimal(0)
                         },
                         {
                             'address': 'DCSHdVLyjx58AbzJ7FAbD52SyULfpepRrs',
                             'received': Decimal('274.870573080000000000'),
                             'sent': Decimal(0),
                             'balance': Decimal('274.870573080000000000'),
                             'rewarded': Decimal(0)
                         },
                     ]
                 })
    service_response = WalletExplorerService.get_wallet_balance_dtos(network='DOGE',
                                                                     addresses=['DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX',
                                                                                'DCSHdVLyjx58AbzJ7FAbD52SyULfpepRrs'],
                                                                     currency=None)
    wallet_balances_dto = [
        WalletBalanceDTO(address='DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX',
                         received=Decimal('7001050117.284460190000000000'),
                         sent=Decimal(0),
                         balance=Decimal('7001050117.284460190000000000'),
                         rewarded=Decimal(0)),
        WalletBalanceDTO(address='DCSHdVLyjx58AbzJ7FAbD52SyULfpepRrs',
                         received=Decimal('274.870573080000000000'),
                         sent=Decimal(0),
                         balance=Decimal('274.870573080000000000'),
                         rewarded=Decimal(0))
    ]
    assert service_response == wallet_balances_dto


@pytest.mark.skip
@pytest.mark.service
@pytest.mark.django_db
def test_get_wallet_balances_dtos_service_with_none_balances_data_should_raise_not_found_exception(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_wallets_balance',
                 return_value=None)
    pytest.raises(AddressNotFoundException,
                  WalletExplorerService.get_wallet_balance_dtos,
                  network='DOGE',
                  addresses=['DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX',
                             'DCSHdVLyjx58AbzJ7FAbD52SyULfpepRrs'],
                  currency='DOGE')


@pytest.mark.service
@pytest.mark.django_db
def test_get_wallet_transaction_dtos_service(mocker):
    # --------- UTXO networks --------------
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_wallet_transactions',
                 return_value={18: [{
                     'address': 'DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk',
                     'block': 5012943,
                     'confirmations': 11,
                     'contract_address': None,
                     'details': {'txid': '2f9f70e3bc243779c55bb8d3e2b1e528ff9299a7ca5044682cb6ac88e3e156cd',
                                 'version': 2,
                                 'vin': [
                                     {
                                         'txid': 'f022e63b246291429a70e3544572ada9703b9f8abf390594f2cbe30fc976984b',
                                         'sequence': 4294967295, 'n': 0,
                                         'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'], 'isAddress': True,
                                         'value': '600006',
                                         'hex': '47304402206ea833bf42b2a658dd3d3a4da5d543513658d4da0927f98d2d7768183'
                                                '1b124320220438cf0c9a4f48f39bed25d5f5954348323292a6ece496a9307e00c5e7'
                                                'a77e0f0012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c2c6a46'
                                                'a7f8ca2f'},
                                     {
                                         'txid': 'e64bb9779447ef2107deac60f7b9d830b1eb3677af65c196201953451b1a6fb9',
                                         'sequence': 4294967295, 'n': 1,
                                         'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'], 'isAddress': True,
                                         'value': '800008',
                                         'hex': '483045022100e6e0b9d26b6e80ce364df5824516c456e7e2600ba03d9d381892766'
                                                'ba6738a1702206e276c7cb66f17fbec91f7a761b66fb993cc98eab5a3adecbff9e60'
                                                'e59481be5012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c2c6a'
                                                '46a7f8ca2f'},
                                     {
                                         'txid': 'a227e4d9674dad7a3bf41fcf3763c7dfe6b46f406ed7d5fdefe0d13cbec5bdbc',
                                         'sequence': 4294967295, 'n': 2,
                                         'addresses': ['D5f7fYMxB84DWZUkc6QpA1pLQGAosc135U'], 'isAddress': True,
                                         'value': '100000',
                                         'hex': '483045022100dad1b10f839932122774a7d236f5267c3b7b6ce8a2ee3341b2773b81f'
                                                '0a3b6e90220798d68b82524a3942143631a3076697332ac0be7ff814e6d7a507c2dc'
                                                'dd25d61832102cf878fe6697a11512f78af43e14c006e48ca19fdfbb7e8c2fc881fb8'
                                                '074fccfa'},
                                     {
                                         'txid': 'f022e63b246291429a70e3544572ada9703b9f8abf390594f2cbe30fc976984b',
                                         'vout': 4, 'sequence': 4294967295, 'n': 3,
                                         'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'], 'isAddress': True,
                                         'value': '1853718880',
                                         'hex': '4730440220365325e3bdcfe0625f7f3b3b7613281732c88b68b755297e2bcac1d0e6'
                                                'fe786202202fac0a6db57af1e7484ff10e380e712b216354733a0dc7e73d7d47a962'
                                                '7e3c36012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c2c6a46a'
                                                '7f8ca2f'},
                                     {
                                         'txid': 'e64bb9779447ef2107deac60f7b9d830b1eb3677af65c196201953451b1a6fb9',
                                         'vout': 4, 'sequence': 4294967295, 'n': 4,
                                         'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'], 'isAddress': True,
                                         'value': '1855549720',
                                         'hex': '483045022100da1ebf8f549db60baedb69b4d84bf002f98b6d61f453cf9e2768cd3'
                                                '1348b0f890220499de964b0f51a69348ba28b141ac2683947f4bf5269cdf9841875'
                                                'd48968f768012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c2'
                                                'c6a46a7f8ca2f'}],
                                 'vout': [{'value': '1400014', 'n': 0,
                                           'hex': '76a914793260180dbed2102da4095c1914d7ebe3304cbf88ac',
                                           'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'],
                                           'isAddress': True},
                                          {'value': '100000', 'n': 1,
                                           'hex': '76a914793260180dbed2102da4095c1914d7ebe3304cbf88ac',
                                           'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'],
                                           'isAddress': True},
                                          {'value': '1774900000', 'n': 2,
                                           'hex': '76a91405ad6b1e662036e441cc8ce1083885e7ba9e36d888ac',
                                           'addresses': ['D5f7fYMxB84DWZUkc6QpA1pLQGAosc135U'],
                                           'isAddress': True},
                                          {'value': '75600000', 'n': 3,
                                           'hex': '76a914943cbd49a2113063807f59df5d0f52794533ceab88ac',
                                           'addresses': ['DJeuJtzLu1cjLkbWWAr6aQums4edTu4GKJ'],
                                           'isAddress': True},
                                          {'value': '1848308600', 'n': 4,
                                           'hex': '76a914793260180dbed2102da4095c1914d7ebe3304cbf88ac',
                                           'addresses': ['DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'],
                                           'isAddress': True}],
                                 'blockHash': '6ff8c6631ba77bd8e06fdfafb174f8f19a9b43169f8b126e1514c5c782efb1f5',
                                 'blockHeight': 5012943, 'confirmations': 11, 'blockTime': 1703016715,
                                 'value': '3700308614', 'valueIn': '3710768614', 'fees': '10460000',
                                 'hex': '02000000054b9876c90fe3cbf2940539bf8a9f3b70a9ad724554e3709a429162243be622f'
                                        '0000000006a47304402206ea833bf42b2a658dd3d3a4da5d543513658d4da0927f98d2d'
                                        '77681831b124320220438cf0c9a4f48f39bed25d5f5954348323292a6ece496a9307e00c'
                                        '5e7a77e0f0012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c2c6a46'
                                        'a7f8ca2fffffffffb96f1a1b4553192096c165af7736ebb130d8b9f760acde0721ef4794'
                                        '77b94be6000000006b483045022100e6e0b9d26b6e80ce364df5824516c456e7e2600ba03'
                                        'd9d381892766ba6738a1702206e276c7cb66f17fbec91f7a761b66fb993cc98eab5a3adec'
                                        'bff9e60e59481be5012102aa53a38eeccca6c7256a12745d384650314fde8adec7cfce4c'
                                        '2c6a46a7f8ca2fffffffffbcbdc5be3cd1e0effdd5d76e406fb4e6dfc76337cf1ff43b7a'
                                        'ad4d67d9e427a2000000006b483045022100dad1b10f839932122774a7d236f5267c3b7b6'
                                        'ce8a2ee3341b2773b81f0a3b6e90220798d68b82524a3942143631a3076697332ac0be7'
                                        'ff814e6d7a507c2dcdd25d61832102cf878fe6697a11512f78af43e14c006e48ca19fdf'
                                        'bb7e8c2fc881fb8074fccfaffffffff4b9876c90fe3cbf2940539bf8a9f3b70a9ad7245'
                                        '54e3709a429162243be622f0040000006a4730440220365325e3bdcfe0625f7f3b3b761'
                                        '3281732c88b68b755297e2bcac1d0e6fe786202202fac0a6db57af1e7484ff10e380e712'
                                        'b216354733a0dc7e73d7d47a9627e3c36012102aa53a38eeccca6c7256a12745d3846503'
                                        '14fde8adec7cfce4c2c6a46a7f8ca2fffffffffb96f1a1b4553192096c165af7736ebb13'
                                        '0d8b9f760acde0721ef479477b94be6040000006b483045022100da1ebf8f549db60baed'
                                        'b69b4d84bf002f98b6d61f453cf9e2768cd31348b0f890220499de964b0f51a69348ba2'
                                        '8b141ac2683947f4bf5269cdf9841875d48968f768012102aa53a38eeccca6c7256a1274'
                                        '5d384650314fde8adec7cfce4c2c6a46a7f8ca2fffffffff05ce5c1500000000001976a91'
                                        '4793260180dbed2102da4095c1914d7ebe3304cbf88aca0860100000000001976a9147932'
                                        '60180dbed2102da4095c1914d7ebe3304cbf88ac20d3ca69000000001976a91405ad6b1e6'
                                        '62036e441cc8ce1083885e7ba9e36d888ac80908104000000001976a914943cbd49a2113'
                                        '063807f59df5d0f52794533ceab88ac78f32a6e000000001976a914793260180dbed2102'
                                        'da4095c1914d7ebe3304cbf88ac00000000'},
                     'from_address': ['D5f7fYMxB84DWZUkc6QpA1pLQGAosc135U',
                                      'DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk'],
                     'hash': '2f9f70e3bc243779c55bb8d3e2b1e528ff9299a7ca5044682cb6ac88e3e156cd',
                     'huge': False,
                     'invoice': None,
                     'is_double_spend': False,
                     'tag': '',
                     'timestamp': datetime.datetime(2023, 12, 19, 20, 11, 55, tzinfo=datetime.timezone.utc),
                     'value': Decimal('-37.10668614'),
                 }]})
    service_response = WalletExplorerService.get_wallet_transactions_dto(
        network='DOGE',
        address='DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk',
        currency='DOGE',
        double_check=False,
    )
    transactions_dtos = [
        TransferTx(
            tx_hash='2f9f70e3bc243779c55bb8d3e2b1e528ff9299a7ca5044682cb6ac88e3e156cd',
            success=True,
            from_address='D5f7fYMxB84DWZUkc6QpA1pLQGAosc135U',
            to_address='',
            value=Decimal('-37.10668614'),
            symbol='DOGE',
            confirmations=11,
            block_height=5012943,
            block_hash=None,
            date=datetime.datetime(2023, 12, 19, 20, 11, 55, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        ),
        TransferTx(
            tx_hash='2f9f70e3bc243779c55bb8d3e2b1e528ff9299a7ca5044682cb6ac88e3e156cd',
            success=True,
            from_address='DGBvecSHtMcduGcYbZQDuE8bjSBudCE5Wk',
            to_address='',
            value=Decimal('-37.10668614'),
            symbol='DOGE',
            confirmations=11,
            block_height=5012943,
            block_hash=None,
            date=datetime.datetime(2023, 12, 19, 20, 11, 55, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    assert service_response == transactions_dtos

    # --------- other networks --------------
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_wallet_transactions',
                 return_value={
                     39: [{
                         'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                         'block': 3490332,
                         'confirmations': 152,
                         'contract_address': None,
                         'details': {},
                         'from_address': ['f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy'],
                         'hash': 'bafy2bzacedy2eiyrs426eucmitp5ua6wugcaxs6umtbg6cz4gjly5hpsh64py',
                         'huge': False,
                         'invoice': None,
                         'is_double_spend': False,
                         'tag': None,
                         'timestamp': datetime.datetime(2023, 12, 19, 23, 36, tzinfo=datetime.timezone.utc),
                         'value': Decimal('-10267.296999630000000000')
                     }]
                 })
    service_response = WalletExplorerService.get_wallet_transactions_dto(
        network='FIL',
        address='f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
        currency='FIL',
        double_check=False,
    )

    transactions_dtos = [
        TransferTx(
            tx_hash='bafy2bzacedy2eiyrs426eucmitp5ua6wugcaxs6umtbg6cz4gjly5hpsh64py',
            success=True,
            from_address='f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
            to_address='',
            value=Decimal('-10267.296999630000000000'),
            symbol='FIL',
            confirmations=152,
            block_height=3490332,
            block_hash=None,
            date=datetime.datetime(2023, 12, 19, 23, 36, tzinfo=datetime.timezone.utc),
            memo=None,
            tx_fee=None,
            token=None,
            index=0,
        )
    ]
    assert service_response == transactions_dtos


@pytest.mark.service
@pytest.mark.django_db
def test__double_check_with_tx_detail__when_none_from_address__successful(mocker):
    mock_tx_details = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address=None,  # None from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    wallet_txs = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address=None,  # None from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    mocker.patch(
        'exchange.explorer.transactions.services.TransactionExplorerService.get_transaction_details_from_default_provider_dtos',
        return_value=mock_tx_details
    )

    mocker.patch(
        'exchange.explorer.blocks.models.GetBlockStats.get_block_stats_by_network_name',
        return_value=type('obj', (object,), {'min_available_block': 0})
    )

    result = WalletExplorerService.double_check_with_tx_details(
        wallet_txs_dtos=wallet_txs,
        network='BTC',
        address='test_address'
    )

    assert len(result) == len(wallet_txs)
    assert result[0].tx_hash == 'test_hash_1'
    assert result[0].from_address is None
    assert result[0].to_address == 'test_address'
    assert result[0].value == Decimal('1.0')


@pytest.mark.service
@pytest.mark.django_db
def test__double_check_with_tx_detail__when_multiple_transactions__successful(mocker):
    mock_tx_details = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address=None,  # None from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        ),
        TransferTx(
            tx_hash='test_hash_2',
            success=True,
            from_address='sender_address',  # Valid from_address
            to_address='test_address',
            value=Decimal('2.0'),
            symbol='BTC',
            confirmations=1,
            block_height=101,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        ),
        TransferTx(
            tx_hash='test_hash_3',
            success=True,
            from_address=None,  # Another None from_address
            to_address='test_address',
            value=Decimal('3.0'),
            symbol='BTC',
            confirmations=1,
            block_height=102,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    wallet_txs = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address=None,  # None from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        ),
        TransferTx(
            tx_hash='test_hash_2',
            success=True,
            from_address='sender_address',  # Valid from_address
            to_address='test_address',
            value=Decimal('2.0'),
            symbol='BTC',
            confirmations=1,
            block_height=101,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        ),
        TransferTx(
            tx_hash='test_hash_3',
            success=True,
            from_address=None,  # Another None from_address
            to_address='test_address',
            value=Decimal('3.0'),
            symbol='BTC',
            confirmations=1,
            block_height=102,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    mocker.patch(
        'exchange.explorer.transactions.services.TransactionExplorerService.get_transaction_details_from_default_provider_dtos',
        return_value=mock_tx_details
    )

    mocker.patch(
        'exchange.explorer.blocks.models.GetBlockStats.get_block_stats_by_network_name',
        return_value=type('obj', (object,), {'min_available_block': 0})
    )

    result = WalletExplorerService.double_check_with_tx_details(
        wallet_txs_dtos=wallet_txs,
        network='BTC',
        address='test_address'
    )

    assert len(result) == len(wallet_txs)

    assert result[0].tx_hash == 'test_hash_1'
    assert result[0].from_address is None
    assert result[0].to_address == 'test_address'
    assert result[0].value == Decimal('1.0')

    assert result[1].tx_hash == 'test_hash_2'
    assert result[1].from_address == 'sender_address'
    assert result[1].to_address == 'test_address'
    assert result[1].value == Decimal('2.0')

    assert result[2].tx_hash == 'test_hash_3'
    assert result[2].from_address is None
    assert result[2].to_address == 'test_address'
    assert result[2].value == Decimal('3.0')


@pytest.mark.service
@pytest.mark.django_db
def test_double_check_with_tx_detail__when_mismatched_from_address__successful(mocker):
    mock_tx_details = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address='sender_address',  # Has from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    wallet_txs = [
        TransferTx(
            tx_hash='test_hash_1',
            success=True,
            from_address=None,  # No from_address
            to_address='test_address',
            value=Decimal('1.0'),
            symbol='BTC',
            confirmations=1,
            block_height=100,
            block_hash=None,
            date=datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            memo='',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    mocker.patch(
        'exchange.explorer.transactions.services.TransactionExplorerService.get_transaction_details_from_default_provider_dtos',
        return_value=mock_tx_details
    )

    mocker.patch(
        'exchange.explorer.blocks.models.GetBlockStats.get_block_stats_by_network_name',
        return_value=type('obj', (object,), {'min_available_block': 0})
    )

    result = WalletExplorerService.double_check_with_tx_details(
        wallet_txs_dtos=wallet_txs,
        network='BTC',
        address='test_address'
    )

    assert len(result) == len(wallet_txs)
    assert result[0].tx_hash == 'test_hash_1'
    assert result[0].from_address is None  # Should keep the wallet_tx's from_address (None)
    assert result[0].to_address == 'test_address'
    assert result[0].value == Decimal('1.0')
