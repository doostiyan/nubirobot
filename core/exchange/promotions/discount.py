import datetime
import json
import math
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple, Type

import pytz
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from exchange.accounts.models import User, UserRestriction
from exchange.base.api import ParseError
from exchange.base.calendar import ir_today
from exchange.base.logging import report_event, report_exception
from exchange.base.models import RIAL, TETHER
from exchange.base.parsers import parse_uuid
from exchange.base.settings import NobitexSettings
from exchange.market.models import Order, OrderMatching
from exchange.promotions.exceptions import (
    ActiveUserDiscountExist,
    CreateNewUserDiscountBudgetLimit,
    DiscountDoesNotExist,
    DiscountTransactionLogDoesNotExist,
    NotActiveDiscount,
    UserDiscountDoesNotExist,
    UserRestrictionError,
)
from exchange.promotions.models import (
    Discount,
    DiscountTransactionLog,
    UserDiscount,
    UserDiscountBatch,
    default_trade_types,
)
from exchange.wallet.models import Transaction, Wallet

RESTRICTIONS = [UserRestriction.RESTRICTION.Trading, UserRestriction.RESTRICTION.WithdrawRequestRial]
BATCH_SIZE = 1000


def get_user_discount_batch_file_information(we_ids: List[str], activation_date: datetime.date,
                                             end_date: datetime.date) -> Tuple[Dict, Dict]:
    """
        This function reads user_discount_batch file and make users dict
        errors of this file, write in details dict
    """
    details = {}
    uuids = set()

    for user_web_id in we_ids:
        user_web_id = user_web_id.strip()
        if user_web_id:
            try:
                parse_uuid(user_web_id)
                uuids.add(user_web_id)
            except ParseError:
                details[user_web_id] = 'invalid_uuid_error'
    uuids = list(uuids)
    users_web_id = set()
    users = {}

    query_filter_user_discount_date = Q(activation_date__lte=end_date, end_date__gte=activation_date)

    number_of_batch = math.ceil(len(uuids) / BATCH_SIZE)
    for i in range(number_of_batch):
        batch_uuids = uuids[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
        users_data = User.objects.filter(webengage_cuid__in=batch_uuids).values('id', 'webengage_cuid').annotate(
            restricted=Exists(UserRestriction.objects.filter(user_id=OuterRef('id'), restriction__in=RESTRICTIONS)),
            discounted=Exists(
                UserDiscount.objects.filter(user_id=OuterRef('id'), discount__status=Discount.STATUS.active).filter(
                    query_filter_user_discount_date)), )
        for user_data in users_data:
            web_id_str = str(user_data['webengage_cuid'])
            if user_data['restricted']:
                details[web_id_str] = 'user_restriction_error'
            elif user_data['discounted']:
                details[web_id_str] = 'active_discount_exist_error'
            else:
                users[user_data['id']] = web_id_str

            users_web_id.add(web_id_str)

    # check webengage ids exist in Database
    for u_id in uuids:
        if u_id not in users_web_id:
            details[u_id] = 'webengage_id_error'

    return users, details


def create_user_discount_bulk(user_ids: List[Type[int]], activation_date: datetime.date,
                              end_date: datetime.date, discount_batch_id: int, discount: Discount) -> int:
    """
        This function creates user_discounts and return the number of user_discounts were created
    """
    number_of_user_discounts = min(len(user_ids), int(discount.budget_remain / discount.amount_rls))
    budget_required = discount.amount_rls * number_of_user_discounts
    user_discounts = [UserDiscount(user_id=user_id, discount_id=discount.id, amount_rls=discount.amount_rls,
                                   activation_date=activation_date, end_date=end_date,
                                   discount_batch_id=discount_batch_id)
                      for user_id in user_ids[:number_of_user_discounts]]

    number_of_try = 0
    while number_of_try < 100:
        with transaction.atomic():
            discount = Discount.objects.select_for_update().get(id=discount.id)
            number_of_user_discounts = min(len(user_ids), int(discount.budget_remain / discount.amount_rls))
            budget_required = discount.amount_rls * number_of_user_discounts

            if number_of_user_discounts == 0:
                break

            try:
                discount.budget_remain = F('budget_remain') - budget_required
                discount.save(update_fields=['budget_remain'])
                UserDiscount.objects.bulk_create(user_discounts[:number_of_user_discounts], batch_size=BATCH_SIZE)
                return number_of_user_discounts
            except IntegrityError:
                number_of_try += 1
    return 0


def process_user_discount_batch_file(user_discount_batch: UserDiscountBatch, we_ids: List[str],
                                     activation_date: datetime.date):
    """
        This function creates user_discount from file
    """
    discount = user_discount_batch.discount
    activation_date, end_date = calculate_dates_for_new_user_discount(discount, activation_date)

    users = None
    try:
        users, details = get_user_discount_batch_file_information(we_ids, activation_date, end_date)
    except Exception:
        report_exception()
        details = {'error': 'read_file_error'}

    if users is not None:
        # try to create user_discounts
        user_ids = list(users.keys())
        try:
            number_of_user_discounts = create_user_discount_bulk(user_ids, activation_date, end_date,
                                                                 user_discount_batch.id, discount)
            for user_id in user_ids[number_of_user_discounts:]:
                details[users[user_id]] = 'discount_budget_limit'

        except Exception:
            report_exception()
            for user_id in user_ids:
                details[users[user_id]] = 'unexpected_error'

    user_discount_batch.details = json.dumps(details)
    user_discount_batch.save(update_fields=['details', 'updated_at'])


def get_dictionary_of_active_user_discounts(start_date: datetime.date,
                                            end_date: datetime.datetime) -> Dict[Discount, List[UserDiscount]]:
    """
        This function gets date and find active user discounts after that and returns a dictionary of them
    """
    user_discounts = UserDiscount.objects.filter(discount__status=Discount.STATUS.active, amount_rls__gt=0,
                                                 activation_date__lte=start_date, end_date__gte=start_date) \
        .order_by('-activation_date').select_related('discount').annotate(
        transaction=Exists(DiscountTransactionLog.objects.filter(user_discount_id=OuterRef('id'),
                                                                 created_at=end_date)))
    user_ids = set()
    res = {}
    end_date_for_cancel_user_discount = start_date - datetime.timedelta(days=1)
    for user_discount in user_discounts:
        if not user_discount.transaction:
            # cancel MultipleUserDiscount
            if user_discount.user_id in user_ids:
                report_event('MultipleActiveUserDiscountError', extras={'src': 'GetDictionaryOfActiveUserDiscounts'})
                cancel_user_discount(user_discount, user_discount.discount, end_date_for_cancel_user_discount)
            else:
                user_ids.add(user_discount.user_id)

            # categories user_discount by discount
            if user_discount.discount not in res:
                res[user_discount.discount] = []
            res[user_discount.discount].append(user_discount)

    return res


def calculate_dst_to_rial(is_buy, currency_id, matched_amount, matched_price, rial_value) -> Decimal:
    """
        this function converts currency to rial price
    """
    # RIAL
    if currency_id == RIAL:
        if is_buy:
            return matched_price
        return Decimal('1')

    if rial_value is None:
        return NobitexSettings.get_nobitex_irr_price(currency_id)

    # TETHER
    if currency_id == TETHER:
        if is_buy:
            return rial_value / (matched_amount)
        return rial_value / (matched_amount * matched_price)

    return NobitexSettings.get_nobitex_irr_price(currency_id)


def get_order_matching_amount_per_user(
    user_ids: List[Type[int]],
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    currency: int = None,
    trade_types: List[int] = None,
) -> Dict[int, int]:
    """
        this function calculates OrderMatching Fee for each user on one or all currencies.
        it returns amount of Fees.
    """
    trade_types = trade_types or default_trade_types()

    order_matchings = OrderMatching.objects.filter(
        (
            (Q(seller_id__in=user_ids, sell_order__trade_type__in=trade_types))
            | (Q(buyer_id__in=user_ids, buy_order__trade_type__in=trade_types))
        )
        & Q(created_at__gte=start_date, created_at__lt=end_date)
    )

    if currency is not None:
        order_matchings = order_matchings.select_related('market')
        order_matchings = order_matchings.filter(Q(market__src_currency=currency) | Q(market__dst_currency=currency))

    order_matchings = order_matchings.values_list('buyer_id', 'seller_id', 'buy_fee_amount', 'sell_fee_amount',
                                                  'market__dst_currency', 'rial_value', 'matched_amount',
                                                  'matched_price')
    orders_matching_data = {}

    def add_matching_data(user_id: int, fee: Decimal, dst_to_rial: Decimal):
        if user_id in orders_matching_data:
            orders_matching_data[user_id] += fee * dst_to_rial
        else:
            orders_matching_data[user_id] = fee * dst_to_rial

    for matching in order_matchings:
        buyer, seller, buy_fee, sell_fee, dst_currency, rial_value, matched_amount, matched_price = matching

        if buyer in user_ids:
            add_matching_data(buyer, buy_fee, calculate_dst_to_rial(
                True, dst_currency, matched_amount, matched_price, rial_value))

        if seller in user_ids:
            add_matching_data(seller, sell_fee, calculate_dst_to_rial(
                False, dst_currency, matched_amount, matched_price, rial_value))

    return orders_matching_data


def create_negative_transaction_for_system_fee_wallet(amount: int, discount_id: int) -> None:
    """
        This function try creating a transaction for discount in system-fee wallet
    """
    system_fee_wallet = Wallet.get_fee_collector_wallet(RIAL)
    fee_transaction = system_fee_wallet.create_transaction(
        tp='discount',
        amount=-amount,
        description=f'Discount-{discount_id} aggregated payments at {now().strftime("%Y-%m-%d/%H")}'
    )
    if not fee_transaction:
        report_event('FeeWalletBalanceError', extras={
            'src': 'CalculateUserDiscount'})
    fee_transaction.commit()


def create_transaction_for_user_discount(user_discount: UserDiscount, amount: Decimal) -> None:
    """
        This function try creating a transaction for discount
    """
    with transaction.atomic():
        tr_dst = Wallet.get_user_wallet(user_discount.user, RIAL).create_transaction(
            tp='discount', amount=amount,
            description=(
                f'تخفیف کمپین {user_discount.discount.name} مطابق معاملات شما در 24ساعت گذشته به حساب شما واریز شد.'
            )
        )

        if not tr_dst:
            report_event('CreateTransactionError', extras={'src': 'CreateTransactionForUserDiscount'})
            return

        discount_transaction_log = DiscountTransactionLog.objects.create(user_discount=user_discount, amount=amount)
        tr_dst.commit(ref=Transaction.Ref('DiscountDst', discount_transaction_log.id))
        discount_transaction_log.transaction = tr_dst
        discount_transaction_log.save(update_fields=['transaction'])

        user_discount.amount_rls = F('amount_rls') - amount
        user_discount.save(update_fields=['amount_rls'])
        create_negative_transaction_for_system_fee_wallet(amount, user_discount.discount_id)


def calculate_user_discount(user_discounts: List[UserDiscount],
                            matching_fee_per_user: Dict[int, int], percent: int) -> None:
    """
        This function calculates discount for each active user_discount
    """
    for user_discount in user_discounts:
        if user_discount.user_id in matching_fee_per_user:
            amount = int(min(matching_fee_per_user[user_discount.user_id] * percent * Decimal('0.01'),
                             user_discount.amount_rls))
            if amount > 0:
                create_transaction_for_user_discount(user_discount, amount)


def calculate_discount(
    start_date: datetime.date,
    utc_start_date: datetime.datetime,
    utc_end_date: datetime.datetime,
) -> None:
    """
    this function calculates discount for users with active discount and returns
    amount of active discount to user Rials wallet.
    this function withdraws discount amount from "system-fee" Rials wallet.
    """
    discounts = get_dictionary_of_active_user_discounts(start_date, utc_end_date)

    for discount, user_discounts in discounts.items():
        user_discount_ids = [ud.user_id for ud in user_discounts]
        # get orderMatching fee per user
        matching_fee_per_user = get_order_matching_amount_per_user(
            user_discount_ids, utc_start_date, utc_end_date, discount.currency, discount.trade_types
        )
        # calculate discount
        calculate_user_discount(user_discounts, matching_fee_per_user, discount.percent)


def update_status_finished_discount(end_date: datetime.date) -> None:
    """
        This function checks discount end_date and change discount status if it was finished
    """
    Discount.objects.filter(status=Discount.STATUS.active, end_date__isnull=False, end_date__lte=end_date) \
        .update(status=Discount.STATUS.finished)


def return_remain_amount_in_user_discount(end_date: datetime.date) -> None:
    """
        This function checks user discount amount_rls and returns amount_rls to discount budget_remain
    """
    discount_data = {}
    with transaction.atomic():
        user_discounts = UserDiscount.objects.select_for_update().filter(activation_date__isnull=False,
                                                                         amount_rls__gt=0, end_date__lte=end_date) \
            .exclude(discount__status=Discount.STATUS.disabled) \
            .select_related('discount')
        # calculate remain amount_rls
        for user_discount in user_discounts:
            if user_discount.discount_id not in discount_data:
                discount_data[user_discount.discount_id] = 0
            discount_data[user_discount.discount_id] += user_discount.amount_rls

        user_discounts.update(amount_rls=0)
        for discount_id, amount in discount_data.items():
            Discount.objects.filter(id=discount_id).update(budget_remain=F('budget_remain') + amount)


def get_user_discount_history(user_id: int) -> Iterable[UserDiscount]:
    """
    This function returns all user discount with sum of transactions
    """
    query_filter = (
        Q(end_date__lt=ir_today(), discount__status__in=[Discount.STATUS.finished, Discount.STATUS.active])
    ) | (Q(activation_date__lte=ir_today(), discount__status=Discount.STATUS.disabled))
    user_discounts = (
        UserDiscount.objects.filter(user_id=user_id)
        .filter(query_filter)
        .distinct()
        .annotate(received_amount=Coalesce(Sum("discount_transaction_log__amount"), Decimal("0")))
        .select_related("discount")
        .order_by("-activation_date")
    )
    return user_discounts


def cancel_user_discount(user_discount: UserDiscount, discount: Discount, end_date: datetime.datetime):
    """
        This function cancels user discount and returns remain amount in user discount to discount budget_remain
    """
    with transaction.atomic():
        remained_budget = user_discount.amount_rls

        if remained_budget:
            discount.budget_remain = F('budget_remain') + remained_budget
            discount.save(update_fields=['budget_remain'])

        user_discount.end_date = end_date
        user_discount.amount_rls = 0
        user_discount.save(update_fields=['end_date', 'amount_rls'])


def get_active_user_discount(
    user_id: int, activation_date: datetime.date, end_date: datetime.date = None, get_remain_amount: bool = False
) -> Optional[UserDiscount]:
    """
    This function returns an active user_discount if it exists.
    """
    if end_date is None:
        query_filter_user_discount_date = Q(end_date__gte=activation_date)

    else:
        query_filter_user_discount_date = Q(activation_date__lte=end_date, end_date__gte=activation_date)

    user_discount = (
        UserDiscount.objects.filter(user_id=user_id, discount__status=Discount.STATUS.active)
        .filter(query_filter_user_discount_date)
    )

    if get_remain_amount:
        user_discount = user_discount.annotate(
            received_amount=Coalesce(Sum("discount_transaction_log__amount"), Decimal("0"))
        )

    user_discount = user_discount.order_by("activation_date").select_related("discount").first()

    return user_discount


def get_discount_with_webengage_id(webengage_campaign_id: str) -> Discount:
    """
        This function returns Discount with webengage_campaign_id or discount_id
    """
    try:
        discount = Discount.objects.get(webengage_campaign_id=webengage_campaign_id)
    except:
        raise DiscountDoesNotExist()
    return discount


def check_active_user_discount(user_id: int, activation_date: datetime.date, end_date: datetime.date = None):
    """
        This function creates new user_discount if active/inactive user_discount is not existed and
        user has not restriction.
    """
    if is_restriction_for_user_discount(user_id):
        raise UserRestrictionError()

    if get_active_user_discount(user_id, activation_date, end_date) is not None:
        report_event('ActiveUserDiscountExistError', extras={'src': 'CheckActiveUserDiscount'})
        raise ActiveUserDiscountExist()


def create_user_discount(user_id: int, discount: Discount, discount_batch_id: int = None):
    """
        This function cancels active user_discount and activate new user_discount
    """
    activation_date, end_date = calculate_dates_for_new_user_discount(discount)

    check_active_user_discount(user_id, activation_date, end_date)

    check_discount_has_enough_budget(discount)

    UserDiscount.create_new_user_discount_with_webengage_campaign_id(user_id, discount, activation_date, end_date,
                                                                     discount_batch_id)


def is_restriction_for_user_discount(user_id: int) -> bool:
    """
        find user restriction before create a user_discount
    """
    return UserRestriction.objects.filter(user_id=user_id, restriction__in=RESTRICTIONS).exists()


def calculate_dates_for_new_user_discount(discount: Discount,
                                          activation_date: datetime.date = None) -> Tuple[datetime.date, datetime.date]:
    """
        this function calculates activation and end date for user discount
    """
    if activation_date is None:
        activation_date = ir_today()
    activation_date = max(discount.start_date, activation_date)
    end_date = activation_date + datetime.timedelta(days=(discount.duration - 1)) if discount.duration > 0 \
        else discount.end_date
    end_date = min(end_date, discount.end_date) if discount.end_date else end_date

    return activation_date, end_date


def get_history_trades_for_user_discount(user_id: int, discount_transaction_log_id: int) -> Iterable[OrderMatching]:
    """
        This function gets user_discount_transaction_log_id and shows history of trades that are used in discount
    """
    user_discount_transaction_log = DiscountTransactionLog.objects.select_related('user_discount') \
        .select_related('user_discount__discount') \
        .filter(id=discount_transaction_log_id).first()
    if user_discount_transaction_log is None:
        return []
    if user_discount_transaction_log.user_discount.user_id != user_id:
        raise DiscountTransactionLogDoesNotExist()

    created_at = user_discount_transaction_log.created_at.astimezone(pytz.timezone('UTC'))
    utc_end_datetime = created_at.replace(hour=20, minute=30, second=0, microsecond=0)
    utc_start_datetime = utc_end_datetime - datetime.timedelta(days=1)

    trade_types = user_discount_transaction_log.user_discount.discount.trade_types or default_trade_types()
    date_query = Q(created_at__gte=utc_start_datetime, created_at__lt=utc_end_datetime)
    trade_and_user_query = Q(sell_order__trade_type__in=trade_types, seller_id=user_id) | Q(
        buy_order__trade_type__in=trade_types, buyer_id=user_id
    )

    trades = OrderMatching.objects.filter(trade_and_user_query, date_query).select_related('market')

    currency = user_discount_transaction_log.user_discount.discount.currency
    if currency is not None:
        trades = trades.filter(Q(market__src_currency=currency) | Q(market__dst_currency=currency))
    return trades


def get_history_discount_transaction_log(user_id: int, user_discount_id: int) -> Iterable[DiscountTransactionLog]:
    """
        This function gets user_id and user_discount_id then return DiscountTransactionLog list
    """
    user_discount = UserDiscount.objects.filter(id=user_discount_id, user_id=user_id)
    if not bool(user_discount):
        raise UserDiscountDoesNotExist()
    user_discount_transaction_logs = DiscountTransactionLog.objects.filter(user_discount_id=user_discount_id)
    return user_discount_transaction_logs


def check_discount_has_enough_budget(discount: Discount):
    if (discount.budget_remain - discount.amount_rls) < 0:
        raise CreateNewUserDiscountBudgetLimit()


def check_discount_is_active(discount: Discount):
    if Discount.STATUS.active != discount.status:
        raise NotActiveDiscount()
