import datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import Currencies
from exchange.staking.models import ExternalEarningPlatform, StakingTransaction
from tests.staking.utils import StakingTestDataMixin


class UnsubscriptionAPITest(StakingTestDataMixin, TestCase):
    URL = '/earn/unsubscription'

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=cls.user.get_verification_profile().id).update(email_confirmed=True)
        cls.user.save()

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def test_success(
        self,
    ):
        response = self.client.get(self.URL)
        assert response.json()['result'] == []

        instant_end_trx = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('10'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.end_request,
                Decimal('0'),
            ),
        )
        staking_v1_end_trx = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('45'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request,
                Decimal('22'),
            ),
        )
        not_extending_trx = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('44'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request,
                Decimal('220'),
            ),
        )
        plan_not_extendable_unstake_trx = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('66'),
        )
        self.create_staking_transaction(
            StakingTransaction.TYPES.release,
            Decimal('11'),
            parent=not_extending_trx,
        )
        get_datetime_utc_iso = lambda dt: (
            datetime.datetime.fromtimestamp(dt.timestamp(), datetime.timezone(datetime.timedelta()))
        ).isoformat()

        response = self.client.get(self.URL)
        assert response.json()['result'] == [
            {
                'id': trx.id,
                'createdAt': get_datetime_utc_iso(trx.created_at),
                'releaseAt': {
                    StakingTransaction.TYPES.instant_end_request: get_datetime_utc_iso(trx.created_at),
                    StakingTransaction.TYPES.end_request: get_datetime_utc_iso(
                        trx.created_at + self.plan.unstaking_period
                    ),
                    StakingTransaction.TYPES.auto_end_request: get_datetime_utc_iso(
                        trx.created_at + self.plan.unstaking_period
                    ),
                    None: get_datetime_utc_iso(trx.created_at + self.plan.unstaking_period),
                }[trx.parent.tp if trx.parent else None],
                'amount': str(trx.amount),
                'releasedAmount': {
                    StakingTransaction.TYPES.instant_end_request: '0',
                    StakingTransaction.TYPES.end_request: '0',
                    StakingTransaction.TYPES.auto_end_request: '11',
                    None: '0',
                }[trx.parent.tp if trx.parent else None],
                'type': {
                    StakingTransaction.TYPES.instant_end_request: 'instant_end_request',
                    StakingTransaction.TYPES.end_request: 'end_request',
                    StakingTransaction.TYPES.auto_end_request: 'auto_end_request',
                    None: 'non_extendable_plan',
                }[trx.parent.tp if trx.parent else None],
                'planId': self.plan.id,
                'planStartedAt': get_datetime_utc_iso(self.plan.staked_at),
                'planStakingPeriod': self.plan.staking_period.total_seconds(),
                'planCurrency': self.plan.currency_codename,
                'planType': 'staking',
            }
            for trx in [
                instant_end_trx,
                staking_v1_end_trx,
                not_extending_trx,
                plan_not_extendable_unstake_trx,
            ]
        ]

    def test_success_when_user_has_only_end_request_transaction(self):
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('10'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.end_request,
                Decimal('0'),
            ),
        )

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '10'
        assert data['planCurrency'] == 'btc'
        assert data['planId'] == transaction.plan.id
        assert data['id'] == transaction.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planType'] == 'staking'
        assert data['releasedAmount'] == '0'
        assert data['type'] == 'end_request'
        assert data['createdAt']
        assert data['planStartedAt']
        assert data['releaseAt']

    def test_success_when_user_has_only_instant_end_request_transaction(self):
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('45'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request,
                Decimal('22'),
            ),
        )

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '45'
        assert data['createdAt']
        assert data['id'] == transaction.id
        assert data['planCurrency'] == 'btc'
        assert data['planId'] == transaction.plan.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planStartedAt']
        assert data['planType'] == 'staking'
        assert data['releaseAt']
        assert data['releasedAmount'] == '0'
        assert data['type'] == 'instant_end_request'

    def test_success_when_user_has_auto_end_transaction(self):
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('44'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request,
                Decimal('220'),
            ),
        )
        self.create_staking_transaction(
            StakingTransaction.TYPES.release,
            Decimal('11'),
            parent=transaction,
        )

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '44'
        assert data['createdAt']
        assert data['id'] == transaction.id
        assert data['planCurrency'] == 'btc'
        assert data['planId'] == transaction.plan.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planStartedAt']
        assert data['planType'] == 'staking'
        assert data['releaseAt']
        assert data['releasedAmount'] == '11'
        assert data['type'] == 'auto_end_request'

    def test_success_when_user_has_not_extendable_plan(self):
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('66'),
        )

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '66'
        assert data['createdAt']
        assert data['id'] == transaction.id
        assert data['planCurrency'] == 'btc'
        assert data['planId'] == transaction.plan.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planStartedAt']
        assert data['planType'] == 'staking'
        assert data['releaseAt']
        assert data['releasedAmount'] == '0'
        assert data['type'] == 'non_extendable_plan'

    def test_success_when_filtering_with_external_earning_platform_and_user_has_auto_end_transaction(self):
        yield_aggregator_plan_kwargs = self.get_plan_kwargs(
            external_platform=self.add_external_platform(
                Currencies.atom, ExternalEarningPlatform.TYPES.yield_aggregator
            )
        )
        plan = self.create_plan(**yield_aggregator_plan_kwargs)
        # yield aggregation transactions
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('31'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request,
                Decimal('220'),
                plan=plan,
            ),
            plan=plan,
        )
        self.create_staking_transaction(
            StakingTransaction.TYPES.release,
            Decimal('20'),
            parent=transaction,
            plan=plan,
        )
        # staking transactions
        self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('44'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request,
                Decimal('220'),
            ),
        )
        self.create_staking_transaction(
            StakingTransaction.TYPES.release,
            Decimal('0'),
            parent=transaction,
        )

        params = {
            'type': 'yield_aggregator',
        }
        response = self.client.get(self.URL, data=params)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '31'
        assert data['createdAt']
        assert data['id'] == transaction.id
        assert data['planCurrency'] == 'atom'
        assert data['planId'] == transaction.plan.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planStartedAt']
        assert data['planType'] == 'yield_aggregator'
        assert data['releaseAt']
        assert data['releasedAmount'] == '20'
        assert data['type'] == 'auto_end_request'

    def test_success_when_filtering_with_external_earning_platform_and_user_has_instant_end_request_transaction(self):
        yield_aggregator_plan_kwargs = self.get_plan_kwargs(
            external_platform=self.add_external_platform(
                Currencies.atom, ExternalEarningPlatform.TYPES.yield_aggregator
            )
        )
        plan = self.create_plan(**yield_aggregator_plan_kwargs)
        # yield aggregation transactions
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('31'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request,
                Decimal('5'),
            ),
            plan=plan,
        )
        # staking transactions
        self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('45'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request,
                Decimal('22'),
            ),
        )

        params = {
            'type': 'yield_aggregator',
        }
        response = self.client.get(self.URL, data=params)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        data = data['result']
        assert data
        assert len(data) == 1
        data = data[0]
        assert data['amount'] == '31'
        assert data['createdAt']
        assert data['id'] == transaction.id
        assert data['planCurrency'] == 'atom'
        assert data['planId'] == transaction.plan.id
        assert data['planStakingPeriod'] == 86400.0
        assert data['planStartedAt']
        assert data['planType'] == 'yield_aggregator'
        assert data['releaseAt']
        assert data['releasedAmount'] == '0'
        assert data['type'] == 'instant_end_request'

    def test_success_when_user_has_no_unsubscription_transaction(self):
        another_user = self.create_user()
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.unstake,
            Decimal('44'),
            user=another_user,
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request,
                Decimal('220'),
                user=another_user,
            ),
        )
        self.create_staking_transaction(
            StakingTransaction.TYPES.release,
            Decimal('11'),
            parent=transaction,
            user=another_user,
        )

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['result'] == []

    def test_when_user_is_not_authenticated(self):
        self.client.logout()
        self.client.defaults.pop('HTTP_AUTHORIZATION')

        response = self.client.get(self.URL)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data.get('result') is None
        assert data.get('status') is None
        assert data['detail'] == 'اطلاعات برای اعتبارسنجی ارسال نشده است.'

    def test_success_with_pagination(self):
        for currency_id, _ in list(Currencies)[:20]:
            kwargs = self.get_plan_kwargs(
                external_platform=self.add_external_platform(currency_id, ExternalEarningPlatform.TYPES.staking)
            )
            plan = self.create_plan(**kwargs)
            transaction = self.create_staking_transaction(
                StakingTransaction.TYPES.unstake,
                Decimal('40'),
                parent=self.create_staking_transaction(
                    StakingTransaction.TYPES.auto_end_request,
                    Decimal('3'),
                ),
                plan=plan,
            )
            self.create_staking_transaction(
                StakingTransaction.TYPES.release, Decimal('13'), parent=transaction, plan=plan
            )

        data = {'page': 2, 'pageSize': 5}
        response = self.client.get(self.URL, data=data)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['hasNext'] == True
        assert data['status'] == 'ok'
        result = data['result']
        assert result
        assert len(result) == 5
        for item in result:
            assert item['amount'] == '40'
            assert item['createdAt']
            assert item['id']
            assert item['planCurrency']
            assert item['planId']
            assert item['planStakingPeriod'] == 86400.0
            assert item['planStartedAt']
            assert item['planType'] == 'staking'
            assert item['releaseAt']
            assert item['releasedAmount'] == '13'
            assert item['type'] == 'auto_end_request'
