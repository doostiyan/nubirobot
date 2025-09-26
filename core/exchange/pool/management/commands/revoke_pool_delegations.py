import math

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from tqdm import tqdm

from exchange.accounts.models import User
from exchange.base.constants import ZERO
from exchange.base.helpers import batcher
from exchange.base.models import Currencies
from exchange.pool.models import DelegationRevokeRequest, LiquidityPool, UserDelegation


class Command(BaseCommand):
    """Examples
    python manage.py revoke_pool_delegations -c ftm
    """

    help = 'Revoke all delegations for specific pool.'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--currency', type=str, help='Pool currency')
        parser.add_argument('--batch-size', type=int, default=1_000)

    def handle(self, currency: str, batch_size: int, **options):
        try:
            currency_code = getattr(Currencies, currency.lower())
        except AttributeError:
            raise CommandError(f"Invalid currency '{currency}'.")

        pool = LiquidityPool.objects.get(currency=currency_code)

        delegation_revoke_total = (
            DelegationRevokeRequest.objects.filter(
                user_delegation=OuterRef('id'), status=DelegationRevokeRequest.STATUS.new
            )
            .values("user_delegation")
            .annotate(total=Sum("amount"))
            .values("total")
        )

        user_delegations = (
            UserDelegation.objects.filter(
                pool=pool,
                closed_at=None,
            )
            .exclude(user=User.get_nobitex_delegator())
            .alias(
                revoke_total=Coalesce(
                    Subquery(
                        delegation_revoke_total[:1],
                        output_field=DecimalField(),
                    ),
                    ZERO,
                ),
            )
            .annotate(amount=F("balance") - F("revoke_total"))
            .values("id", "amount")
        )

        new_revoke_requests = [
            DelegationRevokeRequest(user_delegation_id=delegation["id"], amount=delegation["amount"])
            for delegation in user_delegations
            if delegation["amount"]
        ]

        print(f"Total DelegationRevokeRequests to create: {len(new_revoke_requests)}")
        for revoke_request_slice in tqdm(
            batcher(new_revoke_requests, batch_size),
            total=math.ceil(len(new_revoke_requests) / batch_size),
            unit_scale=batch_size,
        ):
            with transaction.atomic():
                revoke_requests = DelegationRevokeRequest.objects.bulk_create(revoke_request_slice)
                total_revoked_amount = ZERO
                for revoke_request in revoke_requests:
                    total_revoked_amount += revoke_request.amount
                pool.revoked_capacity += total_revoked_amount
                pool.save()

                for revoke_request in revoke_requests:
                    revoke_request.notify_on_new()
