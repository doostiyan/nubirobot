""" Referral Program Logic

    See: https://nobitex.ir/policies/referral/
"""

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Min, Max, Q
from django.utils.timezone import now

from exchange.base.logging import report_event
from exchange.base.models import RIAL
from exchange.market.models import ReferralFee
from exchange.wallet.models import Wallet, Transaction


def calculate_referral_fees():
    """ Calculate referral total amounts for all eligible users, charge
         their wallets, and mark processed ReferralFee objects as calculated.
    """
    nw = now()

    # Get pending fees
    query = ReferralFee.objects.filter(
        is_calculated=False,
        created_at__gt=nw - datetime.timedelta(days=10),
    ).values('user_id').annotate(
        total_amount=Sum('amount'),
        first_date=Min('created_at'),
        first_id=Min('id'),
        last_id=Max('id'),
    ).filter(
        Q(total_amount__gte=Decimal('10_000_0')) |
        Q(first_date__lt=nw - datetime.timedelta(days=7))
    )
    total_paid_referral = Decimal('0')
    for dic in query:
        with transaction.atomic():
            user_id = dic['user_id']
            amount = int(dic['total_amount'])

            # Create Charge Transaction
            if amount > 0:
                tr_dst = Wallet.get_user_wallet(user_id, RIAL).create_transaction(
                    'referral',
                    amount,
                    description=f'Charge for Referral Fee: {amount}',
                )
                if not tr_dst:
                    continue
                # TODO: Using ReferralFee IDs for transfers may collide with future uses of transfer
                tr_dst.commit(ref=Transaction.Ref('TransferDst', dic['first_id']))

            # Mark referral fees as calculated
            total_paid_referral += amount
            ReferralFee.objects.filter(
                user_id=user_id,
                is_calculated=False,
                id__gte=dic['first_id'],  # Just to be explicit
                id__lte=dic['last_id'],   # Maybe the user has new ReferralFees after our initial query
            ).update(is_calculated=True)

    # Create transaction for source system wallet
    with transaction.atomic():
        system_fee_wallet = Wallet.get_fee_collector_wallet(RIAL)
        fee_transaction = system_fee_wallet.create_transaction(
            tp='referral',
            amount=-total_paid_referral,
            description='Referral aggregated payments at {}'.format(nw.strftime('%Y-%m-%d/%H')),
        )
        if not fee_transaction:
            report_event('FeeWalletBalanceError', extras={'src': 'ReferralFeeCalculationCron'})  # unlikely event
        fee_transaction.commit()
