from dataclasses import dataclass, field

from django.db.models import QuerySet

from exchange.accounts.models import User
from exchange.socialtrade.models import Leader


@dataclass
class LeaderProfileData:
    leader_profile: QuerySet = field(default=None)
    private: bool = field(default=False)


class LeaderProfiles:
    def get_leader_profile(self, leader: Leader, user_requested: User):
        if leader.user_id == user_requested.id:
            return self._get_private_profile(leader)
        return self._get_public_profile(leader, user_requested)

    def _get_public_profile(self, leader: Leader, user_requested: User):
        leader = (
            Leader.objects.filter(pk=leader.id)
            .annotate_number_of_subscribers()
            .annotate_is_subscribed(user_requested)
            .annotate_is_trial_available(user_requested)
        )
        return LeaderProfileData(leader_profile=leader, private=False)

    def _get_private_profile(self, leader: Leader):
        leader = (
            Leader.objects.filter(pk=leader.id)
            .annotate_number_of_subscribers()
            .annotate_number_of_unsubscribes()
        )
        return LeaderProfileData(leader_profile=leader, private=True)
