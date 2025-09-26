import datetime
import json
import os
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.db.models import Sum
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.constants import MAX_POSITIVE_32_INT
from exchange.base.id_translation import encode_id
from exchange.base.models import CURRENCY_CODENAMES, Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.wallet.crons import RemoveOldTransactionHistoriesCron
from exchange.wallet.models import Transaction, TransactionHistoryFile, Wallet
from exchange.wallet.tasks import export_transaction_history


class TransactionHistoryTestMixin:
    url = '/users/transactions-history'
    TRANSACTION_SIZE: int

    @classmethod
    def setUpTestData(cls):
        user = User.objects.get(id=201)
        cls.user = user
        cls.token = cls.user.auth_token.key

        wallets = [
            Wallet.get_user_wallet(user, Currencies.btc),
            Wallet.get_user_wallet(user, Currencies.eth),
            Wallet.get_user_wallet(user, Currencies.doge),
            Wallet.get_user_wallet(user, Currencies.rls, tp=Wallet.WALLET_TYPE.margin),
        ]
        wallets_step_balances = {w.id: {} for w in wallets}
        transactions = []
        for wallet in wallets:
            balance = Decimal()
            amount_range = 3
            if wallet.currency == 10:
                amount_range = 1
            elif wallet.currency == 11:
                amount_range = 5
            elif wallet.currency == 18:
                amount_range = 1000
            for i in range(cls.TRANSACTION_SIZE):
                # TODO: remove random values
                amount = Decimal(
                    random.uniform(-min(float(balance), amount_range), amount_range)
                ).quantize(Decimal('0.0000000000'))
                transaction = Transaction(
                    wallet=wallet,
                    tp=random.choice(list(Transaction.TYPE._db_values)),
                    amount=amount,
                    description=str(i),
                    created_at=ir_now() + timedelta(random.randint(-10, 10)),
                    ref_module=None,
                    ref_id=None,
                    balance=wallet.balance + amount,
                )

                transactions.append(transaction)
                balance += amount
                wallet.balance = balance

                if (i + 1) % 1000 == 0:
                    wallets_step_balances[wallet.id][i + 1] = balance

            wallet.save()

        Transaction.objects.bulk_create(transactions)
        cls.transactions = transactions

        cls.wallets_step_balances = wallets_step_balances

        transactions = []
        for i in range(10):
            transaction = Transaction(
                wallet=wallets[0],
                tp=random.choice(list(Transaction.TYPE._db_values)),
                amount=0,
                description=str(i),
                created_at=ir_now() + timedelta(20),
                ref_module=None,
                ref_id=None,
                balance=wallets[0].balance + 0,
            )
            transactions.append(transaction)
        Transaction.objects.bulk_create(transactions)


class TransactionHistoryFullTests(TransactionHistoryTestMixin, APITestCase):
    TRANSACTION_SIZE = 3000

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_authentication(self):
        """
        Test Accessing the url with and without user authentication.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_balance_calculation(self):
        """
        Test that the calculation of transaction balance is performed correctly.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for wallet_id in self.wallets_step_balances.keys():
            transaction_1000 = Transaction.objects.filter(wallet_id=wallet_id).order_by('id')[999]
            self.assertEqual(transaction_1000.balance, self.wallets_step_balances[wallet_id][1000])

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for wallet_id in self.wallets_step_balances.keys():
            transaction_2000 = Transaction.objects.filter(wallet_id=wallet_id).order_by('id')[1999]
            self.assertEqual(transaction_2000.balance, self.wallets_step_balances[wallet_id][2000])

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for wallet_id in self.wallets_step_balances.keys():
            transaction_last = Transaction.objects.filter(wallet_id=wallet_id).order_by('id').last()
            self.assertEqual(transaction_last.balance, self.wallets_step_balances[wallet_id][3000])

    def test_from_id(self):
        transactions = Transaction.objects.order_by('-created_at').all()
        from_id = transactions[7].pk

        response = self.client.get(self.url, data={'from_id': from_id})
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert len(json_response['transactions']) == 7

        transactions_with_negative_id = transactions[8]
        transactions_with_negative_id.id = -1
        transactions_with_negative_id.created_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=21
        )
        transactions_with_negative_id.save()

        response = self.client.get(self.url, data={'from_id': from_id})
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert len(json_response['transactions']) == 8

        response = self.client.get(self.url, data={'from_id': -2 + MAX_POSITIVE_32_INT})
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert len(json_response['transactions']) == 1

        response = self.client.get(self.url, data={'from_id': MAX_POSITIVE_32_INT})
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert len(json_response['transactions']) == 0

    def test_pagination(self):
        response = self.client.get(self.url + '?page=1201&pageSize=10')
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert json_response['hasNext'] is False
        assert len(json_response['transactions']) == 10

        response = self.client.get(self.url + '?page=1202&pageSize=10')
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert json_response['hasNext'] is False
        assert len(json_response['transactions']) == 0

    def test_id_is_positive(self):
        transaction = Transaction.objects.order_by('-id').all()[0]
        transaction.id = -1
        transaction.save()

        from_id = encode_id(transaction.pk) - 1

        response = self.client.get(self.url, data={'from_id': from_id})
        json_response = json.loads(response.content)
        assert json_response['status'] == 'ok'
        assert len(json_response['transactions']) == 1
        assert json_response['transactions'][0]['id'] == encode_id(transaction.pk)


class TransactionHistoryLightTests(TransactionHistoryTestMixin, APITestCase):
    TRANSACTION_SIZE = 10

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_authentication(self):
        """
        Test Accessing the url with and without user authentication.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_content_structure(self):
        """
        Test url response is serialized and has correct structure.
        """
        response = self.client.get(self.url)
        json_response = json.loads(response.content)
        self.assertEqual(json_response['status'], 'ok')

        type_id_map = {v: k for k, v in Transaction.TYPE._identifier_map.items()}
        last_transaction = json_response['transactions'][0]
        last_transaction_obj = Transaction.objects.order_by('-id', '-created_at').first()
        assert (
            set(['id', 'created_at', 'tp', 'type', 'currency', 'amount', 'balance', 'description', 'calculatedFee'])
            == set(last_transaction.keys())
        )

        assert last_transaction['id'] == last_transaction_obj.id
        assert last_transaction['amount'] == str(last_transaction_obj.amount)
        assert last_transaction['balance'] == str(last_transaction_obj.balance)
        assert last_transaction['description'] == last_transaction_obj.description
        assert last_transaction['created_at'] == last_transaction_obj.created_at.isoformat()
        assert last_transaction['tp'] == type_id_map.get(last_transaction_obj.tp, 'etc')
        assert last_transaction['type'] == Transaction.TYPES_HUMAN_DISPLAY.get(last_transaction_obj.tp, 'سایر')
        assert last_transaction['currency'] == CURRENCY_CODENAMES.get(last_transaction_obj.wallet.currency, '').lower()
        assert last_transaction['calculatedFee'] is None

    def test_balance_calculation(self):
        """
        Test that the calculation of transaction balance is performed correctly and wallet and last transaction
        balance are asserted with write values.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for wallet in Wallet.objects.all():
            wallet_transactions = Transaction.objects.filter(wallet=wallet).order_by('id')
            last_wallet_transaction = wallet_transactions.last()
            balance_sum = wallet_transactions.aggregate(Sum('amount'))['amount__sum'] or 0
            self.assertEqual(wallet.balance, balance_sum)
            self.assertEqual(last_wallet_transaction.balance if last_wallet_transaction else 0, balance_sum)

    def test_filter_on_currency(self):
        response = self.client.get(self.url + f'?currency=eth')
        assert response.status_code == status.HTTP_200_OK

        wallet_transactions = Transaction.objects.filter(wallet__currency=Currencies.eth)
        transactions = response.json()['transactions']
        self._assert_transactions(wallet_transactions, transactions)

        response = self.client.get(self.url + '?currency=invalid-currency')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'
        assert response.json()['message'] == 'Invalid choices: "invalid-currency"'

    def test_filter_on_tp(self):
        response = self.client.get(self.url + '?tp=manual,buy,')
        assert response.status_code == status.HTTP_200_OK

        wallet_transactions = Transaction.objects.filter(
            tp__in=[getattr(Transaction.TYPE, tp) for tp in ['manual', 'buy']],
        )
        transactions = response.json()['transactions']
        self._assert_transactions(wallet_transactions, transactions)

        response = self.client.get(self.url + '?tp=')
        transactions = response.json()['transactions']
        assert len(transactions) == Transaction.objects.count()

        response = self.client.get(self.url + '?tp=invalid-type')
        self._assert_invalid_tp(response)

        response = self.client.get(self.url + '?tp=buy,invalid-type')
        self._assert_invalid_tp(response)

    def test_filter_on_from(self):
        response = self.client.get(self.url + f'?from={int(self.transactions[5].created_at.timestamp())}')
        assert response.status_code == status.HTTP_200_OK, response.content
        wallet_transactions = Transaction.objects.filter(
            created_at__gte=parse_utc_timestamp(int(self.transactions[5].created_at.timestamp())),
        )
        transactions = response.json()['transactions']
        self._assert_transactions(wallet_transactions, transactions)

        response = self.client.get(self.url + f'?from=invalid-ts')
        self._assert_invalid_timestamp(response)

    def test_filter_on_to(self):
        response = self.client.get(self.url + f'?to={int(self.transactions[5].created_at.timestamp())}')
        assert response.status_code == status.HTTP_200_OK, response.content
        wallet_transactions = Transaction.objects.filter(
            created_at__lte=parse_utc_timestamp(int(self.transactions[5].created_at.timestamp())),
        )
        transactions = response.json()['transactions']
        self._assert_transactions(wallet_transactions, transactions)

        response = self.client.get(self.url + f'?to=invalid-ts')
        self._assert_invalid_timestamp(response)

    def test_filter_on_from_to_range(self):
        now_ts = int(ir_now().timestamp())

        # to must be greater than from
        response = self.client.get(self.url + f'?to={now_ts}&from={now_ts + 1}')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'InvalidPeriod'
        assert response.json()['message'] == 'from must be before to.'

        # range should be lower than 90 days
        response = self.client.get(self.url + f'?to={now_ts}&from={now_ts - 90 * 24 * 3600 - 1}')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'PeriodTooLong'
        assert response.json()['message'] == 'to - from must be less than 90 days'

    def _assert_transactions(self, expected, actual):
        assert len(actual) == expected.count()
        assert {tx['id'] for tx in actual} == {tx.id for tx in expected}

    def _assert_invalid_timestamp(self, response):
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'
        assert response.json()['message'] == 'Invalid integer value: "invalid-ts"'

    def _assert_invalid_tp(self, response):
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'
        assert response.json()['message'] == 'Invalid choices: "invalid-type"'


class TransactionHistoryRequestTests(TransactionHistoryTestMixin, APITestCase):
    url = '/users/transactions-histories/request'
    TRANSACTION_SIZE = 10

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        self.from_ts = int(ir_now().timestamp() - 5)
        self.to_ts = int(ir_now().timestamp() + 10000)
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

    def request(self, from_ts=None, to_ts=None, currency=None, tp=None, exclude=None):
        """
        Send a transaction history request with specified parameters.

        Parameters:
            from_ts (int): Start timestamp for the transaction history.
            to_ts (int): End timestamp for the transaction history.
            currency (str): Currency for filtering transactions.
            tp (str): Transaction type for filtering transactions.
            exclude (str): Parameter to exclude from the request.

        Returns:
            Response: The response received from the request.
        """

        data = {'from': from_ts or self.from_ts, 'to': to_ts or self.to_ts}
        if tp is not None:
            data.update(tp=tp)

        if currency is not None:
            data.update(currency=currency)

        if exclude is not None:
            del data[exclude]

        response = self.client.post(self.url, data=data, format='json')
        return response

    def test_authentication(self):
        response = self.request()
        assert response.status_code == status.HTTP_200_OK

        self.client.credentials()
        response = self.request()
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def assert_ok(self, response):
        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response['status'] == 'ok'
        assert json_response['message'] == 'Download link will be emailed to the user.'

    def assert_not_ok(self, response, status_code, code, message):
        assert response.status_code == status_code
        json_response = response.json()
        assert json_response['status'] == 'failed'
        assert json_response['code'] == code
        assert json_response['message'] == message

    def test_validation(self):
        response = self.request()
        self.assert_ok(response)

        response = self.request(from_ts='not-valid-ts')
        self.assert_not_ok(response, 400, 'ParseError', 'Invalid integer value: "not-valid-ts"')

        response = self.request(to_ts='not-valid-ts')
        self.assert_not_ok(response, 400, 'ParseError', 'Invalid integer value: "not-valid-ts"')

        response = self.request(exclude='from')
        self.assert_not_ok(response, 400, 'ParseError', 'Missing datetime value')

        response = self.request(exclude='to')
        self.assert_not_ok(response, 400, 'ParseError', 'Missing datetime value')

        response = self.request(to_ts=self.from_ts - 1)
        self.assert_not_ok(response, 422, 'InvalidPeriod', 'from must be before to.')

        response = self.request(to_ts=self.from_ts + int(timedelta(days=90, seconds=1).total_seconds()))
        self.assert_not_ok(response, 422, 'PeriodTooLong', 'to - from must be less than 90 days')

        response = self.request(tp='buy,' * 26)
        self.assert_not_ok(response, 400, 'ParseError', 'Multi choices is too long, max len is 25')

        self.user.verification_profile.email_confirmed = False
        self.user.verification_profile.save()

        response = self.request(to_ts=self.from_ts + int(timedelta(days=89).total_seconds()))
        self.assert_not_ok(response, 400, 'UnverifiedEmail', 'User does not have a verified email.')

    def test_max_per_user(self):
        for i in range(TransactionHistoryFile.MAX_PER_USER - 1):
            TransactionHistoryFile.objects.create(
                from_datetime=ir_now(),
                to_datetime=ir_now() + timedelta(seconds=i),
                user=self.user,
            )

        TransactionHistoryFile.objects.create(
            from_datetime=ir_now(),
            to_datetime=ir_now(),
            user=User.objects.get(pk=202),
        )

        response = self.request()
        self.assert_ok(response)

        TransactionHistoryFile.objects.create(
            from_datetime=ir_now(),
            to_datetime=ir_now() + timedelta(seconds=10000),
            user=self.user,
        )
        response = self.request()
        self.assert_not_ok(response, 422, 'MaxTransactionHistoryReached', 'User reached to max transaction history.')

    @patch('exchange.wallet.models.TransactionHistoryFile.send_email')
    @patch('exchange.wallet.tasks.export_csv')
    def test_export_transaction_history_task(self, export_csv, send_email):
        type_id_map = {v: k for k, v in Transaction.TYPE._identifier_map.items()}
        from_ = ir_now()
        to = ir_now() + timedelta(seconds=1000)
        currency = Currencies.eth
        tps = [Transaction.TYPE.manual, Transaction.TYPE.buy]
        amount = Decimal('1.23')
        wallet = Wallet.objects.get(user=self.user, currency=currency)
        Transaction.objects.create(
            wallet=wallet,
            tp=Transaction.TYPE.manual,
            amount=amount,
            description='test desc',
            created_at=from_ + timedelta(seconds=10),
            ref_module=None,
            ref_id=None,
            balance=wallet.balance + amount,
        )

        expected_txs = Transaction.objects.filter(
            wallet=wallet,
            tp__in=tps,
            created_at__gte=from_,
            created_at__lt=to,
        )

        export_transaction_history(
            user_id=self.user.id,
            from_datetime=from_.isoformat(),
            to_datetime=to.isoformat(),
            currency=currency,
            tps=tps,
        )

        transaction_file_history = TransactionHistoryFile.objects.first()
        assert transaction_file_history is not None
        assert transaction_file_history.from_datetime == from_
        assert transaction_file_history.to_datetime == to
        assert transaction_file_history.currency == currency
        assert transaction_file_history.tps == '30_60'

        export_csv.assert_called_once()
        disk_path, transactions, headers = export_csv.call_args[0]
        send_email.assert_called_once()

        assert (
            set(transactions[0].keys())
            == set(headers)
            == {'id', 'createdAt', 'type', 'tp', 'currency', 'amount', 'balance', 'description'}
        )
        assert (
            disk_path
            == transaction_file_history.disk_path
            == (
                Path(settings.MEDIA_ROOT)
                / 'uploads'
                / TransactionHistoryFile.DIRECTORY_NAME
                / transaction_file_history.file_name
            )
        )

        assert expected_txs.count() == len(transactions)
        for expected_tx, actual_tx in zip(expected_txs, transactions):
            assert expected_tx.id == actual_tx['id']
            assert expected_tx.balance == actual_tx['balance']
            assert expected_tx.description == actual_tx['description']
            assert expected_tx.amount == actual_tx['amount']
            assert type_id_map.get(expected_tx.tp, 'etc') == actual_tx['tp']
            assert Transaction.TYPES_HUMAN_DISPLAY.get(expected_tx.tp, 'سایر') == actual_tx['type']
            assert CURRENCY_CODENAMES.get(expected_tx.currency, '').lower() == actual_tx['currency']

        # When calling again, without any change to the result, task should not sent email
        send_email.reset_mock()
        export_transaction_history(
            user_id=self.user.id,
            from_datetime=from_.isoformat(),
            to_datetime=to.isoformat(),
            currency=currency,
            tps=tps,
        )
        send_email.assert_not_called()


class TransactionHistoryDownloadTests(APITestCase):
    url = '/users/transactions-histories/%s/download'

    def setUp(self):
        self.user = User.objects.get(id=201)
        self.token = self.user.auth_token.key
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

        self.transaction_history_file = TransactionHistoryFile.objects.create(
            from_datetime=ir_now(),
            to_datetime=ir_now(),
            user=self.user,
        )

    def request(self, id: int = None):
        response = self.client.get(self.url % (id or self.transaction_history_file.pk))
        return response

    def test_authentication(self):
        response = self.request()
        assert response.status_code == status.HTTP_200_OK

        self.client.credentials()
        response = self.request()
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def assert_code(self, response, status_code):
        assert response.status_code == status_code

    def test_successful(self):
        response = self.request()
        self.assert_code(response, 200)

    def test_not_found(self):
        response = self.request(-1)
        self.assert_code(response, 404)

    def test_get_deleted(self):
        with open(self.transaction_history_file.disk_path, 'w') as f:
            f.write('test')

        self.transaction_history_file.delete()
        response = self.request()
        self.assert_code(response, 404)
        assert os.path.isfile(self.transaction_history_file.disk_path) is False

    def test_get_others_history(self):
        others_transaction_history_file = TransactionHistoryFile.objects.create(
            from_datetime=ir_now(),
            to_datetime=ir_now() + timedelta(seconds=10),
            user=User.objects.get(pk=202),
        )
        response = self.request(others_transaction_history_file.pk)
        self.assert_code(response, 404)

    @override_settings(IS_PROD=True)
    def test_link_prod(self):
        expected_link = 'https://nobitex.ir/panel/turnover/transaction/tx-download/' + str(self.transaction_history_file.pk)
        assert self.transaction_history_file.link == expected_link

    @override_settings(IS_PROD=False)
    def test_link_testnet(self):
        expected_link = 'https://testnet.nobitex.ir/panel/turnover/transaction/tx-download/' + str(self.transaction_history_file.pk)
        assert self.transaction_history_file.link == expected_link

class TransactionHistoryCleanupCronTests(APITestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)

    def create_file(self, disk_path):
        with open(disk_path, 'w') as f:
            f.write('test')

    def test_cleanup_old_files(self):
        """
        Test the cleanup of old transaction history files:
        - Creates two transaction history files, one old and one newer.
        - Simulates running the cron job to remove old files.
        - Asserts that the old file is deleted from the database.
        - Asserts that the newer file still exists in the database.
        - Asserts that the old file is no longer present on disk.
        - Asserts that the newer file is still present on disk.
        """

        old_transaction_history_file = TransactionHistoryFile.objects.create(
            created_at=ir_now() - TransactionHistoryFile.MAX_AGE,
            from_datetime=ir_now(),
            to_datetime=ir_now(),
            currency=Currencies.eth,
            tps=str(Transaction.TYPE.buy),
            user=self.user,
        )
        newer_transaction_history_file = TransactionHistoryFile.objects.create(
            created_at=ir_now() - TransactionHistoryFile.MAX_AGE + timedelta(seconds=2),
            from_datetime=ir_now(),
            to_datetime=ir_now() + timedelta(days=10),
            currency=Currencies.eth,
            tps=str(Transaction.TYPE.buy),
            user=self.user,
        )

        self.create_file(old_transaction_history_file.disk_path)
        self.create_file(newer_transaction_history_file.disk_path)

        RemoveOldTransactionHistoriesCron().run()

        assert TransactionHistoryFile.objects.filter(pk=old_transaction_history_file.id).exists() is False
        assert TransactionHistoryFile.objects.filter(pk=newer_transaction_history_file.id).exists() is True

        assert os.path.isfile(old_transaction_history_file.disk_path) is False
        assert os.path.isfile(newer_transaction_history_file.disk_path) is True

        os.remove(newer_transaction_history_file.disk_path)
