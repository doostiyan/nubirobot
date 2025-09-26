import unittest
import base64
from exchange.blockchain.api.ton.utils import TonAddressConvertor


class TestTonAddressConvertor(unittest.TestCase):

    def test_detect_address_type_bounceable(self):
        address = base64.urlsafe_b64encode(b'\x11' + b'\x00' * 34).decode('utf8')
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Unknown')

        address = 'EQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxdJT'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Bounceable')

        address = 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Bounceable')

    def test_detect_address_type_non_bounceable(self):
        address = base64.urlsafe_b64encode(b'\x51' + b'\x00' * 34).decode('utf8')
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Unknown')

        address = 'UQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxY-W'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Non-Bounceable')

        address = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Non-Bounceable')

    def test_detect_address_type_hex(self):
        address = '0' * 64
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Hex')

        address = '0b4b194dedd1a2e715549789e83d89bf8276d9d1e824798abb56bddaea8968c5'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Hex')

        address = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Hex')

    def test_detect_address_type_unknown(self):
        address = 'invalid_address'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Unknown')

        address = 'hskfnsonfowie39843ff939j0d3029j202dj309joand'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Unknown')

        address = '932nc20_934nfc-+i923==/nciwncidunc129cin039j'
        self.assertEqual(TonAddressConvertor.detect_address_type(address), 'Unknown')

    def test_convert_bounceable_to_hex(self):
        address = 'EQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxdJT'
        result = TonAddressConvertor.convert_bounceable_to_hex(address)
        expected_result = '0b4b194dedd1a2e715549789e83d89bf8276d9d1e824798abb56bddaea8968c5'
        self.assertEqual(result, expected_result)

        address = 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs'
        result = TonAddressConvertor.convert_bounceable_to_hex(address)
        expected_result = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        self.assertEqual(result, expected_result)

        address = 'EQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbJ8T'
        result = TonAddressConvertor.convert_bounceable_to_hex(address)
        expected_result = '4d42c63ffc3072783e2ba615de061353df2ba44ae052c98ccef7ea0d67b4586c'
        self.assertEqual(result, expected_result)

    def test_convert_bounceable_to_non_bounceable(self):
        address = base64.urlsafe_b64encode(b'\x11' + b'\x00' * 34).decode('utf8')
        result = TonAddressConvertor.convert_bounceable_to_non_bounceable(address)
        self.assertEqual(TonAddressConvertor.detect_address_type(result), 'Unknown')

        address = 'EQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxdJT'
        result = TonAddressConvertor.convert_bounceable_to_non_bounceable(address)
        expected_result = 'UQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxY-W'
        self.assertEqual(result, expected_result)

        address = 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs'
        result = TonAddressConvertor.convert_bounceable_to_non_bounceable(address)
        expected_result = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        self.assertEqual(result, expected_result)

        address = 'EQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbJ8T'
        result = TonAddressConvertor.convert_bounceable_to_non_bounceable(address)
        expected_result = 'UQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbMLW'
        self.assertEqual(result, expected_result)

    def test_convert_hex_to_bounceable(self):
        raw = '0' * 64
        result = TonAddressConvertor.convert_hex_to_bounceable(raw)
        self.assertEqual(TonAddressConvertor.detect_address_type(result), 'Bounceable')

        address = '4d42c63ffc3072783e2ba615de061353df2ba44ae052c98ccef7ea0d67b4586c'
        result = TonAddressConvertor.convert_hex_to_bounceable(address)
        expected_result = 'EQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbJ8T'
        self.assertEqual(result, expected_result)

        address = '7d39154d46ab47250ea3aa63a9d551aeaaafbfcea5125fda503831425aca735a'
        result = TonAddressConvertor.convert_hex_to_bounceable(address)
        expected_result = 'EQB9ORVNRqtHJQ6jqmOp1VGuqq-_zqUSX9pQODFCWspzWrtH'
        self.assertEqual(result, expected_result)

        address = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        result = TonAddressConvertor.convert_hex_to_bounceable(address)
        expected_result = 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs'
        self.assertEqual(result, expected_result)

    def test_convert_hex_to_non_bounceable(self):
        raw = '0' * 64
        result = TonAddressConvertor.convert_hex_to_non_bounceable(raw)
        self.assertEqual(TonAddressConvertor.detect_address_type(result), 'Non-Bounceable')

        address = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        result = TonAddressConvertor.convert_hex_to_non_bounceable(address)
        expected_result = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        self.assertEqual(result, expected_result)

        address = '4d42c63ffc3072783e2ba615de061353df2ba44ae052c98ccef7ea0d67b4586c'
        result = TonAddressConvertor.convert_hex_to_non_bounceable(address)
        expected_result = 'UQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbMLW'
        self.assertEqual(result, expected_result)

        address = '7d39154d46ab47250ea3aa63a9d551aeaaafbfcea5125fda503831425aca735a'
        result = TonAddressConvertor.convert_hex_to_non_bounceable(address)
        expected_result = 'UQB9ORVNRqtHJQ6jqmOp1VGuqq-_zqUSX9pQODFCWspzWuaC'
        self.assertEqual(result, expected_result)

    def test_convert_non_bounceable_to_bounceable(self):
        address = base64.urlsafe_b64encode(b'\x51' + b'\x00' * 34).decode('utf8')
        result = TonAddressConvertor.convert_non_bounceable_to_bounceable(address)
        self.assertEqual(TonAddressConvertor.detect_address_type(result), 'Unknown')

        address = 'UQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxY-W'
        result = TonAddressConvertor.convert_non_bounceable_to_bounceable(address)
        expected_result = 'EQALSxlN7dGi5xVUl4noPYm_gnbZ0egkeYq7Vr3a6oloxdJT'
        self.assertEqual(result, expected_result)

        address = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        result = TonAddressConvertor.convert_non_bounceable_to_bounceable(address)
        expected_result = 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs'
        self.assertEqual(result, expected_result)

        address = 'UQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbMLW'
        result = TonAddressConvertor.convert_non_bounceable_to_bounceable(address)
        expected_result = 'EQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbJ8T'
        self.assertEqual(result, expected_result)

    def test_convert_non_bounceable_to_hex(self):
        address = base64.urlsafe_b64encode(b'\x51' + b'\x00' * 34).decode('utf8')
        result = TonAddressConvertor.convert_non_bounceable_to_hex(address)
        self.assertEqual(result, '0' * 64)

        address = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        result = TonAddressConvertor.convert_non_bounceable_to_hex(address)
        expected_result = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        self.assertEqual(result, expected_result)

        address = 'UQBNQsY__DByeD4rphXeBhNT3yukSuBSyYzO9-oNZ7RYbMLW'
        result = TonAddressConvertor.convert_non_bounceable_to_hex(address)
        expected_result = '4d42c63ffc3072783e2ba615de061353df2ba44ae052c98ccef7ea0d67b4586c'
        self.assertEqual(result, expected_result)

        address = 'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp'
        result = TonAddressConvertor.convert_non_bounceable_to_hex(address)
        expected_result = 'a32d52ced80a23fe4fe90ba94593ef686de03f9fbdaa069e642826a95234b982'
        self.assertEqual(result, expected_result)

    def test_invalid_bounceable_to_hex(self):
        with self.assertRaises(Exception):
            TonAddressConvertor.convert_bounceable_to_hex('invalid_address')

    def test_invalid_non_bounceable_to_hex(self):
        with self.assertRaises(Exception):
            TonAddressConvertor.convert_non_bounceable_to_hex('invalid_address')
