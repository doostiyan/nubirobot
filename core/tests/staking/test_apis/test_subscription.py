import random
from decimal import Decimal
from typing import Optional

from django.test import TestCase
from django.utils.timezone import timedelta
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction

from ..utils import StakingTestDataMixin


class UserSubscriptionTest(StakingTestDataMixin, TestCase):
    URL = '/earn/subscription'

    @classmethod
    def setUpTestData(cls) -> None:
        cls.external_platform = cls.add_external_platform(Currencies.btc, ExternalEarningPlatform.TYPES.staking)
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=cls.user.get_verification_profile().id).update(email_confirmed=True)
        cls.user.save()

    def setUp(
        self,
    ):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('111'), plan=self.plan)
        self.create_staking_transaction(StakingTransaction.TYPES.extend_in, Decimal('100'), plan=self.plan)

    def assert_dates(self, staking: dict, plan: Optional[Plan] = None):
        plan = plan or self.plan
        started_at = plan.staked_at
        ended_at = started_at + plan.staking_period
        released_at = ended_at + plan.unstaking_period
        assert staking["releasedAt"] == self.to_utc_timezone(released_at).isoformat()
        assert staking["endedAt"] == self.to_utc_timezone(ended_at).isoformat()
        assert staking["startedAt"] == self.to_utc_timezone(started_at).isoformat()

    def test_canceled_staking(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.cancel_create_request, Decimal('10'), plan=self.plan)
        StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.stake).delete()
        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        staking = data['result']
        assert len(staking) == 0

    def test_ongoing_staking(
        self,
    ):
        self.plan.staked_at = ir_now() - timedelta(0.5)
        self.plan.save(
            update_fields=('staked_at',),
        )

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['status'] == 'staked'
        assert staking['isPlanExtendable']
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_blocked_staking(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.unstake, Decimal('10'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['receivedReward'] == '0'
        assert staking['extendedAmount'] == '0'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_released_staking(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.release, Decimal('100'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['releasedAmount'] == '100'
        assert staking['extendedAmount'] == '0'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_extended_staking(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('100'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['releasedAmount'] == '0'
        assert staking['extendedAmount'] == '100'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_partial_extention_and_block(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.unstake, Decimal('20'), plan=self.plan)
        self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('40'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['releasedAmount'] == '0'
        assert staking['extendedAmount'] == '40'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_partial_extention_and_release(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.release, Decimal('20'), plan=self.plan)
        self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('40'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['releasedAmount'] == '20'
        assert staking['extendedAmount'] == '40'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_awards(
        self,
    ):
        self.create_staking_transaction(StakingTransaction.TYPES.announce_reward, Decimal('10'), plan=self.plan)
        self.create_staking_transaction(StakingTransaction.TYPES.give_reward, Decimal('11'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '111'
        assert staking['announcedReward'] == '10'
        assert staking['receivedReward'] == '11'
        self.staking = StakingTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('40'),
        )
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_auto_extendable_staking(self):
        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['isAutoExtendEnabled'] is True
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_non_auto_extendable_staking(self):
        self.create_staking_transaction(StakingTransaction.TYPES.auto_end_request, Decimal('0'), plan=self.plan)

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['isAutoExtendEnabled'] is False
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_auto_extendable_flag_for_non_extendable_flag(self):
        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['isAutoExtendEnabled'] is True
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

        self.plan.is_extendable = False
        self.plan.save(update_fields=('is_extendable',))

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['isAutoExtendEnabled'] is False
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == False
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == False
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_instantly_unstaked_amount(self):
        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['instantlyUnstakedAmount'] == '0'
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('2'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request, Decimal('2'), plan=self.plan
            ),
            plan=self.plan,
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('1'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.instant_end_request, Decimal('1'), plan=self.plan
            ),
            plan=self.plan,
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('2'),
            parent=self.create_staking_transaction(StakingTransaction.TYPES.end_request, Decimal('5'), plan=self.plan),
            plan=self.plan,
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('7'),
            parent=self.create_staking_transaction(
                StakingTransaction.TYPES.auto_end_request, Decimal('0'), plan=self.plan
            ),
            plan=self.plan,
        )

        response = self.client.get(
            path=self.URL,
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking["amount"] == "111"
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "btc"
        assert staking["extendedAmount"] == "0"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "3"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == self.plan.id
        assert staking["receivedReward"] == "0"
        assert staking["releasedAmount"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "staking"
        self.assert_dates(staking)

    def test_with_pagination(self):
        for currency_id, _ in list(Currencies)[:20]:
            plan_kwargs = self.get_plan_kwargs(
                external_platform=self.add_external_platform(
                    currency_id,
                    random.choice(
                        [ExternalEarningPlatform.TYPES.staking, ExternalEarningPlatform.TYPES.yield_aggregator]
                    ),
                )
            )
            plan = Plan.objects.create(**plan_kwargs)
            self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('300'), plan=plan)
            self.create_staking_transaction(StakingTransaction.TYPES.release, Decimal('35'), plan=plan)
            self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('100'), plan=plan)

        data = {
            'page': 2,
            'pageSize': 7,
        }
        response = self.client.get(self.URL, data=data)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['hasNext'] == True
        assert data['status'] == 'ok'
        result = data['result']
        assert result
        assert len(result) == 7
        for item in result:
            assert item['amount'] == '300'
            assert item['releasedAmount'] == '35'
            assert item['extendedAmount'] == '100'
            assert item["announcedReward"] == "0"
            assert item["currency"]
            assert item["extendedPlanId"] is None
            assert item["instantlyUnstakedAmount"] == "0"
            assert item["isAutoExtendEnabled"] == True
            assert item["isInstantlyUnstakable"] == True
            assert item["isPlanExtendable"] == True
            assert item["planId"]
            assert item["receivedReward"] == "0"
            assert item["stakingPrecision"] == "0.1"
            assert item["status"] == "staked"
            assert item["type"] in ["yield_aggregator", 'staking']
            p = Plan.objects.get(id=item["planId"])
            self.assert_dates(item, plan=p)

    def test_with_filtering_plan_type(self):
        # yield_aggregator
        yield_aggregator_plan_kwargs = self.get_plan_kwargs(
            external_platform=self.add_external_platform(
                Currencies.usdt, ExternalEarningPlatform.TYPES.yield_aggregator
            ),
        )
        yield_aggregator_plan = Plan.objects.create(**yield_aggregator_plan_kwargs)
        self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('3000'), plan=yield_aggregator_plan)
        self.create_staking_transaction(StakingTransaction.TYPES.release, Decimal('11'), plan=yield_aggregator_plan)
        self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('13'), plan=yield_aggregator_plan)
        # staking
        self.create_staking_transaction(StakingTransaction.TYPES.release, Decimal('20'), plan=self.plan)
        self.create_staking_transaction(StakingTransaction.TYPES.extend_out, Decimal('40'), plan=self.plan)

        data = {
            'type': 'yield_aggregator',
        }
        response = self.client.get(path=self.URL, data=data)
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['hasNext'] == False
        staking = data['result']
        assert len(staking) == 1
        staking = staking[0]
        assert staking['amount'] == '3000'
        assert staking['releasedAmount'] == '11'
        assert staking['extendedAmount'] == '13'
        assert staking["announcedReward"] == "0"
        assert staking["currency"] == "usdt"
        assert staking["extendedPlanId"] is None
        assert staking["instantlyUnstakedAmount"] == "0"
        assert staking["isAutoExtendEnabled"] == True
        assert staking["isInstantlyUnstakable"] == True
        assert staking["isPlanExtendable"] == True
        assert staking["planId"] == yield_aggregator_plan.id
        assert staking["receivedReward"] == "0"
        assert staking["stakingPrecision"] == "0.1"
        assert staking["status"] == "staked"
        assert staking["type"] == "yield_aggregator"
        self.assert_dates(staking, plan=yield_aggregator_plan)

    def test_when_user_has_no_plan(self):
        StakingTransaction.objects.filter(user=self.user).delete()
        transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake,
            Decimal('100'),
            plan=self.plan,
        )
        transaction.user_id = 202
        transaction.save()

        response = self.client.get(self.URL)
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        assert data['result'] == []

    def test_without_being_login(self):
        self.client.logout()
        self.client.defaults.pop('HTTP_AUTHORIZATION')

        response = self.client.get(self.URL)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data.get('result') is None
        assert data.get('status') is None
        assert data['detail'] == 'اطلاعات برای اعتبارسنجی ارسال نشده است.'
