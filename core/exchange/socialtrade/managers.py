
from django.db.models import Count, DecimalField, Exists, IntegerField, Manager, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.market.models import UserTradeStatus


class LeaderQuerySet(QuerySet):
    def annotate_number_of_subscribers(self):
        from exchange.socialtrade.models import SocialTradeSubscription

        active_subscriptions = (
            SocialTradeSubscription.get_actives()
            .filter(leader=OuterRef('pk'))
            .values('leader_id')
            .annotate(count=Count(1))
            .values('count')
        )
        return self.annotate(
            number_of_subscribers=Coalesce(Subquery(active_subscriptions), 0, output_field=IntegerField())
        )

    def annotate_number_of_unsubscribes(self):
        """
        -The users who unfollowed the leader are the ones who either canceled their subscriptions or did not renew them,
        except those who currently follow the leader.
        E.g. If someone canceled their subscription a month ago but then followed the leader again and has an active
        subscription now, they have not unfollowed the leader.

        -Also, having multiple canceled or ended subscriptions should only be counted as 1 unsubscription.
        E.g. If a user has 3 finished and 2 canceled subscriptions of leader1, then that only adds 1 to the leader1's
        unsubscription count
        """
        from exchange.socialtrade.models import SocialTradeSubscription

        canceled_condition = Q(leader=OuterRef('pk'), canceled_at__isnull=False)
        finished_condition = Q(leader=OuterRef('pk'), canceled_at__isnull=True, expires_at__lt=ir_now())
        discontinued_subscriptions = (
            SocialTradeSubscription.objects.filter(canceled_condition | finished_condition)
            .exclude(
                subscriber__in=Subquery(
                    SocialTradeSubscription.get_actives().filter(leader=OuterRef('leader_id')).values_list('subscriber')
                )
            )
            .values('leader_id')
            .annotate(count=Count('subscriber', distinct=True))
            .values('count')
        )
        return self.annotate(
            number_of_unsubscribes=Coalesce(Subquery(discontinued_subscriptions, output_field=IntegerField()), 0)
        )

    def annotate_is_trial_available(self, user):
        from exchange.socialtrade.models import SocialTradeSubscription

        previous_trial = SocialTradeSubscription.objects.filter(
            leader=OuterRef('pk'),
            subscriber=user,
            is_trial=True,
        ).values('pk')

        return self.annotate(is_trial_available=~Exists(previous_trial))

    def annotate_is_subscribed(self, user):
        from exchange.socialtrade.models import SocialTradeSubscription

        is_subscribed = (
            SocialTradeSubscription.get_actives()
            .filter(
                leader=OuterRef('pk'),
                subscriber=user,
            )
            .values('pk')
        )

        return self.annotate(is_subscribed=Exists(is_subscribed))

    def annotate_last_month_trade_volume(self):
        last_month_trade_volume = UserTradeStatus.objects.filter(user=OuterRef('user_id')).values('month_trades_total')
        return self.annotate(
            last_month_trade_volume=Coalesce(Subquery(last_month_trade_volume), ZERO, output_field=DecimalField())
        )


class LeaderManager(Manager):
    def get_queryset(self):
        return LeaderQuerySet(self.model, using=self._db).defer('daily_profits')
