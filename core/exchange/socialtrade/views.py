import json
from decimal import Decimal
from enum import Enum

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.accounts.models import User
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import APIView, NobitexAPIError, PublicAPIView, SemanticAPIError
from exchange.base.constants import ZERO
from exchange.base.helpers import paginate
from exchange.base.models import AMOUNT_PRECISIONS, Settings, get_currency_codename
from exchange.base.parsers import (
    parse_bool,
    parse_choices,
    parse_currency,
    parse_int,
    parse_money,
    parse_str,
    parse_strict_decimal,
)
from exchange.features.utils import FeatureEnabled
from exchange.margin.models import Position
from exchange.socialtrade.exceptions import (
    AlreadySubscribedException,
    InsufficientBalance,
    LeaderAlreadyExist,
    LeaderNotFound,
    PendingLeadershipRequestExist,
    ReachedSubscriptionLimit,
    SelfSubscriptionImpossible,
    SubscriptionFeeIsLessThanTheMinimum,
    SubscriptionFeeIsMoreThanTheMaximum,
    SubscriptionIsNotAllowed,
)
from exchange.socialtrade.funsctions import get_leaders_orders, get_leaders_positions
from exchange.socialtrade.leaders.profile import LeaderProfiles
from exchange.socialtrade.leaders.trades import LeaderTrades
from exchange.socialtrade.models import (
    Leader,
    LeadershipBlacklist,
    LeadershipRequest,
    SocialTradeAvatar,
    SocialTradeSubscription,
)
from exchange.socialtrade.serializers import serialize_orders, serialize_positions
from exchange.socialtrade.validators import FEE_BOUNDARY_KEY, is_nickname_valid, validate_subscription_fee


class OptionsView(APIView):
    """Social Trade Options
    GET /social-trade/options
    """

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request):
        leader = Leader.objects.filter(user=self.request.user).only('id').first()

        return self.response(
            {
                'status': 'ok',
                'leaderId': leader.id if leader else None,
                'feeBoundary': Settings.get_json_object(
                    FEE_BOUNDARY_KEY,
                    json.dumps(settings.SOCIAL_TRADE['default_fee_boundary']),
                ),
                'minNicknameLength': settings.SOCIAL_TRADE['minNicknameLength'],
                'maxNicknameLength': settings.SOCIAL_TRADE['maxNicknameLength'],
            },
        )


class SocialTradeAvatarListView(PublicAPIView):
    @method_decorator(ratelimit(key='ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        return self.response(
            {
                'status': 'ok',
                'avatars': SocialTradeAvatar.objects.filter(is_active=True).order_by('-id').all(),
            },
        )


def leadership_request_ratelimit(group, request):
    """ Ratelimit checker for leadership request POST and GET APIs. Used for increasing ratelimit for testnet.
    """
    return '5/h' if settings.IS_PROD else '30/h'


class LeadershipRequestView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='GET', block=True))
    def get(self, request):
        user = request.user
        latest_requests = LeadershipRequest.objects.filter(user=user).order_by('-created_at')
        return self.response({
            'status': 'ok',
            'data': latest_requests,
        })

    @method_decorator(ratelimit(key='user_or_ip', rate=leadership_request_ratelimit, method='POST', block=True))
    def post(self, request):
        user = request.user
        nickname = parse_str(self.g('nickname'), required=True)
        avatar_id = parse_int(self.g('avatarId'), required=True)
        subscription_currency = parse_currency(self.g('subscriptionCurrency'), required=True)
        subscription_fee = parse_strict_decimal(
            self.g('subscriptionFee'),
            AMOUNT_PRECISIONS.get(get_currency_codename(subscription_currency).upper() + 'IRT', Decimal(1)),
            required=True,
        )
        if subscription_fee != ZERO:
            subscription_fee = parse_money(subscription_fee, required=True)

        self._validate_request_inputs(user, nickname, subscription_currency, subscription_fee)

        avatar = SocialTradeAvatar.objects.filter(pk=avatar_id).first()
        if not avatar:
            return get_404_json_response_object(object_type='SocialTradeAvatar')

        leadership_request = LeadershipRequest.objects.create(
            user=user, nickname=nickname, subscription_currency=subscription_currency,
            subscription_fee=subscription_fee, avatar=avatar
        )
        return self.response({
            'status': 'ok',
            'data': leadership_request,
        })

    def _validate_request_inputs(self, user, nickname, subscription_currency, subscription_fee):
        self._validate_user(user)
        self._validate_nickname(user, nickname)
        self._validate_subscription_fee(subscription_fee, subscription_currency)

    @staticmethod
    def _validate_user(user: User):
        if LeadershipBlacklist.is_user_blacklisted(user):
            raise SemanticAPIError(message='UserBlacklisted', description='User is blacklisted.')

        try:
            LeadershipRequest.can_request_to_become_leader(user)
        except PendingLeadershipRequestExist:
            raise SemanticAPIError(
                message='PendingLeadershipRequestExist',
                description='A pending leadership request exists.',
            )
        except LeaderAlreadyExist:
            raise SemanticAPIError(
                message='LeaderAlreadyExist',
                description='Leader already exists.',
            )
        if not UserLevelManager.is_eligible_for_social_trading_leadership(user):
            raise SemanticAPIError(
                message='IneligibleUser',
                description='User is ineligible due to unverified email or level.',
            )

    @staticmethod
    def _validate_nickname(user: User, nickname: str):
        if not is_nickname_valid(nickname):
            max_length = settings.SOCIAL_TRADE['maxNicknameLength']
            min_length = settings.SOCIAL_TRADE['minNicknameLength']
            raise SemanticAPIError(
                message='InvalidNickname',
                description=(
                    f'Nickname should contain at least {min_length} and at most '
                    f'{max_length} English letters and numbers.'
                ),
            )
        if not LeadershipRequest.is_nickname_unique(user, nickname):
            raise SemanticAPIError(message='NicknameExists', description='Nickname is already picked by another user.')

    @staticmethod
    def _validate_subscription_fee(subscription_fee: Decimal, subscription_currency: int):
        try:
            validate_subscription_fee(subscription_currency, subscription_fee)
        except SubscriptionFeeIsMoreThanTheMaximum as ex:
            raise SemanticAPIError(
                message='SubscriptionFeeIsHigh',
                description='Subscription fee is very high.',
            ) from ex

        except SubscriptionFeeIsLessThanTheMinimum as ex:
            raise SemanticAPIError(message='SubscriptionFeeIsLow', description='Subscription fee is very low.') from ex
        except SubscriptionIsNotAllowed as ex:
            raise SemanticAPIError(
                message='InvalidSubscriptionCurrency',
                description='Cannot choose this currency as the subscription fee currency.',
            ) from ex


class SubscriptionView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True))
    def post(self, request):
        leader_id = parse_int(self.g('leaderId'), required=True)
        is_auto_renewal_enabled = parse_bool(self.g('isAutoRenewalEnabled'), required=True)
        leader = Leader.get_actives().filter(pk=leader_id).first()
        user = request.user

        try:
            subscription = SocialTradeSubscription.subscribe(
                leader, user, is_auto_renewal_enabled=is_auto_renewal_enabled
            )
        except SelfSubscriptionImpossible as ex:
            raise SemanticAPIError('SelfSubscriptionImpossible', 'Subscribing oneself is not possible') from ex
        except AlreadySubscribedException as ex:
            raise SemanticAPIError('AlreadySubscribed', 'Already subscribed to this leader') from ex
        except LeaderNotFound as ex:
            raise SemanticAPIError('LeaderNotFound', 'Leader not found') from ex
        except InsufficientBalance as ex:
            raise SemanticAPIError('InsufficientBalance', 'Wallet balance is not enough') from ex
        except ReachedSubscriptionLimit as ex:
            raise SemanticAPIError('ReachedSubscriptionLimit', 'Reached total subscription limit') from ex

        return self.response(dict(status='ok', subscription=subscription))

    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='POST', block=True))
    def get(self, request):
        user = request.user

        subscriptions = (
            SocialTradeSubscription.get_actives()
            .filter(subscriber=user)
            .order_by('-created_at')
            .select_related('leader')
        )

        return self.response(
            {
                'status': 'ok',
                'subscriptions': subscriptions,
            },
        )


class LeadersPositionsView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request):
        side = parse_choices(Position.SIDES, self.g('side'))
        is_closed = parse_bool(self.g('isClosed'))
        leader_id = parse_int(self.g('leaderId'))
        user = request.user

        try:
            positions, leaders = get_leaders_positions(user, leader_id, side, is_closed, include_closed=False)
        except ObjectDoesNotExist:
            return get_404_json_response_object(object_type='Leader')

        positions, position_has_next = paginate(
            positions,
            request=self,
            check_next=True,
            max_page=100,
            max_page_size=100,
        )
        return self.response(
            {
                'status': 'ok',
                'positions': serialize_positions(positions, leaders),
                'hasNext': position_has_next,
            },
        )


class LeaderOrdersView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request, leader_id):
        side = parse_choices(Position.SIDES, self.g('side'))
        user = request.user

        try:
            orders = get_leaders_orders(user, leader_id, side)
        except ObjectDoesNotExist:
            return get_404_json_response_object(object_type='Leader')

        orders, orders_has_next = paginate(orders, request=self, check_next=True, max_page=100, max_page_size=100)
        return self.response(
            {
                'status': 'ok',
                'orders': serialize_orders(orders),
                'hasNext': orders_has_next,
            },
        )


class LeaderboardView(APIView):
    permission_classes = []

    class LeaderboardSortEnum(Enum):
        mostSubscriber = '-number_of_subscribers'
        leastSubscriber = 'number_of_subscribers'
        mostProfit = '-last_month_profit_percentage'
        leastProfit = 'last_month_profit_percentage'
        newest = '-created_at'
        mostVolume = '-last_month_trade_volume'

    def get_public_queryset(self):
        return Leader.get_actives().filter(deleted_at__isnull=True)

    def get_private_queryset(self):
        only_subscribed = parse_bool(self.g('onlySubscribed'), required=False)
        leaders_queryset = Leader.get_actives_for_user(self.request.user)
        queryset = leaders_queryset.filter(is_subscribed=True) if only_subscribed else leaders_queryset.all()
        return (
            queryset.annotate_is_trial_available(self.request.user)
            .annotate_is_subscribed(self.request.user)
            .filter(Q(deleted_at__isnull=True) | Q(is_subscribed=True))
            .exclude(user=self.request.user)
        )

    def get_queryset(self):
        is_public_request = self.request.user.is_anonymous
        queryset = self.get_public_queryset() if is_public_request else self.get_private_queryset()
        return queryset.select_related('avatar').annotate_number_of_subscribers().annotate_last_month_trade_volume()

    def get_sorted_queryset(self, queryset):
        order_by = parse_choices(self.LeaderboardSortEnum, self.g('order'), required=False)
        order_by = self.LeaderboardSortEnum.newest if order_by is None else order_by
        return queryset.order_by(order_by.value)

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request):
        queryset = self.get_queryset()
        sorted_queryset = self.get_sorted_queryset(queryset)
        paged_data, has_next = paginate(sorted_queryset, request=self, check_next=True, max_page=100, max_page_size=100)
        return self.response({'status': 'ok', 'data': paged_data, 'hasNext': has_next})


class UnsubscribeView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='POST', block=True))
    def post(self, request, subscription_id):
        user = request.user
        try:
            subscription = SocialTradeSubscription.get_actives().get(id=subscription_id, subscriber=user)
        except ObjectDoesNotExist:
            return get_404_json_response_object()

        subscription.unsubscribe()
        return self.response({'status': 'ok'})


class UserDashboardView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request):
        user = request.user
        number_of_recent_trades = parse_int(self.g('tradesNumber', 10), required=True)
        number_of_recent_trades = min(number_of_recent_trades, 20)

        subscribed_leaders = (
            Leader.get_actives_for_user(self.request.user)
            .filter(is_subscribed=True)
            .order_by('activates_at')
            .select_related('user')
        )

        subscriptions = (
            SocialTradeSubscription.get_actives()
            .filter(subscriber=user)
            .order_by('-created_at')
            .select_related('leader')
        )

        delay = settings.SOCIAL_TRADE['delayWhenSubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenSubscribed']
        leaders_trades = LeaderTrades([leader.user for leader in subscribed_leaders], delay, duration)
        recent_trades = leaders_trades.get_recent_trades(number_of_recent_trades, include_closed=False)

        return self.response(
            {
                'status': 'ok',
                'data': {
                    'subscriptions': subscriptions,
                    'recentTrades': recent_trades,
                },
            }
        )


class ChangeAutoRenewalView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='POST', block=True))
    def post(self, request, subscription_id):
        is_auto_renewal_enabled = parse_bool(self.g('isAutoRenewalEnabled'), required=True)
        try:
            subscription = SocialTradeSubscription.get_actives().get(id=subscription_id, subscriber=request.user)
        except ObjectDoesNotExist:
            return get_404_json_response_object()

        if is_auto_renewal_enabled and not subscription.is_renewable:
            return JsonResponse(
                {'status': 'failed', 'code': 'IsNotRenewable', 'message': 'Subscription is not renewable'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        subscription.change_auto_renewal(is_auto_renewal_enabled)
        return self.response({'status': 'ok'})


class ChangeSendNotifView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='POST', block=True))
    def post(self, request, subscription_id):
        is_notif_enabled = parse_bool(self.g('isNotifEnabled'), required=True)

        try:
            subscription = SocialTradeSubscription.get_actives().get(id=subscription_id, subscriber=request.user)
        except ObjectDoesNotExist:
            return get_404_json_response_object()

        subscription.change_is_notif_enabled(is_notif_enabled)
        return self.response({'status': 'ok'})


def get_404_json_response_object(object_type='Subscription'):
    return JsonResponse(
        {'status': 'failed', 'code': 'NotFound', 'message': f'{object_type} does not exist'},
        status=status.HTTP_404_NOT_FOUND,
    )


def get_feature_flag_disabled_response_object(feature_flag):
    return JsonResponse(
        {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': f'{feature_flag}  feature is not available for your user',
        },
        status=status.HTTP_200_OK,
    )


class LeaderProfileView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request, leader_id):
        user = request.user
        try:
            leader = Leader.get_actives_for_user(user).get(pk=leader_id)
        except ObjectDoesNotExist:
            return get_404_json_response_object(object_type='Leader')
        leader_profile = LeaderProfiles().get_leader_profile(leader, user)
        leader = leader_profile.leader_profile.first()
        return self.response(
            {'status': 'ok', 'data': {'leader': leader}},
            opts={
                'private': leader_profile.private,
                'profile_serialization': True,
            },
        )
