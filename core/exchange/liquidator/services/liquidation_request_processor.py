from decimal import ROUND_DOWN
from typing import Iterable, List

from django.db import transaction
from django.db.models import Prefetch

from exchange.accounts.models import Notification
from exchange.base.constants import MAX_PRECISION
from exchange.base.money import money_is_zero
from exchange.liquidator.constants import FEE_RATE
from exchange.liquidator.errors import IncompatibleAmountAndPriceError, LiquidationRequestTransactionCommitError
from exchange.liquidator.functions import check_double_spend_in_liquidation, check_double_spend_in_liquidation_request
from exchange.liquidator.models import Liquidation, LiquidationRequest, LiquidationRequestLiquidationAssociation
from exchange.wallet.models import Transaction, Wallet


class LiquidationRequestProcessor:
    """
    Processes in-progress liquidation requests based on ready_to_share liquidations.

    This class handles the following tasks:

    - Retrieving ready_to_share liquidations with their associated liquidation requests.
    - Retrieving in-progress liquidation requests.
    - Updating in-progress requests by distributing assets from ready_to_share liquidations.
    - Updating the status of ready_to_share liquidations and related liquidation requests.
    - Submitting transactions on requester wallets for external liquidations
    """

    def _get_ready_to_share_liquidations_with_requests(self) -> Iterable[Liquidation]:
        """
        Retrieves ready_to_share liquidations with prefetched liquidation requests.
        These liquidations and liquidations requests are locked for update (select_for_update).

        Returns:
            Iterable[Liquidation]: The ready_to_share liquidations.
        """
        prefetch_object = Prefetch(
            'liquidation_request_associations',
            LiquidationRequestLiquidationAssociation.objects.select_related('liquidation_request')
            .order_by('liquidation_request_id')
            .select_for_update(),
        )
        return (
            Liquidation.objects.filter(status=Liquidation.STATUS.ready_to_share)
            .prefetch_related(prefetch_object)
            .select_for_update()
            .order_by('id')
        )

    @transaction.atomic
    def update_in_progress_liquidation_request(self):
        """
        Updates in-progress liquidation requests based on ready_to_share liquidations.

        This method performs the following steps within an atomic transaction:
        1. Retrieves ready_to_share liquidations with their associated requests.
        2. Retrieves in-progress liquidation requests.
        3. Distributes assets from ready_to_share liquidations to in-progress requests.
        4. Updates the status and fields of in-progress requests based on liquidations.
        5. Updates the status of ready_to_share liquidations to "done".
        """
        liquidations = self._get_ready_to_share_liquidations_with_requests()
        associations, liquidation_requests = self._share_asset_of_liquidations(liquidations)
        self._update_liquidations(liquidations)
        self._update_associations(associations)
        self._update_liquidation_requests(liquidation_requests)

    def _share_asset_of_liquidations(
        self,
        liquidations: Iterable[Liquidation],
    ):
        """
        Shares assets from ready_to_share liquidations to associated in-progress requests.
        """
        updated_associations = []
        liquidation_requests_mapper = {}
        bypassed_liquidations = []

        for liquidation in liquidations:
            if not liquidation.unshared_amount:
                bypassed_liquidations.append(liquidation)
                continue

            for request_association in liquidation.liquidation_request_associations.all():
                updated_associations.append(request_association)

                liquidation_request = liquidation_requests_mapper.get(request_association.liquidation_request_id)
                if not liquidation_request:
                    liquidation_request = request_association.liquidation_request
                    liquidation_requests_mapper[liquidation_request.pk] = liquidation_request

                # change logic in multiple liquidation request
                amount = liquidation.unshared_amount
                total_price = (
                    (amount * liquidation.price).quantize(MAX_PRECISION, ROUND_DOWN)
                    if liquidation.unshared_amount != amount
                    else liquidation.unshared_total_price
                )

                liquidation_request.filled_amount += amount
                liquidation_request.filled_total_price += total_price
                liquidation_request.fee += (total_price * FEE_RATE).quantize(MAX_PRECISION, ROUND_DOWN)

                liquidation.paid_amount += amount
                liquidation.paid_total_price += total_price

                request_association.amount += amount
                request_association.total_price += total_price

                if liquidation.unshared_amount == 0:
                    break

        for liquidation in bypassed_liquidations:
            for association in liquidation.liquidation_request_associations.all():
                if association.liquidation_request_id not in liquidation_requests_mapper:
                    liquidation_requests_mapper[association.liquidation_request_id] = association.liquidation_request

        return updated_associations, list(liquidation_requests_mapper.values())

    def _update_liquidations(self, liquidations: Iterable[Liquidation]):
        external_liquidations = []
        for liquidation in liquidations:
            if liquidation.filled_amount != liquidation.paid_amount:
                check_double_spend_in_liquidation(liquidation)
            liquidation.status = Liquidation.STATUS.done
            if liquidation.market_type == liquidation.MARKET_TYPES.external:
                external_liquidations.append(liquidation)

        self._apply_wallet_transactions_for_external_liquidations(external_liquidations)
        Liquidation.objects.bulk_update(liquidations, fields=('status', 'paid_amount', 'paid_total_price'))

    def _apply_wallet_transactions_for_external_liquidations(self, liquidations: Iterable[Liquidation]):
        marketmaker_user = Liquidation.get_marketmaker_user()
        marketmaker_wallets = self._get_all_user_wallets_dict(marketmaker_user)

        for liquidation in liquidations:
            marketmaker_src_wallet = self._get_from_wallets_dict_or_add(
                marketmaker_wallets, liquidation.src_currency, marketmaker_user
            )
            marketmaker_dst_wallet = self._get_from_wallets_dict_or_add(
                marketmaker_wallets, liquidation.dst_currency, marketmaker_user
            )

            if liquidation.side == Liquidation.SIDES.buy:
                # position was sell (short) - marketmaker bought crypto for pool
                filled_amount = -liquidation.filled_amount
                total_price = liquidation.filled_total_price
            else:
                # position was buy (long) - marketmaker sold crypto to give fiat to pool
                filled_amount = liquidation.filled_amount
                total_price = -liquidation.filled_total_price

            trx_values = [filled_amount, total_price]
            if any(trx_values):
                if not all(trx_values):
                    raise IncompatibleAmountAndPriceError(trx_values)
            else:
                continue

            trx1 = marketmaker_src_wallet.create_transaction(
                'external_liquidation',
                amount=filled_amount,
                allow_negative_balance=True,
                ref_module=Transaction.REF_MODULES['LiquidationSrc'],
                ref_id=liquidation.pk,
                description=f'External liquidation #{liquidation.pk} for marketmaker #{marketmaker_user.pk} trx',
            )
            trx2 = marketmaker_dst_wallet.create_transaction(
                'external_liquidation',
                amount=total_price,
                allow_negative_balance=True,
                ref_module=Transaction.REF_MODULES['LiquidationDst'],
                ref_id=liquidation.pk,
                description=f'External liquidation #{liquidation.pk} for marketmaker #{marketmaker_user.pk} trx',
            )
            trx1.commit(allow_negative_balance=True)
            trx2.commit(allow_negative_balance=True)

    @staticmethod
    def _get_all_user_wallets_dict(user):
        wallets = Wallet.get_user_wallets(user, tp=Wallet.WALLET_TYPE.spot)
        return {wallet.currency: wallet for wallet in wallets}

    @staticmethod
    def _get_from_wallets_dict_or_add(wallets_dict, currency, user):
        if currency in wallets_dict:
            return wallets_dict[currency]

        wallet = Wallet.get_user_wallet(user, currency)

        wallets_dict[currency] = wallet
        return wallet

    def _update_associations(self, associations: Iterable[LiquidationRequestLiquidationAssociation]):
        LiquidationRequestLiquidationAssociation.objects.bulk_update(associations, fields=('amount', 'total_price'))

    def _update_liquidation_requests(self, liquidation_requests: List[LiquidationRequest]):
        """
        Updates the status and fields of liquidation requests and validates that the filled amount doesn't exceed the
        total amount.

        Args:
            liquidation_requests (Set[LiquidationRequest]): A set of liquidation requests to update.

        """
        pending_requests = []
        for liquidation_request in liquidation_requests:
            if liquidation_request.amount < liquidation_request.filled_amount:
                check_double_spend_in_liquidation_request(liquidation_request)
            if money_is_zero(liquidation_request.unfilled_amount):
                liquidation_request.status = LiquidationRequest.STATUS.waiting_for_transactions
            else:
                pending_requests.append(liquidation_request.pk)

        LiquidationRequest.objects.bulk_update(
            liquidation_requests,
            fields=('filled_amount', 'filled_total_price', 'fee', 'status'),
        )
        LiquidationRequest.objects.filter(id__in=pending_requests).exclude(
            liquidations__status__in=Liquidation.ACTIVE_STATUSES,
        ).update(
            status=LiquidationRequest.STATUS.pending,
        )

    @transaction.atomic
    def submit_wallet_transactions_for_external_liquidations(self, *, is_retry=False):
        status = LiquidationRequest.STATUS.waiting_for_transactions
        if is_retry:
            status = LiquidationRequest.STATUS.transactions_failed

        liquidation_requests = (
            LiquidationRequest.objects.filter(
                status=status,
            )
            .prefetch_related('liquidation_associations__liquidation')
            .select_related('src_wallet', 'dst_wallet')
            .select_for_update(skip_locked=True, of=('self',))
        )

        updated_records = []
        for liquidation_request in liquidation_requests:
            try:
                liquidation_request.commit_wallet_transactions_for_external_liquidations()
            except LiquidationRequestTransactionCommitError as e:
                liquidation_request.status = LiquidationRequest.STATUS.transactions_failed

                message = f'Cannot commit liquidation request transactions: #{liquidation_request.pk}\n Reason: {e}'
                if is_retry:
                    message = (
                        f'Retry failed for liquidation request transactions: #{liquidation_request.pk}\n Reason: {e}'
                    )
                Notification.notify_admins(
                    message,
                    title=f'‼️LiquidationRequest - {liquidation_request.market_symbol}',
                    channel='liquidator',
                )

                if not is_retry:
                    updated_records.append(liquidation_request)
            else:
                liquidation_request.status = LiquidationRequest.STATUS.done
                updated_records.append(liquidation_request)

        LiquidationRequest.objects.bulk_update(updated_records, fields=('status',), batch_size=1024)
