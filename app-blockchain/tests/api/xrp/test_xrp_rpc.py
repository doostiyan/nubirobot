from unittest import TestCase
from unittest.mock import Mock

from django.conf import settings
from pytz import UTC
import datetime
import pytest
from _decimal import Decimal
if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos import TransferTx

from exchange.blockchain.api.xrp.new_xrp_rpc import RippleClusterApi


@pytest.mark.slow
class RippleRpcClusterApiCalls(TestCase):
    api = RippleClusterApi

    addresses_of_account = ['rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb',
                            'rBCXdeykcZRC5Ak8sDvZU83c37kGGnyPox']
    hash_of_transactions = ['B58F50CEF200DCA8A915C479AF389385CEFB7B282D0760DF3878E54BDA51AE1E',
                            'A4089728F730B10E34ECD444088852250117AB8E50C8590C309E8CDF84E38FC3',
                            '4988892147BD2B177DF9A23F2F001D2D68256189795D1F7907F50D9C97D59A15',
                            '8E3DD8865653618539619ECC263B3EB6101D2CAC66580EE2F56F1BAFEE589BDA']

    @classmethod
    def check_general_response(cls, response):
        if not response:
            return False
        if not isinstance(response, dict):
            return False
        if not response.get('result'):
            return False
        if not isinstance(response.get('result'), dict):
            return False
        return True

    def test_get_balance_api(self):
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result)
            result = get_balance_result.get('result')
            assert result.get('account_data')
            assert isinstance(result.get('account_data'), dict)
            assert result.get('account_data').get('Balance')
            assert isinstance(result.get('account_data').get('Balance'), str)

    def test_get_address_txs_api(self):

        result_keys = {'account', 'ledger_index_max', 'status', 'transactions', 'validated'}
        result_types_check = [('account', str), ('ledger_index_max', int), ('status', str), ('transactions', list),
                              ('validated', bool)]
        meta_keys = {'TransactionResult', 'delivered_amount'}
        tx_keys = {'Account', 'Amount', 'DeliverMax', 'Destination', 'DestinationTag', 'Fee', 'Flags',
                   'LastLedgerSequence', 'Memos', 'Sequence', 'SigningPubKey', 'TransactionType', 'TxnSignature',
                   'date', 'hash', 'inLedger', 'ledger_index'}
        tx_types_check = [('Account', str), ('Destination', str), ('DestinationTag', int), ('Fee', str),
                          ('TransactionType', str), ('date', int), ('hash', str), ('ledger_index', int)]
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response)
            result = get_address_txs_response.get('result')
            if result_keys.issubset(set(result.keys())):
                for key, value in result_types_check:
                    assert isinstance(result.get(key), value)
                transactions = result.get('transactions')
                for tx in transactions:
                    assert isinstance(tx, dict)
                    assert (tx.get('meta') and isinstance(tx.get('meta'), dict))
                    assert (tx.get('tx') and isinstance(tx.get('tx'), dict))
                    if tx.get('validated'):
                        meta = tx.get('meta')
                        if meta_keys.issubset(meta.keys()):
                            if isinstance(meta.get('TransactionResult'), str) and isinstance(
                                    meta.get('delivered_amount'), str):
                                if tx_keys.issubset(tx.get('tx').keys()):
                                    for key, value in tx_types_check:
                                        assert isinstance(tx.get('tx').get(key), value)

    def test_get_tx_details_api(self):
        transaction_keys = {'Account', 'Amount', 'DeliverMax', 'Destination', 'DestinationTag', 'Fee', 'Flags',
                            'LastLedgerSequence', 'Memos', 'Sequence', 'SigningPubKey', 'TransactionType',
                            'TxnSignature', 'ctid', 'date', 'hash', 'inLedger', 'ledger_index', 'meta', 'status',
                            'validated'}
        types_check = [('Account', str), ('Destination', str), ('DestinationTag', int), ('Fee', str),
                       ('TransactionType', str), ('date', int), ('hash', str), ('ledger_index', int), ('meta', dict),
                       ('status', str), ('validated', bool)]
        meta_keys = {'TransactionResult', 'delivered_amount'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response)
            result = get_tx_details_response.get('result')
            if transaction_keys.issubset(result.keys()):
                for key, value in types_check:
                    assert isinstance(result.get(key), value)
                meta = result.get('meta')
                assert meta_keys.issubset(meta.keys())
                assert isinstance(meta.get('TransactionResult'), str)
                assert isinstance(meta.get('delivered_amount'), str)


class TestRippleRpcClusterApiFromExplorer(TestCase):
    api = RippleClusterApi
    currency = Currencies.xrp
    addresses_of_account = ['rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb',
                            'rBCXdeykcZRC5Ak8sDvZU83c37kGGnyPox']
    # hash of transactions in order of success,failed,failed, failed
    hash_of_transactions = ['B58F50CEF200DCA8A915C479AF389385CEFB7B282D0760DF3878E54BDA51AE1E',
                            'A4089728F730B10E34ECD444088852250117AB8E50C8590C309E8CDF84E38FC3',
                            '4988892147BD2B177DF9A23F2F001D2D68256189795D1F7907F50D9C97D59A15',
                            '8E3DD8865653618539619ECC263B3EB6101D2CAC66580EE2F56F1BAFEE589BDA']
    address_txs = ['rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY']

    def test_get_balance(self):
        balance_mock_response = [
            {'result': {
                'account_data': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208623601', 'Flags': 0,
                                 'LedgerEntryType': 'AccountRoot', 'OwnerCount': 0,
                                 'PreviousTxnID': '549A7620CDC493DE5695D0BFD4CA12D5067DE02FD3377C782A4C00D6C98A6D4C',
                                 'PreviousTxnLgrSeq': 89041293, 'Sequence': 89551822,
                                 'index': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B'},
                'account_flags': {'allowTrustLineClawback': False, 'defaultRipple': False, 'depositAuth': False,
                                  'disableMasterKey': False, 'disallowIncomingCheck': False,
                                  'disallowIncomingNFTokenOffer': False, 'disallowIncomingPayChan': False,
                                  'disallowIncomingTrustline': False, 'disallowIncomingXRP': False,
                                  'globalFreeze': False, 'noFreeze': False, 'passwordSpent': False,
                                  'requireAuthorization': False, 'requireDestinationTag': False},
                'ledger_current_index': 89041295, 'queue_data': {'txn_count': 0}, 'status': 'success',
                'validated': False}},
            {'result': {
                'account_data': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Balance': '1639921835', 'Flags': 0,
                                 'LedgerEntryType': 'AccountRoot', 'OwnerCount': 290,
                                 'PreviousTxnID': '7C38D3BD8C5247C008613910CFE48B85952DEAB1E72A61464021C893AE11F8A2',
                                 'PreviousTxnLgrSeq': 89040828, 'Sequence': 87194274,
                                 'index': '0D969662A3AD45BFD80DE3B57E66A6408040D16F3AA261BB01E0769BB96F6768'},
                'account_flags': {'allowTrustLineClawback': False, 'defaultRipple': False, 'depositAuth': False,
                                  'disableMasterKey': False, 'disallowIncomingCheck': False,
                                  'disallowIncomingNFTokenOffer': False, 'disallowIncomingPayChan': False,
                                  'disallowIncomingTrustline': False, 'disallowIncomingXRP': False,
                                  'globalFreeze': False, 'noFreeze': False, 'passwordSpent': False,
                                  'requireAuthorization': False, 'requireDestinationTag': False},
                'ledger_current_index': 89041303, 'queue_data': {'txn_count': 0}, 'status': 'success',
                'validated': False}},
            {'result': {
                'account_data': {'Account': 'rBCXdeykcZRC5Ak8sDvZU83c37kGGnyPox', 'Balance': '16533341', 'Flags': 0,
                                 'LedgerEntryType': 'AccountRoot', 'OwnerCount': 1,
                                 'PreviousTxnID': '5895CA364F66B5A2712C19FA5AA3CC305476C347ACD018C6690F2B1E850C8D97',
                                 'PreviousTxnLgrSeq': 89038972, 'Sequence': 88268643,
                                 'index': '38A2A9D4778D56FC18B8B53686D6B1F603E3BC8D08BC55292CBCF802CC70F5AB'},
                'account_flags': {'allowTrustLineClawback': False, 'defaultRipple': False, 'depositAuth': False,
                                  'disableMasterKey': False, 'disallowIncomingCheck': False,
                                  'disallowIncomingNFTokenOffer': False, 'disallowIncomingPayChan': False,
                                  'disallowIncomingTrustline': False, 'disallowIncomingXRP': False,
                                  'globalFreeze': False, 'noFreeze': False, 'passwordSpent': False,
                                  'requireAuthorization': False, 'requireDestinationTag': False},
                'ledger_current_index': 89041307, 'queue_data': {'txn_count': 0}, 'status': 'success',
                'validated': False}}
        ]
        self.api.request = Mock(side_effect=balance_mock_response)
        parsed_responses = []
        for address in self.addresses_of_account:
            api_response = self.api.get_balance(address)
            parse_response = self.api.parser.parse_balance_response(api_response)
            parsed_responses.append(parse_response)
        expected_parse_responses = [Decimal('4208.623601'), Decimal('1639.921835'), Decimal('16.533341')]
        for balance, expected_balance in zip(parsed_responses, expected_parse_responses):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_response = [
            {'result': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                        'Destination': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'DestinationTag': 2017, 'Fee': '25',
                        'Flags': 2147483648, 'LastLedgerSequence': 89018930, 'Memos': [{'Memo': {
                    'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                    {'Memo': {
                        'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                    {'Memo': {
                        'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                    {'Memo': {
                        'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                    {'Memo': {
                        'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                    {'Memo': {
                        'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                    {'Memo': {
                        'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                    {'Memo': {
                        'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                    {'Memo': {
                        'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                    {'Memo': {
                        'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                    {'Memo': {
                        'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                    {'Memo': {
                        'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                    {'Memo': {
                        'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                    {'Memo': {
                        'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                    {'Memo': {
                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                    {'Memo': {
                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89520858,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '304302201746BA551044045E334872899409213907E2531E9D94372BA6770EBD68336603021F61E8E6AF5C3942349C0CCAAF555AA211A0FBFF9BD6967CA59D843FC9373140',
                        'ctid': 'C54E522500070000', 'date': 772961631,
                        'hash': 'B58F50CEF200DCA8A915C479AF389385CEFB7B282D0760DF3878E54BDA51AE1E',
                        'inLedger': 89018917, 'ledger_index': 89018917, 'meta': {'AffectedNodes': [{'ModifiedNode': {
                    'FinalFields': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Balance': '1959095189',
                                    'Flags': 0, 'OwnerCount': 290, 'Sequence': 87194007},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '0D969662A3AD45BFD80DE3B57E66A6408040D16F3AA261BB01E0769BB96F6768',
                    'PreviousFields': {'Balance': '1959095188'},
                    'PreviousTxnID': '4EBFA28925B9ABE872FC5D2CC9401BE5163B055491A37B45B96C706D83B871C4',
                    'PreviousTxnLgrSeq': 89018916}}, {'ModifiedNode': {
                    'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4209428455',
                                    'Flags': 0, 'OwnerCount': 0, 'Sequence': 89520859},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                    'PreviousFields': {'Balance': '4209428481', 'Sequence': 89520858},
                    'PreviousTxnID': '55DEB4AC1E7791D6DCB22965B82773B4C8007D74A7F438E6AD6969167E2E90F2',
                    'PreviousTxnLgrSeq': 89018916}}], 'TransactionIndex': 7, 'TransactionResult': 'tesSUCCESS',
                    'delivered_amount': '1'},
                        'status': 'success', 'validated': True}},
            {'result': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Fee': '15', 'Flags': 524288,
                        'Sequence': 87194269,
                        'SigningPubKey': '035566B011B878AA5EC3DA46FC01B9BC929F0E196D96F8C7D7B5C311AB261B207A',
                        'TakerGets': {'currency': '58434F5245000000000000000000000000000000',
                                      'issuer': 'r3dVizzUAS3U29WKaaSALqkieytA2LCoRe', 'value': '4.645432'},
                        'TakerPays': '1', 'TransactionType': 'OfferCreate',
                        'TxnSignature': '30440220799EECFA239F08449181D317F7F909572124811A9A6DB9D80D85BA3ED2157D72022062BFD2628273870AD3650AC94DD6086AB003A0A9FA6BB990CE71912CB3FCEE9F',
                        'ctid': 'C54EA70700160000', 'date': 773044490,
                        'hash': 'A4089728F730B10E34ECD444088852250117AB8E50C8590C309E8CDF84E38FC3',
                        'inLedger': 89040647, 'ledger_index': 89040647, 'meta': {'AffectedNodes': [{'ModifiedNode': {
                    'FinalFields': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Balance': '1639921227',
                                    'Flags': 0, 'OwnerCount': 290, 'Sequence': 87194270},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '0D969662A3AD45BFD80DE3B57E66A6408040D16F3AA261BB01E0769BB96F6768',
                    'PreviousFields': {'Balance': '1639075739', 'Sequence': 87194269},
                    'PreviousTxnID': '2C82E758F1825AD71A1D7F8B778C2466E8EE883C2E8B7D620698F4A4DFEC3591',
                    'PreviousTxnLgrSeq': 89040647}}, {'ModifiedNode': {
                    'FinalFields': {'AMMID': 'CC7564FBE32710D4B022B8B33B41E28C8C2BE4096EAE7B57CD96822C7C81E439',
                                    'Account': 'rwmP5KpxyXazdGuUxWy94Vf35FTiwKFdTA', 'Balance': '16748184809',
                                    'Flags': 26214400, 'OwnerCount': 1, 'Sequence': 86795387},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '8862F75381FF1FDF13C8F727131A0CB257EB7AD816998F9A5463CE820A00EF0A',
                    'PreviousFields': {'Balance': '16749030312'},
                    'PreviousTxnID': 'EAB6F364C563FE11099092CA04D76ADF93AC629C0D45F399C8A2A6357325D4D1',
                    'PreviousTxnLgrSeq': 89040586}}, {'ModifiedNode': {'FinalFields': {
                    'Balance': {'currency': '58434F5245000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji', 'value': '-91783.70217347478'},
                    'Flags': 16908288, 'HighLimit': {'currency': '58434F5245000000000000000000000000000000',
                                                     'issuer': 'rwmP5KpxyXazdGuUxWy94Vf35FTiwKFdTA', 'value': '0'},
                    'HighNode': '0', 'LowLimit': {'currency': '58434F5245000000000000000000000000000000',
                                                  'issuer': 'r3dVizzUAS3U29WKaaSALqkieytA2LCoRe', 'value': '0'},
                    'LowNode': '988'}, 'LedgerEntryType': 'RippleState',
                    'LedgerIndex': '9BE256CCF7FEA1C0D4054BA2E6A9BED6200173A8EB8D591DE90D5F52A67C1D7D',
                    'PreviousFields': {'Balance': {
                        'currency': '58434F5245000000000000000000000000000000',
                        'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                        'value': '-91779.05674147478'}},
                    'PreviousTxnID': 'EAB6F364C563FE11099092CA04D76ADF93AC629C0D45F399C8A2A6357325D4D1',
                    'PreviousTxnLgrSeq': 89040586}}, {
                    'ModifiedNode': {
                        'FinalFields': {
                            'Balance': {
                                'currency': '58434F5245000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '-0.0000043871674'},
                            'Flags': 2228224,
                            'HighLimit': {
                                'currency': '58434F5245000000000000000000000000000000',
                                'issuer': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb',
                                'value': '1000000000000000e5'},
                            'HighNode': '0',
                            'LowLimit': {
                                'currency': '58434F5245000000000000000000000000000000',
                                'issuer': 'r3dVizzUAS3U29WKaaSALqkieytA2LCoRe',
                                'value': '0'},
                            'LowNode': '992'},
                        'LedgerEntryType': 'RippleState',
                        'LedgerIndex': 'EB06D028A949150D75259F80BABCB46F2D52FCA88171DFE90D6F8183D9C48810',
                        'PreviousFields': {
                            'Balance': {
                                'currency': '58434F5245000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '-4.6454363871674'}},
                        'PreviousTxnID': '2C82E758F1825AD71A1D7F8B778C2466E8EE883C2E8B7D620698F4A4DFEC3591',
                        'PreviousTxnLgrSeq': 89040647}}],
                    'TransactionIndex': 22,
                    'TransactionResult': 'tesSUCCESS'},
                        'status': 'success', 'validated': True}},
            {'result': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Fee': '15', 'Flags': 524288,
                        'Sequence': 87194265,
                        'SigningPubKey': '035566B011B878AA5EC3DA46FC01B9BC929F0E196D96F8C7D7B5C311AB261B207A',
                        'TakerGets': {'currency': '5A52505900000000000000000000000000000000',
                                      'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA', 'value': '626.952425'},
                        'TakerPays': '1', 'TransactionType': 'OfferCreate',
                        'TxnSignature': '3044022017DFAA086BB90FA67D8F1410FE7877B94BD683E8D1AA2D2614CA726D0C2BD32202206BA03D13FC31E286D6E1CC26D413AED0DC10EEED00F36E5ABF7A1D65F0C21B5C',
                        'ctid': 'C54EA5F100290000', 'date': 773043431,
                        'hash': '4988892147BD2B177DF9A23F2F001D2D68256189795D1F7907F50D9C97D59A15',
                        'inLedger': 89040369, 'ledger_index': 89040369, 'meta': {'AffectedNodes': [{'ModifiedNode': {
                    'FinalFields': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Balance': '1639920705',
                                    'Flags': 0, 'OwnerCount': 290, 'Sequence': 87194266},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '0D969662A3AD45BFD80DE3B57E66A6408040D16F3AA261BB01E0769BB96F6768',
                    'PreviousFields': {'Balance': '1633914474', 'Sequence': 87194265},
                    'PreviousTxnID': '8E3DD8865653618539619ECC263B3EB6101D2CAC66580EE2F56F1BAFEE589BDA',
                    'PreviousTxnLgrSeq': 89040369}}, {'ModifiedNode': {
                    'FinalFields': {'AMMID': 'FD4EDD6276A7081B3E9ED5ECDC3DB303DD50C85BBBEC8B7E31208732F74C9EEC',
                                    'Account': 'rJph4hcDHXEyyoe2CYM18McydukdTLvBhs', 'Balance': '120234563014',
                                    'Flags': 26214400, 'OwnerCount': 1, 'Sequence': 86796611},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '346B43E3F0D422B7D13EF82CDCFA7012C341E04FCD7891DAADC68AC58A54E87A',
                    'PreviousFields': {'Balance': '120240569260'},
                    'PreviousTxnID': '720F3B057390C9F75FD501F2965BD58404CEB184266514491527821E29D1BEC1',
                    'PreviousTxnLgrSeq': 89040285}}, {'ModifiedNode': {'FinalFields': {
                    'Balance': {'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji', 'value': '-12513719.29698804'},
                    'Flags': 16908288, 'HighLimit': {'currency': '5A52505900000000000000000000000000000000',
                                                     'issuer': 'rJph4hcDHXEyyoe2CYM18McydukdTLvBhs', 'value': '0'},
                    'HighNode': '0', 'LowLimit': {'currency': '5A52505900000000000000000000000000000000',
                                                  'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA', 'value': '0'},
                    'LowNode': '86'}, 'LedgerEntryType': 'RippleState',
                    'LedgerIndex': '9C610B2C8C2FCE98F831A49696E0EFE26F9EEE276A90A3C003A6CAD2895950CF',
                    'PreviousFields': {'Balance': {
                        'currency': '5A52505900000000000000000000000000000000',
                        'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                        'value': '-12513092.34456304'}},
                    'PreviousTxnID': '720F3B057390C9F75FD501F2965BD58404CEB184266514491527821E29D1BEC1',
                    'PreviousTxnLgrSeq': 89040285}}, {
                    'ModifiedNode': {
                        'FinalFields': {
                            'Balance': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '0'},
                            'Flags': 2228224,
                            'HighLimit': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb',
                                'value': '1000000000000000e5'},
                            'HighNode': '5',
                            'LowLimit': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA',
                                'value': '0'},
                            'LowNode': '8c'},
                        'LedgerEntryType': 'RippleState',
                        'LedgerIndex': 'A6146D9FE2A991182DAF96BC3DA249F9B12DB3668578275E714A286DB07DC738',
                        'PreviousFields': {
                            'Balance': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '-626.952425'}},
                        'PreviousTxnID': '8E3DD8865653618539619ECC263B3EB6101D2CAC66580EE2F56F1BAFEE589BDA',
                        'PreviousTxnLgrSeq': 89040369}}],
                    'TransactionIndex': 41,
                    'TransactionResult': 'tesSUCCESS'},
                        'status': 'success', 'validated': True}},
            {'result': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Fee': '25', 'Flags': 131072,
                        'Sequence': 87194264,
                        'SigningPubKey': '035566B011B878AA5EC3DA46FC01B9BC929F0E196D96F8C7D7B5C311AB261B207A',
                        'TakerGets': '6005880', 'TakerPays': {'currency': '5A52505900000000000000000000000000000000',
                                                              'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA',
                                                              'value': '626.952425'}, 'TransactionType': 'OfferCreate',
                        'TxnSignature': '30440220294A18B0DFA22370F0B73C4D9BAEA57F0116F23D653DE167EF2FA8F22F4BF91F0220560531D65F3C8B379335E4FCE183C0D66206F62021389156931EE455366B5677',
                        'ctid': 'C54EA5F100280000', 'date': 773043431,
                        'hash': '8E3DD8865653618539619ECC263B3EB6101D2CAC66580EE2F56F1BAFEE589BDA',
                        'inLedger': 89040369, 'ledger_index': 89040369, 'meta': {'AffectedNodes': [{'ModifiedNode': {
                    'FinalFields': {'Account': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', 'Balance': '1633914474',
                                    'Flags': 0, 'OwnerCount': 290, 'Sequence': 87194265},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '0D969662A3AD45BFD80DE3B57E66A6408040D16F3AA261BB01E0769BB96F6768',
                    'PreviousFields': {'Balance': '1639919058', 'Sequence': 87194264},
                    'PreviousTxnID': '5A371469AC1A4EC24DAADEF86B7DC5CC05092B4CDA54F5E3827A7C4110CD3DE6',
                    'PreviousTxnLgrSeq': 89039916}}, {'ModifiedNode': {'FinalFields': {
                    'Balance': {'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji', 'value': '-939.31573715844'}, 'Flags': 2228224,
                    'HighLimit': {'currency': '5A52505900000000000000000000000000000000',
                                  'issuer': 'rJtvvbBSExY3F3uhzE2nP2JPtXVztRRvsk', 'value': '100291546.334375'},
                    'HighNode': '0', 'LowLimit': {'currency': '5A52505900000000000000000000000000000000',
                                                  'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA', 'value': '0'},
                    'LowNode': '63'}, 'LedgerEntryType': 'RippleState',
                    'LedgerIndex': '6F52CDBA326BBDB7AC6E70312D11AD1737F1DAE22A081E298732EAECA03612C5',
                    'PreviousFields': {'Balance': {
                        'currency': '5A52505900000000000000000000000000000000',
                        'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                        'value': '-1566.26816215844'}},
                    'PreviousTxnID': 'D45E325907E80429CBF38A9000FEEC4CC88066ADB1E1B0BFBD7A789569E3E0CB',
                    'PreviousTxnLgrSeq': 89040350}}, {
                    'ModifiedNode': {
                        'FinalFields': {
                            'Balance': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '-626.952425'},
                            'Flags': 2228224,
                            'HighLimit': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb',
                                'value': '1000000000000000e5'},
                            'HighNode': '5',
                            'LowLimit': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA',
                                'value': '0'},
                            'LowNode': '8c'},
                        'LedgerEntryType': 'RippleState',
                        'LedgerIndex': 'A6146D9FE2A991182DAF96BC3DA249F9B12DB3668578275E714A286DB07DC738',
                        'PreviousFields': {
                            'Balance': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rrrrrrrrrrrrrrrrrrrrBZbvji',
                                'value': '0'}},
                        'PreviousTxnID': 'D5964F408007865570E2704BA5B1862445693C94DBC850549D702F86D129E628',
                        'PreviousTxnLgrSeq': 89023285}},
                    {'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rJtvvbBSExY3F3uhzE2nP2JPtXVztRRvsk',
                            'BookDirectory': 'DCDC6E8881CDC2E88EA5F5B55FCCDC599A177234EA44CB5958220692780EE96F',
                            'BookNode': '0',
                            'Flags': 0,
                            'OwnerNode': '1',
                            'Sequence': 84183480,
                            'TakerGets': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA',
                                'value': '306.0479708859419'},
                            'TakerPays': '2931136'},
                        'LedgerEntryType': 'Offer',
                        'LedgerIndex': 'A99D5011EF2A42FC59FEDDE120D27EC6AF46E0D07208BE45DCC0FC80CC016D6B',
                        'PreviousFields': {
                            'TakerGets': {
                                'currency': '5A52505900000000000000000000000000000000',
                                'issuer': 'rsxkrpsYaeTUdciSFJwvto7MKSrgGnvYvA',
                                'value': '933.0003958859419'},
                            'TakerPays': '8935695'},
                        'PreviousTxnID': 'D45E325907E80429CBF38A9000FEEC4CC88066ADB1E1B0BFBD7A789569E3E0CB',
                        'PreviousTxnLgrSeq': 89040350}},
                    {'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rJtvvbBSExY3F3uhzE2nP2JPtXVztRRvsk',
                            'Balance': '271215632',
                            'Flags': 0,
                            'OwnerCount': 30,
                            'Sequence': 84183482},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': 'F69959F08C3DE621692CF736FEBF967559AA14917229DEEB66B1717FEB7FF89A',
                        'PreviousFields': {
                            'Balance': '265211073'},
                        'PreviousTxnID': '00183393DF1D242B402804800A62205996F989A85335AA99A488A5D5C49679A0',
                        'PreviousTxnLgrSeq': 89040369}}],
                    'TransactionIndex': 40,
                    'TransactionResult': 'tesSUCCESS'},
                        'status': 'success', 'validated': True}}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_response)
        parsed_responses = []
        for tx_hash in self.hash_of_transactions:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            parsed_responses.append(parsed_response)
        expected_txs_details = [
            [TransferTx(tx_hash='B58F50CEF200DCA8A915C479AF389385CEFB7B282D0760DF3878E54BDA51AE1E', success=True,
                        from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                        to_address='rLYdNN9X7WdZ2Jm76vtDJdB9b6SZ7G1CMb', value=Decimal('0.000001'), symbol='XRP',
                        confirmations=0, block_height=89018917, block_hash=None,
                        date=datetime.datetime(2024, 6, 29, 7, 33, 51, tzinfo=UTC), memo='2017',
                        tx_fee=Decimal('0.000025'), token=None, index=None)], [], [], []
        ]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_responses):
            assert tx_details == expected_tx_details

    def test_get_address_txs(self):
        address_txs_mock_response = [
            {'result': {'account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'ledger_index_max': 89041683,
                        'ledger_index_min': 32570, 'limit': 50, 'marker': {'ledger': 89041642, 'seq': 65},
                        'status': 'success', 'transactions': [{'meta': {'AffectedNodes': [{'ModifiedNode': {
                    'FinalFields': {'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'Balance': '11459238429',
                                    'Flags': 0, 'OwnerCount': 0, 'Sequence': 77285543},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                    'PreviousFields': {'Balance': '11459238428'},
                    'PreviousTxnID': 'FC2D8EF47C079673FBF39AB8874A74D3D9EA76E5E580C3E77014141F057494BA',
                    'PreviousTxnLgrSeq': 89041682}}, {'ModifiedNode': {
                    'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610059',
                                    'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552343},
                    'LedgerEntryType': 'AccountRoot',
                    'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                    'PreviousFields': {'Balance': '4208610085', 'Sequence': 89552342},
                    'PreviousTxnID': '8D2B3A18963A6571B90FF27446777BC5A26B6D9655F64ADF534320738B137AEE',
                    'PreviousTxnLgrSeq': 89041682}}], 'TransactionIndex': 13, 'TransactionResult': 'tesSUCCESS',
                    'delivered_amount': '1'},
                    'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                           'Amount': '1', 'DeliverMax': '1',
                           'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                           'DestinationTag': 399202771, 'Fee': '25',
                           'Flags': 2147483648,
                           'LastLedgerSequence': 89041695, 'Memos': [{
                            'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {
                                'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {
                                'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {
                                'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {
                                'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {
                                'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {
                                'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {
                                'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {
                                'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {
                                'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {
                                'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {
                                'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {
                                'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {
                                'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {
                                'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {
                                'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                           'Sequence': 89552342,
                           'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                           'TransactionType': 'Payment',
                           'TxnSignature': '30450221009BDF3F353A9FCBBCB71048307904274CAB9029E99F24D6827D807ACF959095F30220386AB972EA826991EFC174842790A7AD684799579F3E1562B187073F8B0E4A32',
                           'date': 773048440,
                           'hash': '6ADFADCF19F2B25EB5332395FA68C986C52C74C3D7B3DE200282341F833EFFC2',
                           'inLedger': 89041682, 'ledger_index': 89041682},
                    'validated': True}, {'meta': {'AffectedNodes': [{
                    'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                            'Balance': '4208610085',
                            'Flags': 0,
                            'OwnerCount': 0,
                            'Sequence': 89552342},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                        'PreviousFields': {
                            'Balance': '4208610111',
                            'Sequence': 89552341},
                        'PreviousTxnID': '430CF23DE4FCAE3457CC07A57BC260FE6BA06CA69902120A809F7959594D5783',
                        'PreviousTxnLgrSeq': 89041681}},
                    {
                        'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                'Balance': '1955609156398',
                                'Flags': 131072,
                                'OwnerCount': 1,
                                'Sequence': 115792},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                            'PreviousFields': {
                                'Balance': '1955609156397'},
                            'PreviousTxnID': 'DFBBF1554BD051D96DC740F5F85C6A653036E9C94E11372132A95F8F633BB41D',
                            'PreviousTxnLgrSeq': 89041681}}],
                    'TransactionIndex': 12,
                    'TransactionResult': 'tesSUCCESS',
                    'delivered_amount': '1'},
                    'tx': {
                        'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                        'Amount': '1',
                        'DeliverMax': '1',
                        'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                        'DestinationTag': 500301078,
                        'Fee': '25',
                        'Flags': 2147483648,
                        'LastLedgerSequence': 89041695,
                        'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89552341,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '304402205E0F92045707BBE873933CA60BD4EFE43205FA4C2525051C3187A6AB8B95AADB02200C383F5CC276F8AA896EDD766C998B266FAE919D872B3BEADB02BBA373D82DDA',
                        'date': 773048440,
                        'hash': '8D2B3A18963A6571B90FF27446777BC5A26B6D9655F64ADF534320738B137AEE',
                        'inLedger': 89041682,
                        'ledger_index': 89041682},
                    'validated': True}, {'meta': {
                    'AffectedNodes': [{'ModifiedNode': {
                        'FinalFields': {'Account': 'rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV', 'Balance': '9099884047395',
                                        'Flags': 1179648,
                                        'MessageKey': '0200000000000000000000000005CDB1526F6E224E02919A4C018D9784EA25EB3D',
                                        'OwnerCount': 1, 'Sequence': 3654}, 'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': '384FB0B8D3D82F5C0EDD8181255BD89068EB56336EEA1E69380DCA4E37181317',
                        'PreviousFields': {'Balance': '9099884047394'},
                        'PreviousTxnID': '181D1D96F812735CC6A853CA42B5CBDD1451B13F13E79784A8395F2368899D58',
                        'PreviousTxnLgrSeq': 89041680}}, {'ModifiedNode': {
                        'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610111',
                                        'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552341},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                        'PreviousFields': {'Balance': '4208610137', 'Sequence': 89552340},
                        'PreviousTxnID': 'A938E9CAC2F5352B2C4D9D25D1E0DF49FCBBB992DFD96C353DB17B50C30AD392',
                        'PreviousTxnLgrSeq': 89041680}}], 'TransactionIndex': 16, 'TransactionResult': 'tesSUCCESS',
                    'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                     'DeliverMax': '1',
                                                     'Destination': 'rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV',
                                                     'DestinationTag': 209141062, 'Fee': '25', 'Flags': 2147483648,
                                                     'LastLedgerSequence': 89041695, 'Memos': [{'Memo': {
                        'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                        {'Memo': {
                            'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                        {'Memo': {
                            'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                        {'Memo': {
                            'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                        {'Memo': {
                            'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                        {'Memo': {
                            'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                        {'Memo': {
                            'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                        {'Memo': {
                            'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                        {'Memo': {
                            'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                        {'Memo': {
                            'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                        {'Memo': {
                            'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                        {'Memo': {
                            'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                        {'Memo': {
                            'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                        {'Memo': {
                            'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                        {'Memo': {
                            'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                        {'Memo': {
                            'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                     'Sequence': 89552340,
                                                     'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                     'TransactionType': 'Payment',
                                                     'TxnSignature': '304402205D950B451A2B69199C40D60E9E25BDE5900ED95EC354B1F0D4491E7E361F09E002205927ADEE26A66AEAE5D782225DD83015A079B4141B60654F63D532D4ABEA979F',
                                                     'date': 773048431,
                                                     'hash': '430CF23DE4FCAE3457CC07A57BC260FE6BA06CA69902120A809F7959594D5783',
                                                     'inLedger': 89041681, 'ledger_index': 89041681},
                    'validated': True},
                    {'meta': {'AffectedNodes': [{'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                            'Balance': '9951638171', 'Flags': 0,
                            'OwnerCount': 0, 'Sequence': 77285543},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                        'PreviousFields': {'Balance': '9951638170'},
                        'PreviousTxnID': '9D698BCF44D869F85383BA83D3AF5981B6B3EDF9274EBF24247F0FD1EF3CCB32',
                        'PreviousTxnLgrSeq': 89041679}}, {'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                            'Balance': '4208610137', 'Flags': 0,
                            'OwnerCount': 0, 'Sequence': 89552340},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                        'PreviousFields': {'Balance': '4208610163',
                                           'Sequence': 89552339},
                        'PreviousTxnID': 'D1504B3F7CE3649F522249423CF62F8BCA463F05A4439BFC0242D2F57E498412',
                        'PreviousTxnLgrSeq': 89041680}}],
                        'TransactionIndex': 18,
                        'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'},
                        'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                               'Amount': '1', 'DeliverMax': '1',
                               'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                               'DestinationTag': 399202771, 'Fee': '25',
                               'Flags': 2147483648,
                               'LastLedgerSequence': 89041692, 'Memos': [{
                                'Memo': {
                                    'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {
                                    'Memo': {
                                        'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {
                                    'Memo': {
                                        'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {
                                    'Memo': {
                                        'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {
                                    'Memo': {
                                        'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {
                                    'Memo': {
                                        'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {
                                    'Memo': {
                                        'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {
                                    'Memo': {
                                        'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {
                                    'Memo': {
                                        'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {
                                    'Memo': {
                                        'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {
                                    'Memo': {
                                        'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {
                                    'Memo': {
                                        'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {
                                    'Memo': {
                                        'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {
                                    'Memo': {
                                        'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {
                                    'Memo': {
                                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {
                                    'Memo': {
                                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                               'Sequence': 89552339,
                               'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                               'TransactionType': 'Payment',
                               'TxnSignature': '3045022100A235D21E9F91BA0F316860BD1673840B096CBEA1EF477BF3528B28B8ECF399D102202217B3DD2B1BCCC9031198469E2A12F18FC1DB020FFE6F62E32DA5B68D2163C1',
                               'date': 773048430,
                               'hash': 'A938E9CAC2F5352B2C4D9D25D1E0DF49FCBBB992DFD96C353DB17B50C30AD392',
                               'inLedger': 89041680, 'ledger_index': 89041680},
                        'validated': True}, {'meta': {'AffectedNodes': [{
                        'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rJMB7w47XsRVou7sE79DKzNvAquZwARbQG',
                                'Balance': '2443324687',
                                'Flags': 0,
                                'OwnerCount': 83,
                                'Sequence': 67396477},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'AF82D22C0FD9FF69C5AFA347A35C5EF0605D11BF818B2CE7442C378B4C05D49B',
                            'PreviousFields': {
                                'Balance': '2443324686'},
                            'PreviousTxnID': 'FBA0CB7211C55D63B044D7B6095D84CB1AA6E574C2ED44D1F91D732A1B92F91D',
                            'PreviousTxnLgrSeq': 89041677}},
                        {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610163',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552339},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610189',
                                    'Sequence': 89552338},
                                'PreviousTxnID': 'F689870A66E918C927639CA9E7FB50EB158B92FBE38A4D2E499393E4B93B0F42',
                                'PreviousTxnLgrSeq': 89041679}}],
                        'TransactionIndex': 17,
                        'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'},
                        'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                            'Amount': '1',
                            'DeliverMax': '1',
                            'Destination': 'rJMB7w47XsRVou7sE79DKzNvAquZwARbQG',
                            'DestinationTag': 2017,
                            'Fee': '25',
                            'Flags': 2147483648,
                            'LastLedgerSequence': 89041692,
                            'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552338,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '30440220051F8ED6DF3B2AA21913F290504725BFC98BD200E5F9255B1D451F8FF84DCCE202206970B1A32F43DADCCCBC4F3AF191DFC643DA0C9C19035593A47BE10301514768',
                            'date': 773048430,
                            'hash': 'D1504B3F7CE3649F522249423CF62F8BCA463F05A4439BFC0242D2F57E498412',
                            'inLedger': 89041680,
                            'ledger_index': 89041680},
                        'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610189',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552338},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610215', 'Sequence': 89552337},
                            'PreviousTxnID': '6F18B0E6EDD1E9D25127FD00EC52CF7CE28DDE65E21D3DD537D60308D9192EAF',
                            'PreviousTxnLgrSeq': 89041679}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'Balance': '187826979066',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 199461},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                            'PreviousFields': {'Balance': '187826979065'},
                            'PreviousTxnID': '93C94FED62F816D9F50287B01033E25F55487F1AEEAFB7F0A9A197A1EA23A54A',
                            'PreviousTxnLgrSeq': 89041677}}], 'TransactionIndex': 16, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                                         'DestinationTag': 3426593446, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041692, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552337,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '304402206E38B5FB115B9AF816970FE47EA19227BDF59A8CB51A838F67431E726D72831A02207279C844C99971220009636585DE37DD69E495A4B7341E75472DDD7B837445F5',
                                                         'date': 773048422,
                                                         'hash': 'F689870A66E918C927639CA9E7FB50EB158B92FBE38A4D2E499393E4B93B0F42',
                                                         'inLedger': 89041679, 'ledger_index': 89041679},
                        'validated': True},
                    {'meta': {'AffectedNodes': [{'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE',
                            'Balance': '264210910677', 'Flags': 131072,
                            'OwnerCount': 0, 'Sequence': 63582770},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': '7C8019185EFF5095E320FA4A8204D9455D1BB7F91FEAB383181D6895EACA15EB',
                        'PreviousFields': {'Balance': '264210910676'},
                        'PreviousTxnID': 'AEDE3448C0690E5D38589E4316651C2C54423EE9EAAC81F6061A6CE5EFD46B7F',
                        'PreviousTxnLgrSeq': 89041677}}, {'ModifiedNode': {
                        'FinalFields': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                            'Balance': '4208610215', 'Flags': 0,
                            'OwnerCount': 0, 'Sequence': 89552337},
                        'LedgerEntryType': 'AccountRoot',
                        'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                        'PreviousFields': {'Balance': '4208610241',
                                           'Sequence': 89552336},
                        'PreviousTxnID': '47E445A17D30967EB773E80F7F6D1F8796116FD1D16CE69638DEEB8A7B6AF094',
                        'PreviousTxnLgrSeq': 89041678}}],
                        'TransactionIndex': 15,
                        'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'},
                        'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                               'Amount': '1', 'DeliverMax': '1',
                               'Destination': 'rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE',
                               'DestinationTag': 176203189, 'Fee': '25',
                               'Flags': 2147483648,
                               'LastLedgerSequence': 89041692, 'Memos': [{
                                'Memo': {
                                    'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {
                                    'Memo': {
                                        'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {
                                    'Memo': {
                                        'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {
                                    'Memo': {
                                        'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {
                                    'Memo': {
                                        'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {
                                    'Memo': {
                                        'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {
                                    'Memo': {
                                        'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {
                                    'Memo': {
                                        'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {
                                    'Memo': {
                                        'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {
                                    'Memo': {
                                        'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {
                                    'Memo': {
                                        'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {
                                    'Memo': {
                                        'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {
                                    'Memo': {
                                        'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {
                                    'Memo': {
                                        'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {
                                    'Memo': {
                                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {
                                    'Memo': {
                                        'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                               'Sequence': 89552336,
                               'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                               'TransactionType': 'Payment',
                               'TxnSignature': '30450221009F7995D70CCDEA64B571DDBC87F709D4F6E3C246C175B38731654A9035883523022065567578556941AB6985BA62C0EFFFBFB06AD138E4C16D4DACAAD38F40CCFAB8',
                               'date': 773048422,
                               'hash': '6F18B0E6EDD1E9D25127FD00EC52CF7CE28DDE65E21D3DD537D60308D9192EAF',
                               'inLedger': 89041679, 'ledger_index': 89041679},
                        'validated': True}, {'meta': {'AffectedNodes': [{
                        'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwHkJBjh7UJodTczQsF1BV5pLv7SgGv4j5',
                                'Balance': '594145976',
                                'Flags': 0,
                                'OwnerCount': 174,
                                'Sequence': 67795996},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'A089E16A5603789E58D917A7ED98EFB84CE0F013FA02FBCA91160C9D1038D3A3',
                            'PreviousFields': {
                                'Balance': '594145975'},
                            'PreviousTxnID': '076F25E8E780D53958A3BFCD9D1CAC6CCA268767B27D8CAA13C93F3411C6D53C',
                            'PreviousTxnLgrSeq': 89041675}},
                        {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610241',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552336},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610267',
                                    'Sequence': 89552335},
                                'PreviousTxnID': '757944996FF1B20205F03FE45143AA49B0AF99824FCADB31933456BD8A16B729',
                                'PreviousTxnLgrSeq': 89041677}}],
                        'TransactionIndex': 16,
                        'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'},
                        'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                            'Amount': '1',
                            'DeliverMax': '1',
                            'Destination': 'rwHkJBjh7UJodTczQsF1BV5pLv7SgGv4j5',
                            'DestinationTag': 2017,
                            'Fee': '25',
                            'Flags': 2147483648,
                            'LastLedgerSequence': 89041690,
                            'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552335,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '30440220685432B77026DC9B9E4E0AE085AB7253ECA27BB819F50A2B11821C876D432C57022002CFCC266488BB83011839B42F6C633BB005E85817A7A251F9A9505176C5DA52',
                            'date': 773048421,
                            'hash': '47E445A17D30967EB773E80F7F6D1F8796116FD1D16CE69638DEEB8A7B6AF094',
                            'inLedger': 89041678,
                            'ledger_index': 89041678},
                        'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rPJURMhyJdkA19zZyqwv1bruUo9Y8Pyovo', 'Balance': '16438654',
                                            'Flags': 0, 'OwnerCount': 3, 'Sequence': 85108812},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '1DC62FD9EA546A52A74ABF4392DDE34033A978C4C369E3D6807C0560CA899EE1',
                            'PreviousFields': {'Balance': '16438653'},
                            'PreviousTxnID': '5241CEDCBAFF03B6809C8B6B3C6DE7ABB80C53A04CB03411F43D5D4727290799',
                            'PreviousTxnLgrSeq': 89041675}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610267',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552335},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610293', 'Sequence': 89552334},
                            'PreviousTxnID': '580ED9F542CA5835E5E6510BA1DB462A96E5299D3F80660FE0C8517168F45B17',
                            'PreviousTxnLgrSeq': 89041676}}], 'TransactionIndex': 109,
                        'TransactionResult': 'tesSUCCESS', 'delivered_amount': '1'}, 'tx': {
                        'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                        'Destination': 'rPJURMhyJdkA19zZyqwv1bruUo9Y8Pyovo', 'DestinationTag': 2017, 'Fee': '25',
                        'Flags': 2147483648, 'LastLedgerSequence': 89041690, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89552334,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '3045022100846A00E02FAF17155F8E4AD825356901ADAFC5EA9ECF5820E18219861DC3E18C02205EACAA0F6993BD5ACEE728CE0E6EE4A00065C7AB9845DF0F86FAB6B45AF04C98',
                        'date': 773048420, 'hash': '757944996FF1B20205F03FE45143AA49B0AF99824FCADB31933456BD8A16B729',
                        'inLedger': 89041677, 'ledger_index': 89041677}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'Balance': '8496781718',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 77285543},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                            'PreviousFields': {'Balance': '8496781717'},
                            'PreviousTxnID': '7830B40DDDC46AA11870B90517A11CB56104665453EE2560ECC2531DA924027B',
                            'PreviousTxnLgrSeq': 89041676}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610293',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552334},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610319', 'Sequence': 89552333},
                            'PreviousTxnID': '1B416E66DEF1287CBB9A78F1DD6B3D7A60699684054A42863F88A7E147F43E88',
                            'PreviousTxnLgrSeq': 89041675}}], 'TransactionIndex': 212,
                        'TransactionResult': 'tesSUCCESS', 'delivered_amount': '1'}, 'tx': {
                        'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                        'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'DestinationTag': 395224681, 'Fee': '25',
                        'Flags': 2147483648, 'LastLedgerSequence': 89041689, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89552333,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '3044022053FE439EE585D934BD37C1C8F3CBE1AF49F202A25FD2275726E9651FDF15C60B0220266C27C86255C362B4B37B4336213EF641A31A4078A30B0536CDEF04AFED6287',
                        'date': 773048412, 'hash': '580ED9F542CA5835E5E6510BA1DB462A96E5299D3F80660FE0C8517168F45B17',
                        'inLedger': 89041676, 'ledger_index': 89041676}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610319',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552333},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610345', 'Sequence': 89552332},
                            'PreviousTxnID': '7E126245BA064F881AFF99F9B57834E66716599A7AABF32B8153F46E236FCA85',
                            'PreviousTxnLgrSeq': 89041674}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'r35mbUmndYnnqUWWWki4K1H6NdUWAgvQR7', 'Balance': '244242234319',
                                            'Flags': 131072, 'OwnerCount': 0, 'Sequence': 76774679},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'EE137AB57196CEEEA462D11163CDEF1C8188C05CB69BAC6BE9B9EA1A6820AD06',
                            'PreviousFields': {'Balance': '244242234318'},
                            'PreviousTxnID': 'FE12CD3B6973ED9132AF25A576AC5D78230963B3D9F5B2FEE6652AFDBD7E6E75',
                            'PreviousTxnLgrSeq': 89041205}}], 'TransactionIndex': 13, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'r35mbUmndYnnqUWWWki4K1H6NdUWAgvQR7',
                                                         'DestinationTag': 2017, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041689, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552332,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3044022053DAB00766D43BBE728DF59EC246C55684F03217C533EFF15A51A6B3426371ED02205A349666A90C4C331B2A9632520BB90995A6267C12D64B752207AE427B60AFF0',
                                                         'date': 773048411,
                                                         'hash': '1B416E66DEF1287CBB9A78F1DD6B3D7A60699684054A42863F88A7E147F43E88',
                                                         'inLedger': 89041675, 'ledger_index': 89041675},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                                'Balance': '8496758490', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 77285543},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                            'PreviousFields': {'Balance': '8496758489'},
                            'PreviousTxnID': '6221DFE3ECB5E6037C673B74D75F8691899D2B47C1C76CFF014232C81C61833C',
                            'PreviousTxnLgrSeq': 89041673}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610345',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552332},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610371',
                                    'Sequence': 89552331},
                                'PreviousTxnID': '152F94CE06E5AADE161A8BA86462A56498E797953D4BC4C5215415BE9A3418FE',
                                'PreviousTxnLgrSeq': 89041674}}],
                            'TransactionIndex': 8,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'DestinationTag': 399237106,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041686, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552331,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100A94CA80A887D1C6E3DF4406514A25FAD4A5A1750C1EA876FEE027DD44C81DF3B022026C5C9FE2295F4331FDF4BE604C73B9A098C8A27EE59E8EE2295E79E9477B302',
                            'date': 773048410,
                            'hash': '7E126245BA064F881AFF99F9B57834E66716599A7AABF32B8153F46E236FCA85',
                            'inLedger': 89041674, 'ledger_index': 89041674}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rD37r1cciGqmdBpqou2DneEiWA1iQsAphP', 'Balance': '3240706154019',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 83694438},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'A950B1061997F92CE4F80448E57F858027C9459B4F05DE374BAAEDC0A9C9D83A',
                            'PreviousFields': {'Balance': '3240706154018'},
                            'PreviousTxnID': '23C8E60ACF1F2B8AE9FAC06F8163736551A5E944957CF8611D1D01BF10D592E5',
                            'PreviousTxnLgrSeq': 89041672}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610371',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552331},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610397', 'Sequence': 89552330},
                            'PreviousTxnID': '0DB90AE69F19B9D3292D1D26486A2D548C152B37C7D0BCC71D82D623FF7FAE64',
                            'PreviousTxnLgrSeq': 89041673}}], 'TransactionIndex': 7, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rD37r1cciGqmdBpqou2DneEiWA1iQsAphP',
                                                         'DestinationTag': 2437, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041686, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552330,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '30440220472734261718353331B3220F0B0EF3E22A9112E2F06783AAAADBB7D592589283022010A2E4308B95E853D2366E8530982C42EDDFF142582C6EF2EAEBC3A8275CD7F6',
                                                         'date': 773048410,
                                                         'hash': '152F94CE06E5AADE161A8BA86462A56498E797953D4BC4C5215415BE9A3418FE',
                                                         'inLedger': 89041674, 'ledger_index': 89041674},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE',
                                'Balance': '263882236666', 'Flags': 131072,
                                'OwnerCount': 0, 'Sequence': 63582770},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '7C8019185EFF5095E320FA4A8204D9455D1BB7F91FEAB383181D6895EACA15EB',
                            'PreviousFields': {'Balance': '263882236665'},
                            'PreviousTxnID': '8EEB41140D71E2DD2803E102270113DC06D4129CC1F05AB679FC092DE6DEF943',
                            'PreviousTxnLgrSeq': 89041671}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610397',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552330},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610423',
                                    'Sequence': 89552329},
                                'PreviousTxnID': 'B7C4B5B87C51F39847B6F6DDA67B086D3920841D2301D7299E867D29DF5D10CD',
                                'PreviousTxnLgrSeq': 89041672}}],
                            'TransactionIndex': 174,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE', 'DestinationTag': 350081973,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041686, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552329,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100ECABB1BCF53E6962E25133D9BD686ED6A8B534DD505A47D13E53BC331524064D02200D2F571776689EC4B9C940DCCF15AD78C5EE501BB2944ED10554CE8C012DC113',
                            'date': 773048401,
                            'hash': '0DB90AE69F19B9D3292D1D26486A2D548C152B37C7D0BCC71D82D623FF7FAE64',
                            'inLedger': 89041673, 'ledger_index': 89041673}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rs2dgzYeqYqsk8bvkQR5YPyqsXYcA24MP2', 'Balance': '2828988274200',
                                            'Flags': 131072, 'OwnerCount': 9, 'Sequence': 886950},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '64B6FFE42CFD12696CE8BB04843DAC143820CF5BC4EFB10F51C293CB9B77C14F',
                            'PreviousFields': {'Balance': '2828988274199'},
                            'PreviousTxnID': '6BCD091946DEBB74764B0C8C8E2D237EBF2608D0BFAA8FB31E7CAF7F6C7FF59B',
                            'PreviousTxnLgrSeq': 89041672}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610423',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552329},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610449', 'Sequence': 89552328},
                            'PreviousTxnID': '25C6BD0AD20674706C9426DD38A52792D52D2E779A65CDE5D20FE1F636E07509',
                            'PreviousTxnLgrSeq': 89041671}}], 'TransactionIndex': 156,
                        'TransactionResult': 'tesSUCCESS', 'delivered_amount': '1'}, 'tx': {
                        'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                        'Destination': 'rs2dgzYeqYqsk8bvkQR5YPyqsXYcA24MP2', 'DestinationTag': 476405, 'Fee': '25',
                        'Flags': 2147483648, 'LastLedgerSequence': 89041684, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89552328,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '304402200466DF9A9547B01FDB9A15E24D90F33E5FD7A729D8845CE29E4D621C83C764A902204EFA5B361BE11328637BD625E0D121EF5F8B4D81E361B131F55062C152D86148',
                        'date': 773048400, 'hash': 'B7C4B5B87C51F39847B6F6DDA67B086D3920841D2301D7299E867D29DF5D10CD',
                        'inLedger': 89041672, 'ledger_index': 89041672}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610449',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552328},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610475', 'Sequence': 89552327},
                            'PreviousTxnID': '24DB11A39E741B1618D78C036BE98060875A7D67D1483FB8FE40B4EFD2DE385A',
                            'PreviousTxnLgrSeq': 89041671}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh', 'Balance': '1954893782721',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 115792},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                            'PreviousFields': {'Balance': '1954893782720'},
                            'PreviousTxnID': 'EB00A0EA3327D0E250CF60377F33153A358C38C4081301A73C5AB2F490E9E079',
                            'PreviousTxnLgrSeq': 89041670}}], 'TransactionIndex': 1, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                                         'DestinationTag': 7468142, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041684, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552327,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3044022017005B8E9B452E9472EF208E34D84464047A1B792FD80B4C1412B8C2BD3DE9D6022019F27914EBD86B342F058DEA44BFAA4CE47CA2C2F81CCD7EBD5A53BF85A87604',
                                                         'date': 773048392,
                                                         'hash': '25C6BD0AD20674706C9426DD38A52792D52D2E779A65CDE5D20FE1F636E07509',
                                                         'inLedger': 89041671, 'ledger_index': 89041671},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
                                'Balance': '22379954', 'Flags': 0,
                                'OwnerCount': 4, 'Sequence': 75027596},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '193CC0FF109E95DCC5C6A194062C8DA5D6AF686B58F25F37741C9F832239A220',
                            'PreviousFields': {'Balance': '22379953'},
                            'PreviousTxnID': 'C2BC31683039EA1B5EBFCD1009E2E72BEA54455D025B59A1E2A4BF68905A4568',
                            'PreviousTxnLgrSeq': 89041669}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610475',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552327},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610501',
                                    'Sequence': 89552326},
                                'PreviousTxnID': '9077C56BFA0CD5CA0E84FDBAD4D88B694792DC9A1FAACEF67E448EB140EA2C7A',
                                'PreviousTxnLgrSeq': 89041670}}],
                            'TransactionIndex': 0,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041684, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552326,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100EE0E862089A869D5A36AB0AE5E94E5B700B8C384FC908AF3D2B486A93EBD1E3A02202CF1181954C258E80D428A757BC2228FFC54F0AD33DCA4AA501461D0B9F2DC20',
                            'date': 773048392,
                            'hash': '24DB11A39E741B1618D78C036BE98060875A7D67D1483FB8FE40B4EFD2DE385A',
                            'inLedger': 89041671, 'ledger_index': 89041671}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610501',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552326},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610527', 'Sequence': 89552325},
                            'PreviousTxnID': 'C2BC31683039EA1B5EBFCD1009E2E72BEA54455D025B59A1E2A4BF68905A4568',
                            'PreviousTxnLgrSeq': 89041669}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'Balance': '186579642265',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 199461},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                            'PreviousFields': {'Balance': '186579642264'},
                            'PreviousTxnID': 'D2F916037122A758AD72BDDB693FF4A014DF2EC29E242B3FF7B5A5D03D38C1AA',
                            'PreviousTxnLgrSeq': 89041667}}], 'TransactionIndex': 7, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                                         'DestinationTag': 2476714657, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041682, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552325,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100A245364DF9CFCB89E2E0A6BBDF5E3164C43F070B18A85D3C472946546F62F59502204E2CE61A1182FD16388432C2D6AB6EB14C5D4C65E26D1D64272CF8E4FA74207D',
                                                         'date': 773048391,
                                                         'hash': '9077C56BFA0CD5CA0E84FDBAD4D88B694792DC9A1FAACEF67E448EB140EA2C7A',
                                                         'inLedger': 89041670, 'ledger_index': 89041670},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
                                'Balance': '22379953', 'Flags': 0,
                                'OwnerCount': 4, 'Sequence': 75027596},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '193CC0FF109E95DCC5C6A194062C8DA5D6AF686B58F25F37741C9F832239A220',
                            'PreviousFields': {'Balance': '22379952'},
                            'PreviousTxnID': '780D6FABFF72E89905AB9C09B3B82F88874216599FC962C1ED1E1AD1E1CBCA16',
                            'PreviousTxnLgrSeq': 89041667}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610527',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552325},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610553',
                                    'Sequence': 89552324},
                                'PreviousTxnID': 'D9E223380CAA7C4EDC3D22186C828D20048573E56317B6E3BD79C6243240B059',
                                'PreviousTxnLgrSeq': 89041669}}],
                            'TransactionIndex': 18,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041682, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552324,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402202F510C545EBBDEF05EE777BAF1F67CCC100054C1A2B42D6E861CF1939295A928022065EA4CE0C64BA0A29D0642763D3EAECAD4A07278242953CBA76044448ABDFCD5',
                            'date': 773048390,
                            'hash': 'C2BC31683039EA1B5EBFCD1009E2E72BEA54455D025B59A1E2A4BF68905A4568',
                            'inLedger': 89041669, 'ledger_index': 89041669}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610553',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552324},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610579', 'Sequence': 89552323},
                            'PreviousTxnID': '6AB62EB5D93E8C1B5FB9AB8D5D0E2A4B5A2D5F80F6CC682B5BF0D83F9FFC5418',
                            'PreviousTxnLgrSeq': 89041668}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh', 'Balance': '1953587261220',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 115792},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                            'PreviousFields': {'Balance': '1953587261219'},
                            'PreviousTxnID': '38B881EB67F7F3085B7336AC5C8914DC7C116B15C3E590D898B2BB37638D864E',
                            'PreviousTxnLgrSeq': 89041667}}], 'TransactionIndex': 17, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                                         'DestinationTag': 7468142, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041682, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552323,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '304502210080ED96753E61349FB0F0EDDE4DFF49A4D65040E53AA1E9F74B77F5B02156651502203D3E183822419699E0EE038C7271DB85652720628A22A171B6E769650739199D',
                                                         'date': 773048390,
                                                         'hash': 'D9E223380CAA7C4EDC3D22186C828D20048573E56317B6E3BD79C6243240B059',
                                                         'inLedger': 89041669, 'ledger_index': 89041669},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rK8v2KxgLQSgarqSuQ7qwXrN799xp7o2T8',
                                'Balance': '15785367569', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 85322385},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '40035FD4BBB6402EF6A0511736A7038960107214A0370E334F960E2E148A608D',
                            'PreviousFields': {'Balance': '15785367568'},
                            'PreviousTxnID': 'C7271A2C9FDE58585F23CA79828F6DBF6836549329D66E6FAC753DB095F4A1EB',
                            'PreviousTxnLgrSeq': 89041665}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610579',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552323},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610605',
                                    'Sequence': 89552322},
                                'PreviousTxnID': '38B881EB67F7F3085B7336AC5C8914DC7C116B15C3E590D898B2BB37638D864E',
                                'PreviousTxnLgrSeq': 89041667}}],
                            'TransactionIndex': 17,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rK8v2KxgLQSgarqSuQ7qwXrN799xp7o2T8', 'DestinationTag': 3803555883,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041680, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552322,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402202BCE93F8744ECDC8C18940DC2AC075C6F2C05FD054960C22E00CC7A42E2534BE0220090F3E4963EC2FB741A038B40F7CFCF83FC4AE1AC7558916295F477A818DDDC4',
                            'date': 773048381,
                            'hash': '6AB62EB5D93E8C1B5FB9AB8D5D0E2A4B5A2D5F80F6CC682B5BF0D83F9FFC5418',
                            'inLedger': 89041668, 'ledger_index': 89041668}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610605',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552322},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610631', 'Sequence': 89552321},
                            'PreviousTxnID': '780D6FABFF72E89905AB9C09B3B82F88874216599FC962C1ED1E1AD1E1CBCA16',
                            'PreviousTxnLgrSeq': 89041667}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh', 'Balance': '1953587261219',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 115792},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                            'PreviousFields': {'Balance': '1953587261218'},
                            'PreviousTxnID': 'E58BEA97C8CCA7D09BDDF33BC37607227D6A14172C30A250642F51E1E6578D09',
                            'PreviousTxnLgrSeq': 89041667}}], 'TransactionIndex': 34, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                                         'DestinationTag': 7468142, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041680, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552321,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100AB55219E4A6EA9093F9C8F9432948CEF2028FAE8C423FEDBFF9EE8F51703E0DC02200511DF45DC1BD4FA76FAA0B8855BE50D581AA396AF0F9A3A92561D920E331544',
                                                         'date': 773048380,
                                                         'hash': '38B881EB67F7F3085B7336AC5C8914DC7C116B15C3E590D898B2BB37638D864E',
                                                         'inLedger': 89041667, 'ledger_index': 89041667},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
                                'Balance': '22379952', 'Flags': 0,
                                'OwnerCount': 4, 'Sequence': 75027596},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '193CC0FF109E95DCC5C6A194062C8DA5D6AF686B58F25F37741C9F832239A220',
                            'PreviousFields': {'Balance': '22379951'},
                            'PreviousTxnID': '00EFFD2E107BE8D5DD0321BB3BDB67C52E85EBB0035F8460B2D8C07A7FB15C66',
                            'PreviousTxnLgrSeq': 89041665}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610631',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552321},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610657',
                                    'Sequence': 89552320},
                                'PreviousTxnID': 'D2F916037122A758AD72BDDB693FF4A014DF2EC29E242B3FF7B5A5D03D38C1AA',
                                'PreviousTxnLgrSeq': 89041667}}],
                            'TransactionIndex': 33,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041680, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552320,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100B61B13FC7059D63338393BE76253A1A4032CABA6EF077146B4D64788B68B806C022003AD4DE09D86685583CCE87B72292C2FB4BED69E0099AD0C11BEF083ACC99BE7',
                            'date': 773048380,
                            'hash': '780D6FABFF72E89905AB9C09B3B82F88874216599FC962C1ED1E1AD1E1CBCA16',
                            'inLedger': 89041667, 'ledger_index': 89041667}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610657',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552320},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610683', 'Sequence': 89552319},
                            'PreviousTxnID': '3BBC1F2463A112E3726B46292D8B56F81A2A848B7AF04217DDADA968C9B24730',
                            'PreviousTxnLgrSeq': 89041665}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'Balance': '186579642264',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 199461},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                            'PreviousFields': {'Balance': '186579642263'},
                            'PreviousTxnID': '3BBC1F2463A112E3726B46292D8B56F81A2A848B7AF04217DDADA968C9B24730',
                            'PreviousTxnLgrSeq': 89041665}}], 'TransactionIndex': 32, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                                         'DestinationTag': 2476714657, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041680, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552319,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3044022011599C01099B3BE17C59E8A363ADD12545AC86D8CEC9758D639323ED3DCAD5B6022009E8FC23EFD0D90CA1E35B25E8A92D29BAB1D9998220113FEB36A86DEF0799BB',
                                                         'date': 773048380,
                                                         'hash': 'D2F916037122A758AD72BDDB693FF4A014DF2EC29E242B3FF7B5A5D03D38C1AA',
                                                         'inLedger': 89041667, 'ledger_index': 89041667},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208610683', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552319},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610709',
                                               'Sequence': 89552318},
                            'PreviousTxnID': '00B1BC7FC5AB7EF7C054445FBFA965AEE1DD3BF03E8207D18BF3AAC45B2889BB',
                            'PreviousTxnLgrSeq': 89041664}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                    'Balance': '186579642263',
                                    'Flags': 131072,
                                    'OwnerCount': 1,
                                    'Sequence': 199461},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                                'PreviousFields': {
                                    'Balance': '186579642262'},
                                'PreviousTxnID': '7922A99A933FE3D78B8D7410E51126582A59AA79C14B568A06FB19390205A7F7',
                                'PreviousTxnLgrSeq': 89041663}}],
                            'TransactionIndex': 22,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'DestinationTag': 2476714657,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041678, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552318,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '30440220355340A222EF24E24B7804FE6337ED93EB7ABB94A3091A5DBC8BCDAF13BDAB1C02205B5698313442BB3B485E642FA0EAAB091267360BEB7AA949BE3BD370A57AF409',
                            'date': 773048371,
                            'hash': '3BBC1F2463A112E3726B46292D8B56F81A2A848B7AF04217DDADA968C9B24730',
                            'inLedger': 89041665, 'ledger_index': 89041665}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV', 'Balance': '9099884047076',
                                            'Flags': 1179648,
                                            'MessageKey': '0200000000000000000000000005CDB1526F6E224E02919A4C018D9784EA25EB3D',
                                            'OwnerCount': 1, 'Sequence': 3654}, 'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '384FB0B8D3D82F5C0EDD8181255BD89068EB56336EEA1E69380DCA4E37181317',
                            'PreviousFields': {'Balance': '9099884047075'},
                            'PreviousTxnID': '7D1F2220734F4ABE8C54C499FFC5F0A639BA0547E13697E18EBD28EBC7BB6077',
                            'PreviousTxnLgrSeq': 89041662}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610709',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552318},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610735', 'Sequence': 89552317},
                            'PreviousTxnID': 'E62A322CECBD47D5874511C7F25D96356CEB35AAFC94B4064759539D6C7B96A0',
                            'PreviousTxnLgrSeq': 89041662}}], 'TransactionIndex': 30, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV',
                                                         'DestinationTag': 212979054, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041677, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552317,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100CDEE72A725F07001FF8F3595EC66E82ED897E94E9EEF22B7D546463A116CD32F02201482F919790BF6E9688F0C58B050305D79A7D413F6F5E94A5C0EFB538740DF33',
                                                         'date': 773048370,
                                                         'hash': '00B1BC7FC5AB7EF7C054445FBFA965AEE1DD3BF03E8207D18BF3AAC45B2889BB',
                                                         'inLedger': 89041664, 'ledger_index': 89041664},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208610735', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552317},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610761',
                                               'Sequence': 89552316},
                            'PreviousTxnID': 'C4571D24B43649E69EB2647CDA6A0A1982445800C67CF0700A5F036E44558380',
                            'PreviousTxnLgrSeq': 89041661}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                    'Balance': '1952166700753',
                                    'Flags': 131072,
                                    'OwnerCount': 1,
                                    'Sequence': 115792},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                                'PreviousFields': {
                                    'Balance': '1952166700752'},
                                'PreviousTxnID': '409FF7147081DB80964E4CE88A39DFA67CE425437456E7370DC680A4F30994B6',
                                'PreviousTxnLgrSeq': 89041662}}],
                            'TransactionIndex': 27,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh', 'DestinationTag': 500356014,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041675, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552316,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100945985F66FE8DAD994152738402E71086FF5CEBA2D5885D00915830D16C78FD00220145811BB7E608CE3C22E800D4F94318D443CC54ACEE41A2F44A88F88404A37BD',
                            'date': 773048361,
                            'hash': 'E62A322CECBD47D5874511C7F25D96356CEB35AAFC94B4064759539D6C7B96A0',
                            'inLedger': 89041662, 'ledger_index': 89041662}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF', 'Balance': '32880002',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 81229452},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '1A02E86EF95D73FD02F89AEAAD725A6DADC4801E32DC1EF1FB50B58A6E79F6D5',
                            'PreviousFields': {'Balance': '32880001'},
                            'PreviousTxnID': '76AE22492EF804A40D2C274BC3163BA84F9CB705653DD8B444A3861BA3FF57F8',
                            'PreviousTxnLgrSeq': 89041658}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610761',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552316},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610787', 'Sequence': 89552315},
                            'PreviousTxnID': '80E6687FC2FF15D0F184DF06ABBBE827161959644BE550FC21FE50A3695DC2D1',
                            'PreviousTxnLgrSeq': 89041660}}], 'TransactionIndex': 144,
                        'TransactionResult': 'tesSUCCESS', 'delivered_amount': '1'}, 'tx': {
                        'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                        'Destination': 'r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF', 'DestinationTag': 2017, 'Fee': '25',
                        'Flags': 2147483648, 'LastLedgerSequence': 89041673, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                        'Sequence': 89552315,
                        'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                        'TransactionType': 'Payment',
                        'TxnSignature': '3045022100E57AD6FD18F546430BC82E62C093B805E851F0298778756F2E01DDA6512EE8CF02203D85233B2C1E9BF7CBB7288E268E365E5A7B2150897AA7F48F68124FBA768B94',
                        'date': 773048360, 'hash': 'C4571D24B43649E69EB2647CDA6A0A1982445800C67CF0700A5F036E44558380',
                        'inLedger': 89041661, 'ledger_index': 89041661}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610787',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552315},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610813', 'Sequence': 89552314},
                            'PreviousTxnID': 'BC7DF1CA87ED91DB73541250037579E0D68E73709AF98A1E7DBBD311FF7976E6',
                            'PreviousTxnLgrSeq': 89041660}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'Balance': '183456477154',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 199461},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                            'PreviousFields': {'Balance': '183456477153'},
                            'PreviousTxnID': 'D4593BB1BD400B035F222BACF38005B042FEC053CD86526E009FCA04909867CA',
                            'PreviousTxnLgrSeq': 89041658}}], 'TransactionIndex': 7, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                                         'DestinationTag': 2336991916, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041673, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552314,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100AF00740935E5847EC55797F1195B6DB871AA97534C862194A75D5060074A7B0F022002E5B9B0E2783E59660219A843D9C1B1D2A14998E9429973A867A69652B79B78',
                                                         'date': 773048351,
                                                         'hash': '80E6687FC2FF15D0F184DF06ABBBE827161959644BE550FC21FE50A3695DC2D1',
                                                         'inLedger': 89041660, 'ledger_index': 89041660},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208610813', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552314},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610839',
                                               'Sequence': 89552313},
                            'PreviousTxnID': 'F47B504C0A1875DB2D65330EFD0BA2695B1F69BB32CC10E293C94D22718B7A45',
                            'PreviousTxnLgrSeq': 89041660}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'raTjYCE2ForijAiCsjywXQ3WTq58U42gyq',
                                    'Balance': '991771727124',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'RegularKey': 'rGPHPD7mWCnHhHbvGXcvaRrKxgATP9rxAU',
                                    'Sequence': 159},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'C38462B3D5E08894B6128DF44063BC4A8B6C98E839BAF8A99C197ACA549A8FF0',
                                'PreviousFields': {
                                    'Balance': '991771727123'},
                                'PreviousTxnID': '217576458FEF002B02A5222531F705093385A023D654F74EC802E8D57EB6312F',
                                'PreviousTxnLgrSeq': 89041658}}],
                            'TransactionIndex': 6,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'raTjYCE2ForijAiCsjywXQ3WTq58U42gyq', 'DestinationTag': 831130842,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041673, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552313,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402206396FA9C2593A282C18B8B56EF663047953728250AEEF7686B8E8DFE3296F39D02207859E66F805D9CFC27E1E5815884C2A487F9B083A837B7C7F48ED26D8FFB1AC2',
                            'date': 773048351,
                            'hash': 'BC7DF1CA87ED91DB73541250037579E0D68E73709AF98A1E7DBBD311FF7976E6',
                            'inLedger': 89041660, 'ledger_index': 89041660}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610839',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552313},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610865', 'Sequence': 89552312},
                            'PreviousTxnID': '217576458FEF002B02A5222531F705093385A023D654F74EC802E8D57EB6312F',
                            'PreviousTxnLgrSeq': 89041658}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rGdHd9Re5KPsM2SukJ9wsoXwmkt5n2vHP1', 'Balance': '2632098001',
                                            'Flags': 131072, 'OwnerCount': 0, 'Sequence': 32070},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'DC08FBB10BB9DC7ECCFDED94DA2C5EDCC73E027F6E0639E2C714531A382BB9B9',
                            'PreviousFields': {'Balance': '2632098000'},
                            'PreviousTxnID': 'ADB0E40F71F1AACB8B5DD1C5EBBECB206BD9E6C609B1D2A6B73E6D464902C5E8',
                            'PreviousTxnLgrSeq': 89041658}}], 'TransactionIndex': 5, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rGdHd9Re5KPsM2SukJ9wsoXwmkt5n2vHP1',
                                                         'DestinationTag': 165878, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041673, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552312,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100B4B1B7B67F5C7050BD2A2D58AE20E9CA56ED6F367521A94482FBCD242D3B6CB802206DADC6D0C80F00A6120B90DD67B79AD1F3C5CA00FA5B3228DCBB9B800C6C678F',
                                                         'date': 773048351,
                                                         'hash': 'F47B504C0A1875DB2D65330EFD0BA2695B1F69BB32CC10E293C94D22718B7A45',
                                                         'inLedger': 89041660, 'ledger_index': 89041660},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208610865', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552312},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610891',
                                               'Sequence': 89552311},
                            'PreviousTxnID': 'D4593BB1BD400B035F222BACF38005B042FEC053CD86526E009FCA04909867CA',
                            'PreviousTxnLgrSeq': 89041658}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'raTjYCE2ForijAiCsjywXQ3WTq58U42gyq',
                                    'Balance': '991771727123',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'RegularKey': 'rGPHPD7mWCnHhHbvGXcvaRrKxgATP9rxAU',
                                    'Sequence': 159},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'C38462B3D5E08894B6128DF44063BC4A8B6C98E839BAF8A99C197ACA549A8FF0',
                                'PreviousFields': {
                                    'Balance': '991771727122'},
                                'PreviousTxnID': 'D8CA062D0E4E8512A2CB0087BE9728FFFF94F72EE0F6D92CB1FE0CABCA506C29',
                                'PreviousTxnLgrSeq': 89041655}}],
                            'TransactionIndex': 14,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'raTjYCE2ForijAiCsjywXQ3WTq58U42gyq', 'DestinationTag': 831130842,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041670, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552311,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402202E5BB00D54E1735AD75189026F4DE875986817FA738FED8F098392C05E565E38022059D6D38C89CD324D2F876B15E800DA0BB255774A69DAC24117F31935E935FE30',
                            'date': 773048342,
                            'hash': '217576458FEF002B02A5222531F705093385A023D654F74EC802E8D57EB6312F',
                            'inLedger': 89041658, 'ledger_index': 89041658}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610891',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552311},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610917', 'Sequence': 89552310},
                            'PreviousTxnID': '76AE22492EF804A40D2C274BC3163BA84F9CB705653DD8B444A3861BA3FF57F8',
                            'PreviousTxnLgrSeq': 89041658}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA', 'Balance': '183456477153',
                                            'Flags': 131072, 'OwnerCount': 1, 'Sequence': 199461},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'E5C6084FF22D11C5236D69FA9EA6F46ED694A663FCEDCE10D84B00BF09F74F1B',
                            'PreviousFields': {'Balance': '183456477152'},
                            'PreviousTxnID': '79ED2E70FB1CCFDAB792CD4943C33245004D099CB47D99676EB1F7BA60A955BB',
                            'PreviousTxnLgrSeq': 89041655}}], 'TransactionIndex': 13, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
                                                         'DestinationTag': 2336991916, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041670, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552310,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100CA56D785D53E797B068349FEA10AE12640E976951CF7DF6070AFBEF081ECE4270220791FDCF34A2A7C5CE438DC7A8E4E78D832832D4B6EA6FF76F61DFDBF9420E992',
                                                         'date': 773048342,
                                                         'hash': 'D4593BB1BD400B035F222BACF38005B042FEC053CD86526E009FCA04909867CA',
                                                         'inLedger': 89041658, 'ledger_index': 89041658},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF',
                                'Balance': '32880001', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 81229452},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '1A02E86EF95D73FD02F89AEAAD725A6DADC4801E32DC1EF1FB50B58A6E79F6D5',
                            'PreviousFields': {'Balance': '32880000'},
                            'PreviousTxnID': '15DAA498A00A98E823FAB1EE935820CFE8AAD049033B97EF8200C220564C3039',
                            'PreviousTxnLgrSeq': 89041655}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208610917',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552310},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208610943',
                                    'Sequence': 89552309},
                                'PreviousTxnID': '3727438EB9D00038D4089E41BAF9B0F471A87560FBDC7C1C8BE347951657D3D5',
                                'PreviousTxnLgrSeq': 89041657}}],
                            'TransactionIndex': 12,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041670, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552309,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304502210097539DD96EEFC6EA412C0D3C59E89F258942EB67B4671C7E728D702E530A575602206D0F6E91DDB603E2B31B8A782DA364EF6208EC3468CB83A7008BA0F444DAD818',
                            'date': 773048342,
                            'hash': '76AE22492EF804A40D2C274BC3163BA84F9CB705653DD8B444A3861BA3FF57F8',
                            'inLedger': 89041658, 'ledger_index': 89041658}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rN9TVUqkaDfhF1Ho4VdvkDpMNE7SoNp71', 'Balance': '157611502',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 85778541},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '1352D5E0D4D7F27F81247A44BE02D46437366E6F79222D9116766BA3986ACC6C',
                            'PreviousFields': {'Balance': '157611501'},
                            'PreviousTxnID': '0B043C5A8E491B3246B5D343635D7CF1E37D73DB5FA03407C6CCF14E97142D8E',
                            'PreviousTxnLgrSeq': 89041655}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610943',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552309},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610969', 'Sequence': 89552308},
                            'PreviousTxnID': 'B0269C60BF756CA6E6608F690F4B944217E517EF551F1CA07E8D0FF3DEA0BF5B',
                            'PreviousTxnLgrSeq': 89041656}}], 'TransactionIndex': 10, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rN9TVUqkaDfhF1Ho4VdvkDpMNE7SoNp71',
                                                         'DestinationTag': 2017, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041670, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552308,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '304402202B3791E611F90E37B92F04F3D3328E840A3EDA01A9EA8A4E625A5BCA2DA66DD202207DAD4BBC5971563007FE13D90111005E69A1A59E8EBC8F4458F43F013854927F',
                                                         'date': 773048341,
                                                         'hash': '3727438EB9D00038D4089E41BAF9B0F471A87560FBDC7C1C8BE347951657D3D5',
                                                         'inLedger': 89041657, 'ledger_index': 89041657},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208610969', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552308},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208610995',
                                               'Sequence': 89552307},
                            'PreviousTxnID': '246F5D043B0EDB18C5375403ADDA18F79B3F2AF7B74142561237EE2EC5982510',
                            'PreviousTxnLgrSeq': 89041656}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
                                    'Balance': '1949383802997',
                                    'Flags': 131072,
                                    'OwnerCount': 1,
                                    'Sequence': 115792},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'C19B36F6B6F2EEC9F4E2AF875E533596503F4541DBA570F06B26904FDBBE9C52',
                                'PreviousFields': {
                                    'Balance': '1949383802996'},
                                'PreviousTxnID': 'D9B4B7291C9AF8A1BF60C799AC241D4CDF4E20D853693762BF49E7ABBF5AC675',
                                'PreviousTxnLgrSeq': 89041656}}],
                            'TransactionIndex': 21,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rJn2zAPdFA193sixJwuFixRkYDUtx3apQh', 'DestinationTag': 500619401,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041669, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552307,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402201E01DE4FFACC6A6BCF99D3A82D33ADEA9CF399C7211A6C046AF9993E995B6DF10220399291B4BBE3BC87490B543F247BCD598DBEE8702EED56CBE527E1E3D84F286C',
                            'date': 773048340,
                            'hash': 'B0269C60BF756CA6E6608F690F4B944217E517EF551F1CA07E8D0FF3DEA0BF5B',
                            'inLedger': 89041656, 'ledger_index': 89041656}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'Balance': '7543265786',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 77285543},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                            'PreviousFields': {'Balance': '7543265785'},
                            'PreviousTxnID': '519336FB6F21CECE3453E5DDFDCAFB47B395E5C2347906C268250431040837D1',
                            'PreviousTxnLgrSeq': 89041656}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208610995',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552307},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611021', 'Sequence': 89552306},
                            'PreviousTxnID': '1A7245E470D0A79B2BCDF2CCFA8533AC4B6AED0119CCED3297B954613F9CF096',
                            'PreviousTxnLgrSeq': 89041654}}], 'TransactionIndex': 20, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                                                         'DestinationTag': 325415231, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041669, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552306,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100F6083CC0F0D4858430E484865B7461DEB4CF261BE22F02A57042B41961FF8B6B022038DBBFD4D2FD7556396426D807806776110B16C7A95F86EADAA5662E0669691B',
                                                         'date': 773048340,
                                                         'hash': '246F5D043B0EDB18C5375403ADDA18F79B3F2AF7B74142561237EE2EC5982510',
                                                         'inLedger': 89041656, 'ledger_index': 89041656},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                                'Balance': '7543265679', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 77285543},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                            'PreviousFields': {'Balance': '7543265678'},
                            'PreviousTxnID': '2B21FA4A4309D473C009DAC51AF0AD64E61CAE18BAD0C657006451CFA470B780',
                            'PreviousTxnLgrSeq': 89041652}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208611021',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552306},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208611047',
                                    'Sequence': 89552305},
                                'PreviousTxnID': '9BF480E2C01ED318753A940BA96B7E3B7D9F4DF9342B81EDAD920CA8F62962B2',
                                'PreviousTxnLgrSeq': 89041652}}],
                            'TransactionIndex': 21,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'DestinationTag': 325415231,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041667, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552305,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3045022100F652428E61C87D386A8489B67CE25AB5C3E1F711B955F64D0373EEA10A032D2202201773996B7255865440325FF263EB79472DDAAD74F3E5712870B19B1077BD31CC',
                            'date': 773048330,
                            'hash': '1A7245E470D0A79B2BCDF2CCFA8533AC4B6AED0119CCED3297B954613F9CF096',
                            'inLedger': 89041654, 'ledger_index': 89041654}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy', 'Balance': '301171275',
                                            'Flags': 0, 'OwnerCount': 14, 'Sequence': 83570170},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '8BCC878E77AF52A960746662BAD2237D7AAFC14D5F5D3260747C6810CEC4B681',
                            'PreviousFields': {'Balance': '301171274'},
                            'PreviousTxnID': 'ED40EFA329506973886FD7F70F937426EF189CA39A827DF26E1EABD1996B0235',
                            'PreviousTxnLgrSeq': 89041650}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611047',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552305},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611073', 'Sequence': 89552304},
                            'PreviousTxnID': '69CCEC0025710CEB5C1BA9D5C96071AEDF192AB280EE60A46C095683FE17604F',
                            'PreviousTxnLgrSeq': 89041652}}], 'TransactionIndex': 17, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
                                                         'DestinationTag': 2017, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041665, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552304,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100EBEC0FEDD9442E46E6FCA451405CBF94B46588177E2EFC0EAE153B1CB0843974022056E7820AA78568C1F302BE7B81B27932C3B41A0F31CA3A37DD0BDB77CC577439',
                                                         'date': 773048321,
                                                         'hash': '9BF480E2C01ED318753A940BA96B7E3B7D9F4DF9342B81EDAD920CA8F62962B2',
                                                         'inLedger': 89041652, 'ledger_index': 89041652},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
                                'Balance': '10539463348', 'Flags': 131072,
                                'OwnerCount': 0, 'Sequence': 59255670},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '6F94B5486DBA5021658BF814570177F012A1680FD1973735094F71957DCFFF9F',
                            'PreviousFields': {'Balance': '10539463347'},
                            'PreviousTxnID': '5734608420F04536343DAFA485FA2B2A1CF768FF28E0CBE55E3F16891F30C71D',
                            'PreviousTxnLgrSeq': 89041650}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208611073',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552304},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208611099',
                                    'Sequence': 89552303},
                                'PreviousTxnID': '7D728E9CA22851143F3CFFB678C9CA9EC3F448B1460134F7BDAB8F48364785E9',
                                'PreviousTxnLgrSeq': 89041652}}],
                            'TransactionIndex': 16,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB', 'DestinationTag': 2082184339,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041665, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552303,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304502210093C6A6D57531F6E8722FBDE30E92015DF634B4554013BA430AB2067BF3F27FFE022068337517921FEF8636A5536FF326206A44E7A4959C686733A96CD9741F2E799A',
                            'date': 773048321,
                            'hash': '69CCEC0025710CEB5C1BA9D5C96071AEDF192AB280EE60A46C095683FE17604F',
                            'inLedger': 89041652, 'ledger_index': 89041652}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611099',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552303},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611125', 'Sequence': 89552302},
                            'PreviousTxnID': '4A0763DC78FC299AD9AB297234D02E2690DC4D457445368FAAE441A8AC3BFB8C',
                            'PreviousTxnLgrSeq': 89041652}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rKcyeSaT9zhmZxJgUaQq1aFmyvMXd6x7FU', 'Balance': '404085261598',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 70271305},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'D1C0B1E69DA4156D44CCBCDE06CD736A205FFBDA779CCEC251772AB698D45D9F',
                            'PreviousFields': {'Balance': '404085261597'},
                            'PreviousTxnID': '18023AEB87379326BFEBB62CF054A4250B4EDDE5493DB74A41E1FCDBB30D4EF0',
                            'PreviousTxnLgrSeq': 89041650}}], 'TransactionIndex': 15, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rKcyeSaT9zhmZxJgUaQq1aFmyvMXd6x7FU',
                                                         'DestinationTag': 1140014125, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041665, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552302,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100B22C2638ABA2070C218BC76AC3E5F854646B04390C55A0C03AB1F0440181F4E902203BDC655CE4F70AC4CF03DB89599CBEAD93C6832C42085BF7037C5CD13E3AFD30',
                                                         'date': 773048321,
                                                         'hash': '7D728E9CA22851143F3CFFB678C9CA9EC3F448B1460134F7BDAB8F48364785E9',
                                                         'inLedger': 89041652, 'ledger_index': 89041652},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
                                'Balance': '7543265625', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 77285543},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '59EDFBD7E3AA8EF84600C7AABD24DBC8229C19A1FF956C83D6B04390CF7C7E34',
                            'PreviousFields': {'Balance': '7543265624'},
                            'PreviousTxnID': '90FE5C7469DC95BB4DC3B74BCF64EB428EE3AFE28CC4D63236CA09F12B2F13A1',
                            'PreviousTxnLgrSeq': 89041650}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208611125',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552302},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208611151',
                                    'Sequence': 89552301},
                                'PreviousTxnID': '5734608420F04536343DAFA485FA2B2A1CF768FF28E0CBE55E3F16891F30C71D',
                                'PreviousTxnLgrSeq': 89041650}}],
                            'TransactionIndex': 14,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', 'DestinationTag': 399238402,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041665, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552301,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402205040DE7346D7CF2402725E997D7864E035EC06356480A1B82F431F2235910E8102202A8EA6C13EA996D9737858DEAC75A8863A13B8E19B2746E8BE1919034FDCA1E6',
                            'date': 773048321,
                            'hash': '4A0763DC78FC299AD9AB297234D02E2690DC4D457445368FAAE441A8AC3BFB8C',
                            'inLedger': 89041652, 'ledger_index': 89041652}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB', 'Balance': '10539463347',
                                            'Flags': 131072, 'OwnerCount': 0, 'Sequence': 59255670},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '6F94B5486DBA5021658BF814570177F012A1680FD1973735094F71957DCFFF9F',
                            'PreviousFields': {'Balance': '10539463346'},
                            'PreviousTxnID': 'E8E10B2D16166D1DB51CA6FD251FD8B5C2B2F33073391CEDC8F56658ADF956F6',
                            'PreviousTxnLgrSeq': 89041648}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611151',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552301},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611177', 'Sequence': 89552300},
                            'PreviousTxnID': 'ED40EFA329506973886FD7F70F937426EF189CA39A827DF26E1EABD1996B0235',
                            'PreviousTxnLgrSeq': 89041650}}], 'TransactionIndex': 28, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
                                                         'DestinationTag': 2082184339, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041663, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552300,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '304402202E83EAC5D9B93D936215033A9E9125C1FDB68DF5A18ED5FC50E58E358131A8B502203FAEAB656F3BFED6B5DE396FFE71B1AE828DF37C94EEF4E9EED9A6BB4D07E8A0',
                                                         'date': 773048312,
                                                         'hash': '5734608420F04536343DAFA485FA2B2A1CF768FF28E0CBE55E3F16891F30C71D',
                                                         'inLedger': 89041650, 'ledger_index': 89041650},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
                                'Balance': '301171274', 'Flags': 0,
                                'OwnerCount': 14, 'Sequence': 83570170},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '8BCC878E77AF52A960746662BAD2237D7AAFC14D5F5D3260747C6810CEC4B681',
                            'PreviousFields': {'Balance': '301171273'},
                            'PreviousTxnID': '637D60DFFF8463A26E12F80E7E664FF9A8F8D2EB3C254797915969E460EFA0E0',
                            'PreviousTxnLgrSeq': 89041648}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208611177',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552300},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208611203',
                                    'Sequence': 89552299},
                                'PreviousTxnID': '488DACB2AC3D954EDE805CB93BA7DC89540A4F45BE371900C4AFEE40EB63D9EB',
                                'PreviousTxnLgrSeq': 89041650}}],
                            'TransactionIndex': 27,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041663, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552299,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402205E73D6D6190844BE0C09F85F1B30B6C6D193BBB8CEF8AEB773BEE5F74AB180110220054E9C392405F113160379900B308B51CB046B0B55F4811ADF3D050FD88438A7',
                            'date': 773048312,
                            'hash': 'ED40EFA329506973886FD7F70F937426EF189CA39A827DF26E1EABD1996B0235',
                            'inLedger': 89041650, 'ledger_index': 89041650}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rHcFoo6a9qT5NHiVn1THQRhsEGcxtYCV4d',
                                            'Balance': '49460272495641', 'Flags': 131072, 'OwnerCount': 3,
                                            'Sequence': 490251}, 'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '2D010D063E32BC145A0331B98CDC23CAC0A1932AD6BB17A08026CE70621388F2',
                            'PreviousFields': {'Balance': '49460272495640'},
                            'PreviousTxnID': '08BE2D9F7C859458322B402AA6E476EC8D038B1D2D6BFBED1342601CE0B49732',
                            'PreviousTxnLgrSeq': 89041648}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611203',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552299},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611229', 'Sequence': 89552298},
                            'PreviousTxnID': '637D60DFFF8463A26E12F80E7E664FF9A8F8D2EB3C254797915969E460EFA0E0',
                            'PreviousTxnLgrSeq': 89041648}}], 'TransactionIndex': 26, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rHcFoo6a9qT5NHiVn1THQRhsEGcxtYCV4d',
                                                         'DestinationTag': 2357348680, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041663, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552298,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '304402206BCE04FD444FF571774C32BF73B1B83091EADB0DA6135C8EB924D7EFEE59972302202AF7BF0F28A20A64924DE74623A14A9CDD7F4A9DE2663ADF8F3B45796F7D176C',
                                                         'date': 773048312,
                                                         'hash': '488DACB2AC3D954EDE805CB93BA7DC89540A4F45BE371900C4AFEE40EB63D9EB',
                                                         'inLedger': 89041650, 'ledger_index': 89041650},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
                                'Balance': '301171273', 'Flags': 0,
                                'OwnerCount': 14, 'Sequence': 83570170},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '8BCC878E77AF52A960746662BAD2237D7AAFC14D5F5D3260747C6810CEC4B681',
                            'PreviousFields': {'Balance': '301171272'},
                            'PreviousTxnID': 'F300802EA13BDDCC347D3B5223AD6248C56A4C569DB09AE2FCB46328EF000988',
                            'PreviousTxnLgrSeq': 89041644}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                    'Balance': '4208611229',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 89552298},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                                'PreviousFields': {
                                    'Balance': '4208611255',
                                    'Sequence': 89552297},
                                'PreviousTxnID': 'E8E10B2D16166D1DB51CA6FD251FD8B5C2B2F33073391CEDC8F56658ADF956F6',
                                'PreviousTxnLgrSeq': 89041648}}],
                            'TransactionIndex': 21,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041661, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552297,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402207827EFE0E00568FD880519A3B25773DC30C2603AE87507D24E2011730529600B022024F470F27613B39A4EDBE46FD14D836765666FBE337592F9BB08077F9067CB78',
                            'date': 773048310,
                            'hash': '637D60DFFF8463A26E12F80E7E664FF9A8F8D2EB3C254797915969E460EFA0E0',
                            'inLedger': 89041648, 'ledger_index': 89041648}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB', 'Balance': '10539463346',
                                            'Flags': 131072, 'OwnerCount': 0, 'Sequence': 59255670},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '6F94B5486DBA5021658BF814570177F012A1680FD1973735094F71957DCFFF9F',
                            'PreviousFields': {'Balance': '10539463345'},
                            'PreviousTxnID': '5DCD5B2C744FABEDA6EEDD8A1689CED2CCA08E584FEA0E19CD3DF7A17CE434BC',
                            'PreviousTxnLgrSeq': 89041646}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611255',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552297},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611281', 'Sequence': 89552296},
                            'PreviousTxnID': '8FCB35A11D0E07A1924A4D48D5FFA1C221A4A4FA289016211F13BC072CC048F2',
                            'PreviousTxnLgrSeq': 89041647}}], 'TransactionIndex': 20, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
                                                         'DestinationTag': 2082184339, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041661, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552296,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100DB2A9DE4004FB50095DB7BFF04449015CE906B3A944437CB168E59B8D1A49CEA02200D4C587B7FC87C5DCC3167E5FDB2F9B481F52C9F1D7177852A18D1FA6FEC5DCC',
                                                         'date': 773048310,
                                                         'hash': 'E8E10B2D16166D1DB51CA6FD251FD8B5C2B2F33073391CEDC8F56658ADF956F6',
                                                         'inLedger': 89041648, 'ledger_index': 89041648},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208611281', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552296},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611307',
                                               'Sequence': 89552295},
                            'PreviousTxnID': '5DCD5B2C744FABEDA6EEDD8A1689CED2CCA08E584FEA0E19CD3DF7A17CE434BC',
                            'PreviousTxnLgrSeq': 89041646}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rHmku65GJrrsp6Sb7KRzCgM2tAA3JBACQZ',
                                    'Balance': '2766326485',
                                    'Domain': '6E6F6E6B79632E696F',
                                    'Flags': 0,
                                    'OwnerCount': 0,
                                    'Sequence': 79025090},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'F0B57F86E1F2F0B5BEE5B23A74DDC91441344F06000195D624496635A041716D',
                                'PreviousFields': {
                                    'Balance': '2766326484'},
                                'PreviousTxnID': 'A879B2DC5C46539CF315E2F35DE43A2C0D2C9A04C99505CBC415E2EA1526ED50',
                                'PreviousTxnLgrSeq': 89041520}}],
                            'TransactionIndex': 18,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rHmku65GJrrsp6Sb7KRzCgM2tAA3JBACQZ', 'DestinationTag': 2017, 'Fee': '25',
                            'Flags': 2147483648, 'LastLedgerSequence': 89041661, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552295,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '3044022030BAE1C391FC87495A74242FB6DB555202EF9EE673E6B4D9880385B71355D022022042249261E8A4D334BBFE07399C51A70A2C03198C7B0FAA94E9C0641D80B01E76',
                            'date': 773048301,
                            'hash': '8FCB35A11D0E07A1924A4D48D5FFA1C221A4A4FA289016211F13BC072CC048F2',
                            'inLedger': 89041647, 'ledger_index': 89041647}, 'validated': True}, {'meta': {
                        'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {'Account': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB', 'Balance': '10539463345',
                                            'Flags': 131072, 'OwnerCount': 0, 'Sequence': 59255670},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': '6F94B5486DBA5021658BF814570177F012A1680FD1973735094F71957DCFFF9F',
                            'PreviousFields': {'Balance': '10539463344'},
                            'PreviousTxnID': '45748392C887A82CEA2A58A627128F857E71E9D60C3436A6DE8C1802F3C9E98A',
                            'PreviousTxnLgrSeq': 89041644}}, {'ModifiedNode': {
                            'FinalFields': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Balance': '4208611307',
                                            'Flags': 0, 'OwnerCount': 0, 'Sequence': 89552295},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611333', 'Sequence': 89552294},
                            'PreviousTxnID': '03A533E1219E81D57027CF3501045A1A334E19DDBD5F642F0F2959D83B3EFCFE',
                            'PreviousTxnLgrSeq': 89041645}}], 'TransactionIndex': 12, 'TransactionResult': 'tesSUCCESS',
                        'delivered_amount': '1'}, 'tx': {'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1',
                                                         'DeliverMax': '1',
                                                         'Destination': 'rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
                                                         'DestinationTag': 2082184339, 'Fee': '25', 'Flags': 2147483648,
                                                         'LastLedgerSequence': 89041659, 'Memos': [{'Memo': {
                            'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                            {'Memo': {
                                'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                            {'Memo': {
                                'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                            {'Memo': {
                                'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                            {'Memo': {
                                'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                            {'Memo': {
                                'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                            {'Memo': {
                                'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                            {'Memo': {
                                'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                            {'Memo': {
                                'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                            {'Memo': {
                                'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                            {'Memo': {
                                'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                            {'Memo': {
                                'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                            {'Memo': {
                                'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                            {'Memo': {
                                'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                            {'Memo': {
                                'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                                                         'Sequence': 89552294,
                                                         'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                                                         'TransactionType': 'Payment',
                                                         'TxnSignature': '3045022100C823DC8CC79B2DB3F6CA0C46C835A8BFB86AC95A43247FE8F754F99F214379040220244CC23D6D613B7BEDBCFD40A388C4663F67D6BF73571AF6E602D2100E5BF6EF',
                                                         'date': 773048300,
                                                         'hash': '5DCD5B2C744FABEDA6EEDD8A1689CED2CCA08E584FEA0E19CD3DF7A17CE434BC',
                                                         'inLedger': 89041646, 'ledger_index': 89041646},
                        'validated': True}, {
                        'meta': {'AffectedNodes': [{'ModifiedNode': {
                            'FinalFields': {
                                'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                                'Balance': '4208611333', 'Flags': 0,
                                'OwnerCount': 0, 'Sequence': 89552294},
                            'LedgerEntryType': 'AccountRoot',
                            'LedgerIndex': 'B1E70E44C3D201A11890678AC660EAD84642373F8D9B261ADEFA324306792F2B',
                            'PreviousFields': {'Balance': '4208611359',
                                               'Sequence': 89552293},
                            'PreviousTxnID': 'D7D01D9A4E338BAF4C451670A441CCAACC32088F8E40C5E8DCA44E46C1ABEB63',
                            'PreviousTxnLgrSeq': 89041642}}, {
                            'ModifiedNode': {
                                'FinalFields': {
                                    'Account': 'rnHqddewfDgsZykzKJYgk9jFysebWbrL49',
                                    'Balance': '34220261446',
                                    'Flags': 131072,
                                    'OwnerCount': 0,
                                    'Sequence': 18470},
                                'LedgerEntryType': 'AccountRoot',
                                'LedgerIndex': 'C995C45CFCAE71F296C263A987D0D2ED426AFF8431E143C28B2FDED81869502A',
                                'PreviousFields': {
                                    'Balance': '34220261445'},
                                'PreviousTxnID': '9D2895C9AB755AD1EC379BB85D95CD7F3E3BE22A371865E5A89D3506BD4B85B5',
                                'PreviousTxnLgrSeq': 89041644}}],
                            'TransactionIndex': 14,
                            'TransactionResult': 'tesSUCCESS',
                            'delivered_amount': '1'}, 'tx': {
                            'Account': 'rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', 'Amount': '1', 'DeliverMax': '1',
                            'Destination': 'rnHqddewfDgsZykzKJYgk9jFysebWbrL49', 'DestinationTag': 1836815735,
                            'Fee': '25', 'Flags': 2147483648, 'LastLedgerSequence': 89041659, 'Memos': [{'Memo': {
                                'MemoData': '5768656E20796F75207365652074686973206D6573736167652C207765206861766520616C7265616479206265656E206172726573746564206F72207475726E6564206F757273656C76657320696E2E'}},
                                {'Memo': {
                                    'MemoData': '546F20616C6C20476174654875622075736572732C'}},
                                {'Memo': {
                                    'MemoData': '476174654875622069732061207368616D656C6573732063686561742E'}},
                                {'Memo': {
                                    'MemoData': '496E20323031372C2047617465487562206C6F7374207E354D2055534420637573746F6D6572206173736574732062656361757365207468657920646964206E6F7420756E6465727374616E64205061727469616C205061796D656E742066656174757265'}},
                                {'Memo': {
                                    'MemoData': '496E20323032322C2077652073656E74207E31334D205553442061737365747320746F204761746548756220776974682074686569722070726F6D697365733A'}},
                                {'Memo': {
                                    'MemoData': '312E206E6F206C6F6E6765722074616B65206C6567616C20616374696F6E20616761696E7374207573'}},
                                {'Memo': {
                                    'MemoData': '322E206E6F206675727468657220636C61696D7320666F7220636F6D70656E736174696F6E'}},
                                {'Memo': {
                                    'MemoData': '332E206B65657020354D2055534420616E64206169722064726F7020746865206C6566742061737365747320746F20616C6C2047617465487562207573657273'}},
                                {'Memo': {
                                    'MemoData': '342E20646F206E6F74207368617265206F757220696E666F726D6174696F6E20776974682074686972642070617274696573'}},
                                {'Memo': {
                                    'MemoData': '352E206D616B6520616E20616E6E6F756E63656D656E7420726567617264696E67207468652061626F76652061677265656D656E7473'}},
                                {'Memo': {
                                    'MemoData': '77652073656E742074686520636F696E732C20627574204761746548756220646964206E6F74206B6565702074686569722070726F6D69736573'}},
                                {'Memo': {
                                    'MemoData': '6E6F20616E6E6F756E63656D656E742C206E6F206169722064726F702C20636F6E74696E756520746F20746872656174656E2075732077697468206C6567616C20616374696F6E'}},
                                {'Memo': {
                                    'MemoData': '476174654875622061736B20666F72206D6F726520616E64206D6F726520636F696E732E20416E20696E7361746961626C6520626C61636B6D61696C657221'}},
                                {'Memo': {
                                    'MemoData': '57652068617665206E6F206D6F726520636F696E732C2074686520747275746820697320746865206F6E6C79207468696E672077652063616E207368617265'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}},
                                {'Memo': {
                                    'MemoData': '54686520747275746820697320746865206F6E6C79207468696E672077652063616E2073686172652E'}}],
                            'Sequence': 89552293,
                            'SigningPubKey': '03924D5111DD356B7B68E7E68A16848968B8492D812728627A3582572B14C798BF',
                            'TransactionType': 'Payment',
                            'TxnSignature': '304402204ED0C247B6533DE90A226FE9346AC122E5F6B700CAB3900E1B126B1E5006B45A022061BC6EFE6E55206697C2DCD6D1FD9DF3F9D38D0492DBA1ABFECAF3F2F0C84B4E',
                            'date': 773048292,
                            'hash': '03A533E1219E81D57027CF3501045A1A334E19DDBD5F642F0F2959D83B3EFCFE',
                            'inLedger': 89041645, 'ledger_index': 89041645}, 'validated': True}], 'validated': True}}

        ]
        self.api.request = Mock(side_effect=address_txs_mock_response)
        addresses_txs = []
        for address in self.address_txs:
            api_response = self.api.get_address_txs(address)
            parsed_response = self.api.parser.parse_address_txs_response(address, api_response, None)
            addresses_txs.append(parsed_response)
        expected_addresses_txs = [
            [TransferTx(tx_hash='6ADFADCF19F2B25EB5332395FA68C986C52C74C3D7B3DE200282341F833EFFC2', success=True,
                        from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY',
                        to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV', value=Decimal('0.000001'), symbol='XRP',
                        confirmations=1, block_height=89041682, block_hash=None,
                        date=datetime.datetime(2024, 6, 30, 7, 40, 40, tzinfo= UTC),
             memo = '399202771', tx_fee = Decimal('0.000025'), token = None, index = None), TransferTx(
            tx_hash='8D2B3A18963A6571B90FF27446777BC5A26B6D9655F64ADF534320738B137AEE', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=1, block_height=89041682, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 40, tzinfo= UTC), memo = '500301078', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='430CF23DE4FCAE3457CC07A57BC260FE6BA06CA69902120A809F7959594D5783', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=2, block_height=89041681, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 31, tzinfo= UTC), memo = '209141062', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='A938E9CAC2F5352B2C4D9D25D1E0DF49FCBBB992DFD96C353DB17B50C30AD392', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=3, block_height=89041680, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 30, tzinfo= UTC), memo = '399202771', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='D1504B3F7CE3649F522249423CF62F8BCA463F05A4439BFC0242D2F57E498412', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJMB7w47XsRVou7sE79DKzNvAquZwARbQG',
            value=Decimal('0.000001'), symbol='XRP', confirmations=3, block_height=89041680, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 30, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='F689870A66E918C927639CA9E7FB50EB158B92FBE38A4D2E499393E4B93B0F42', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=4, block_height=89041679, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 22, tzinfo= UTC), memo = '3426593446', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='6F18B0E6EDD1E9D25127FD00EC52CF7CE28DDE65E21D3DD537D60308D9192EAF', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE',
            value=Decimal('0.000001'), symbol='XRP', confirmations=4, block_height=89041679, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 22, tzinfo= UTC), memo = '176203189', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='47E445A17D30967EB773E80F7F6D1F8796116FD1D16CE69638DEEB8A7B6AF094', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rwHkJBjh7UJodTczQsF1BV5pLv7SgGv4j5',
            value=Decimal('0.000001'), symbol='XRP', confirmations=5, block_height=89041678, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 21, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='757944996FF1B20205F03FE45143AA49B0AF99824FCADB31933456BD8A16B729', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rPJURMhyJdkA19zZyqwv1bruUo9Y8Pyovo',
            value=Decimal('0.000001'), symbol='XRP', confirmations=6, block_height=89041677, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 20, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='580ED9F542CA5835E5E6510BA1DB462A96E5299D3F80660FE0C8517168F45B17', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=7, block_height=89041676, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 12, tzinfo= UTC), memo = '395224681', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='1B416E66DEF1287CBB9A78F1DD6B3D7A60699684054A42863F88A7E147F43E88', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='r35mbUmndYnnqUWWWki4K1H6NdUWAgvQR7',
            value=Decimal('0.000001'), symbol='XRP', confirmations=8, block_height=89041675, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 11, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='7E126245BA064F881AFF99F9B57834E66716599A7AABF32B8153F46E236FCA85', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=9, block_height=89041674, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 10, tzinfo= UTC), memo = '399237106', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='152F94CE06E5AADE161A8BA86462A56498E797953D4BC4C5215415BE9A3418FE', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rD37r1cciGqmdBpqou2DneEiWA1iQsAphP',
            value=Decimal('0.000001'), symbol='XRP', confirmations=9, block_height=89041674, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 10, tzinfo= UTC), memo = '2437', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='0DB90AE69F19B9D3292D1D26486A2D548C152B37C7D0BCC71D82D623FF7FAE64', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rKKbNYZRqwPgZYkFWvqNUFBuscEyiFyCE',
            value=Decimal('0.000001'), symbol='XRP', confirmations=10, block_height=89041673, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, 1, tzinfo= UTC), memo = '350081973', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='B7C4B5B87C51F39847B6F6DDA67B086D3920841D2301D7299E867D29DF5D10CD', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rs2dgzYeqYqsk8bvkQR5YPyqsXYcA24MP2',
            value=Decimal('0.000001'), symbol='XRP', confirmations=11, block_height=89041672, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 40, tzinfo= UTC), memo = '476405', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='25C6BD0AD20674706C9426DD38A52792D52D2E779A65CDE5D20FE1F636E07509', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=12, block_height=89041671, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 52, tzinfo= UTC), memo = '7468142', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='24DB11A39E741B1618D78C036BE98060875A7D67D1483FB8FE40B4EFD2DE385A', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
            value=Decimal('0.000001'), symbol='XRP', confirmations=12, block_height=89041671, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 52, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='9077C56BFA0CD5CA0E84FDBAD4D88B694792DC9A1FAACEF67E448EB140EA2C7A', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=13, block_height=89041670, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 51, tzinfo= UTC), memo = '2476714657', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='C2BC31683039EA1B5EBFCD1009E2E72BEA54455D025B59A1E2A4BF68905A4568', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
            value=Decimal('0.000001'), symbol='XRP', confirmations=14, block_height=89041669, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 50, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='D9E223380CAA7C4EDC3D22186C828D20048573E56317B6E3BD79C6243240B059', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=14, block_height=89041669, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 50, tzinfo= UTC), memo = '7468142', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='6AB62EB5D93E8C1B5FB9AB8D5D0E2A4B5A2D5F80F6CC682B5BF0D83F9FFC5418', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rK8v2KxgLQSgarqSuQ7qwXrN799xp7o2T8',
            value=Decimal('0.000001'), symbol='XRP', confirmations=15, block_height=89041668, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 41, tzinfo= UTC), memo = '3803555883', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='38B881EB67F7F3085B7336AC5C8914DC7C116B15C3E590D898B2BB37638D864E', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=16, block_height=89041667, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 40, tzinfo= UTC), memo = '7468142', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='780D6FABFF72E89905AB9C09B3B82F88874216599FC962C1ED1E1AD1E1CBCA16', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rnFApzSsKwXyTZtci4Z6nLVL8E1nLZzSBF',
            value=Decimal('0.000001'), symbol='XRP', confirmations=16, block_height=89041667, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 40, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='D2F916037122A758AD72BDDB693FF4A014DF2EC29E242B3FF7B5A5D03D38C1AA', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=16, block_height=89041667, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 40, tzinfo= UTC), memo = '2476714657', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='3BBC1F2463A112E3726B46292D8B56F81A2A848B7AF04217DDADA968C9B24730', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=18, block_height=89041665, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 31, tzinfo= UTC), memo = '2476714657', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='00B1BC7FC5AB7EF7C054445FBFA965AEE1DD3BF03E8207D18BF3AAC45B2889BB', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rfrnxmLBiXHj38a2ZUDNzbks3y6yd3wJnV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=19, block_height=89041664, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 30, tzinfo= UTC), memo = '212979054', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='E62A322CECBD47D5874511C7F25D96356CEB35AAFC94B4064759539D6C7B96A0', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=21, block_height=89041662, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 21, tzinfo= UTC), memo = '500356014', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='C4571D24B43649E69EB2647CDA6A0A1982445800C67CF0700A5F036E44558380', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF',
            value=Decimal('0.000001'), symbol='XRP', confirmations=22, block_height=89041661, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 20, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='80E6687FC2FF15D0F184DF06ABBBE827161959644BE550FC21FE50A3695DC2D1', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=23, block_height=89041660, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 11, tzinfo= UTC), memo = '2336991916', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='BC7DF1CA87ED91DB73541250037579E0D68E73709AF98A1E7DBBD311FF7976E6', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raTjYCE2ForijAiCsjywXQ3WTq58U42gyq',
            value=Decimal('0.000001'), symbol='XRP', confirmations=23, block_height=89041660, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 11, tzinfo= UTC), memo = '831130842', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='F47B504C0A1875DB2D65330EFD0BA2695B1F69BB32CC10E293C94D22718B7A45', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rGdHd9Re5KPsM2SukJ9wsoXwmkt5n2vHP1',
            value=Decimal('0.000001'), symbol='XRP', confirmations=23, block_height=89041660, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 11, tzinfo= UTC), memo = '165878', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='217576458FEF002B02A5222531F705093385A023D654F74EC802E8D57EB6312F', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raTjYCE2ForijAiCsjywXQ3WTq58U42gyq',
            value=Decimal('0.000001'), symbol='XRP', confirmations=25, block_height=89041658, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 2, tzinfo= UTC), memo = '831130842', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='D4593BB1BD400B035F222BACF38005B042FEC053CD86526E009FCA04909867CA', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='raQwCVAJVqjrVm1Nj5SFRcX8i22BhdC9WA',
            value=Decimal('0.000001'), symbol='XRP', confirmations=25, block_height=89041658, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 2, tzinfo= UTC), memo = '2336991916', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='76AE22492EF804A40D2C274BC3163BA84F9CB705653DD8B444A3861BA3FF57F8', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='r3FCiURwFC6zR8yK4AFYCtGZtiar4JyPzF',
            value=Decimal('0.000001'), symbol='XRP', confirmations=25, block_height=89041658, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 2, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='3727438EB9D00038D4089E41BAF9B0F471A87560FBDC7C1C8BE347951657D3D5', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rN9TVUqkaDfhF1Ho4VdvkDpMNE7SoNp71',
            value=Decimal('0.000001'), symbol='XRP', confirmations=26, block_height=89041657, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, 1, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='B0269C60BF756CA6E6608F690F4B944217E517EF551F1CA07E8D0FF3DEA0BF5B', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rJn2zAPdFA193sixJwuFixRkYDUtx3apQh',
            value=Decimal('0.000001'), symbol='XRP', confirmations=27, block_height=89041656, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, tzinfo= UTC), memo = '500619401', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='246F5D043B0EDB18C5375403ADDA18F79B3F2AF7B74142561237EE2EC5982510', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=27, block_height=89041656, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 39, tzinfo= UTC), memo = '325415231', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='1A7245E470D0A79B2BCDF2CCFA8533AC4B6AED0119CCED3297B954613F9CF096', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=29, block_height=89041654, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 50, tzinfo= UTC), memo = '325415231', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='9BF480E2C01ED318753A940BA96B7E3B7D9F4DF9342B81EDAD920CA8F62962B2', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
            value=Decimal('0.000001'), symbol='XRP', confirmations=31, block_height=89041652, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 41, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='69CCEC0025710CEB5C1BA9D5C96071AEDF192AB280EE60A46C095683FE17604F', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
            value=Decimal('0.000001'), symbol='XRP', confirmations=31, block_height=89041652, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 41, tzinfo= UTC), memo = '2082184339', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='7D728E9CA22851143F3CFFB678C9CA9EC3F448B1460134F7BDAB8F48364785E9', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rKcyeSaT9zhmZxJgUaQq1aFmyvMXd6x7FU',
            value=Decimal('0.000001'), symbol='XRP', confirmations=31, block_height=89041652, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 41, tzinfo= UTC), memo = '1140014125', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='4A0763DC78FC299AD9AB297234D02E2690DC4D457445368FAAE441A8AC3BFB8C', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV',
            value=Decimal('0.000001'), symbol='XRP', confirmations=31, block_height=89041652, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 41, tzinfo= UTC), memo = '399238402', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='5734608420F04536343DAFA485FA2B2A1CF768FF28E0CBE55E3F16891F30C71D', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
            value=Decimal('0.000001'), symbol='XRP', confirmations=33, block_height=89041650, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 32, tzinfo= UTC), memo = '2082184339', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='ED40EFA329506973886FD7F70F937426EF189CA39A827DF26E1EABD1996B0235', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
            value=Decimal('0.000001'), symbol='XRP', confirmations=33, block_height=89041650, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 32, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='488DACB2AC3D954EDE805CB93BA7DC89540A4F45BE371900C4AFEE40EB63D9EB', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rHcFoo6a9qT5NHiVn1THQRhsEGcxtYCV4d',
            value=Decimal('0.000001'), symbol='XRP', confirmations=33, block_height=89041650, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 32, tzinfo= UTC), memo = '2357348680', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='637D60DFFF8463A26E12F80E7E664FF9A8F8D2EB3C254797915969E460EFA0E0', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rRE2wh2SUotgtb552JcUxZLFpSjPh5sTy',
            value=Decimal('0.000001'), symbol='XRP', confirmations=35, block_height=89041648, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 30, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='E8E10B2D16166D1DB51CA6FD251FD8B5C2B2F33073391CEDC8F56658ADF956F6', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
            value=Decimal('0.000001'), symbol='XRP', confirmations=35, block_height=89041648, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 30, tzinfo= UTC), memo = '2082184339', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='8FCB35A11D0E07A1924A4D48D5FFA1C221A4A4FA289016211F13BC072CC048F2', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rHmku65GJrrsp6Sb7KRzCgM2tAA3JBACQZ',
            value=Decimal('0.000001'), symbol='XRP', confirmations=36, block_height=89041647, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 21, tzinfo= UTC), memo = '2017', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='5DCD5B2C744FABEDA6EEDD8A1689CED2CCA08E584FEA0E19CD3DF7A17CE434BC', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB',
            value=Decimal('0.000001'), symbol='XRP', confirmations=37, block_height=89041646, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 20, tzinfo= UTC), memo = '2082184339', tx_fee = Decimal(
            '0.000025'), token = None, index = None), TransferTx(
            tx_hash='03A533E1219E81D57027CF3501045A1A334E19DDBD5F642F0F2959D83B3EFCFE', success=True,
            from_address='rwjyDXa3YsdZUJcJSDkyRRvt1qwPfxVNKY', to_address='rnHqddewfDgsZykzKJYgk9jFysebWbrL49',
            value=Decimal('0.000001'), symbol='XRP', confirmations=38, block_height=89041645, block_hash=None,
            date=datetime.datetime(2024, 6, 30, 7, 38, 12, tzinfo= UTC), memo = '1836815735', tx_fee = Decimal(
            '0.000025'), token = None, index = None)]
        ]
        for address_txs, expected_address_txs in zip(addresses_txs, expected_addresses_txs):
            assert address_txs == expected_address_txs
