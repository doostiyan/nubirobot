import datetime
from decimal import Decimal

from django.test import Client, TestCase
from django.test.utils import override_settings
from django.utils.timezone import now

from exchange.accounts.models import User, UserPlan
from exchange.accounts.userlevels import UserPlanManager
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, Currencies
from exchange.pool.models import LiquidityPool, UserDelegation
from exchange.wallet.models import Wallet


class PlanTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def test_activate_trader_plan(self):
        assert not UserPlanManager.is_eligible_to_activate(self.user, UserPlan.TYPE.trader)
        self.user.user_type = User.USER_TYPES.level0
        assert not UserPlanManager.is_eligible_to_activate(self.user, UserPlan.TYPE.trader)
        self.user.user_type = User.USER_TYPES.level1
        assert UserPlanManager.is_eligible_to_activate(self.user, UserPlan.TYPE.trader)
        self.user.user_type = User.USER_TYPES.level2
        assert UserPlanManager.is_eligible_to_activate(self.user, UserPlan.TYPE.trader)
        self.user.user_type = User.USER_TYPES.verified
        assert UserPlanManager.is_eligible_to_activate(self.user, UserPlan.TYPE.trader)

    def test_deactivate_trader_plan(self):
        self.user.user_type = User.USER_TYPES.level1
        plan = UserPlan(user=self.user, type=UserPlan.TYPE.trader)
        plan.activate()

        # Users who are initially in level1 cannot exit trader plan
        assert not UserPlanManager.is_eligible_to_deactivate(plan)
        plan.set_kv('initial_user_type', User.USER_TYPES.level2, save=True)
        assert UserPlanManager.is_eligible_to_deactivate(plan)
        plan.set_kv('initial_user_type', User.USER_TYPES.level1p, save=True)
        assert not UserPlanManager.is_eligible_to_deactivate(plan)
        plan.set_kv('initial_user_type', User.USER_TYPES.verified, save=True)
        assert UserPlanManager.is_eligible_to_deactivate(plan)

        # Allow deactivation with only rial balance
        rial_wallet = Wallet.get_user_wallet(self.user, RIAL)
        rial_wallet.create_transaction('manual', Decimal('1_000_000_0')).commit()
        assert UserPlanManager.is_eligible_to_deactivate(plan)

        # Not allow deactivation with coin balance
        btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_wallet.create_transaction('manual', Decimal('0.001')).commit()
        assert UserPlanManager.is_eligible_to_deactivate(plan)
        btc_wallet.create_transaction('manual', Decimal('0.002')).commit()
        assert not UserPlanManager.is_eligible_to_deactivate(plan)
        btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_wallet.create_transaction('manual', Decimal('-0.002')).commit()

        # Not allow deactivation with active delegations
        plan.set_kv('initial_user_type', User.USER_TYPES.level2, save=True)
        btc_pool = LiquidityPool.objects.create(currency=Currencies.btc, capacity=10000, manager_id=410, is_active=True, activated_at=ir_now())
        user_delegation = UserDelegation.objects.create(pool=btc_pool, user=self.user, balance=Decimal('0.001'))
        assert not UserPlanManager.is_eligible_to_deactivate(plan)
        user_delegation.delete()

        # Allow exit after level2 verification
        plan.set_kv('initial_user_type', User.USER_TYPES.level1, save=True)
        assert not UserPlanManager.is_eligible_to_deactivate(plan)
        self.user.city = 'تهران'
        self.user.address = 'نوبیتکس'
        self.user.phone = '12345678'
        self.user.save(update_fields=['city', 'address', 'phone'])
        vp = self.user.get_verification_profile()
        vp.mobile_identity_confirmed = True
        vp.selfie_confirmed = True
        vp.bank_account_confirmed = True
        vp.mobile_confirmed = True
        vp.identity_confirmed = True
        vp.email_confirmed = True
        vp.address_confirmed = True
        vp.save()
        assert UserPlanManager.is_eligible_to_deactivate(plan)

    @override_settings(TRADER_PLAN_MONTHLY_LIMIT=2)
    def test_plan_api(self):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save(update_fields=['user_type'])
        # Activate
        r = self.client.post('/users/plans/activate', data={
            'plan': 'trader',
        }).json()
        assert r['status'] == 'ok'
        plan = UserPlan.objects.filter(user=self.user, type=UserPlan.TYPE.trader).order_by('-id').first()
        assert plan.is_active
        assert plan.date_from
        assert now() - plan.date_from < datetime.timedelta(seconds=10)
        assert plan.date_to is None
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.trader
        # Deactivate
        r = self.client.post('/users/plans/deactivate', data={
            'plan': 'trader',
        }).json()
        assert r['status'] == 'ok'
        plan.refresh_from_db()
        assert plan.user == self.user
        assert plan.type == UserPlan.TYPE.trader
        assert not plan.is_active
        assert plan.date_from
        assert plan.date_to
        assert now() - plan.date_to < datetime.timedelta(seconds=10)
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level2
        # Another cycle
        r = self.client.post('/users/plans/activate', data={'plan': 'trader'}).json()
        assert r['status'] == 'ok'
        r = self.client.post('/users/plans/activate', data={'plan': 'trader'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'PlanAlreadyActivated'
        r = self.client.post('/users/plans/deactivate', data={'plan': 'trader'}).json()
        assert r['status'] == 'ok'
        # Check monthly limit
        r = self.client.post('/users/plans/activate', data={'plan': 'trader'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'NotEligibleToActivatePlan'
        # Check no active plan
        r = self.client.post('/users/plans/deactivate', data={'plan': 'trader'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'NoSuchActivePlan'
