from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from django.db import transaction
from django.db.models import Q

from exchange.accounts.models import User
from exchange.base.constants import ZERO
from exchange.base.internal.services import Services
from exchange.wallet.internal.exceptions import (
    DisallowedDstWalletType,
    DisallowedSrcWalletType,
    DisallowedSystemWallet,
    InactiveWallet,
    InsufficientBalance,
    InvalidRefModule,
    InvalidTransaction,
    InvalidTransactionType,
    NonZeroAmountSum,
    TransactionException,
    UserNotFound,
)
from exchange.wallet.internal.permissions import (
    ALLOWED_DST_TYPES,
    ALLOWED_NEGATIVE_BALANCE_WALLETS,
    ALLOWED_SRC_TYPES,
    ALLOWED_SYSTEM_USER,
    ALLOWED_TX_REF_MODULES,
    ALLOWED_TX_TYPE,
)
from exchange.wallet.internal.types import TransactionInput, TransactionResult
from exchange.wallet.models import Transaction, Wallet


def create_service_transaction(
    service: Services,
    wallet: Wallet,
    tp: str,
    amount: Decimal,
    description: str,
    ref_module: Optional[str] = None,
    ref_id: Optional[int] = None,
    *,
    allow_negative_balance=False,
) -> Transaction:
    """
    Creates a transaction within a specific service context for a given wallet.

    Raises:
    - InactiveWallet: If the wallet is not active.
    - InvalidRefModule: If `ref_module` is invalid or not allowed for the specified service.
    - InvalidTransactionType: If the transaction type `tp` is invalid for the service.
    - DisallowedSystemWallet: If the wallet is flagged as a system wallet but not permitted for
      the service.
    - DisallowedSrcWalletType: If the wallet type is disallowed as a source wallet for the
      service.
    - DisallowedDstWalletType: If the wallet type is disallowed as a destination wallet for the
      service.
    - InsufficientBalance: If there are insufficient funds in the wallet and negative balance is
      not allowed.
    - InvalidTransaction: If the transaction is flagged as invalid during the commit phase.

    """

    # Validate
    if not wallet.is_active:
        raise InactiveWallet()

    _ref_module = None
    if ref_module:
        if ref_module not in Transaction.REF_MODULES or ref_module not in ALLOWED_TX_REF_MODULES.get(service, ()):
            raise InvalidRefModule()

        _ref_module = Transaction.REF_MODULES[ref_module]

    _type = getattr(Transaction.TYPE, tp, None)
    if not _type or _type not in ALLOWED_TX_TYPE.get(service, ()):
        raise InvalidTransactionType()

    is_system_wallet = False
    if wallet.user.is_system_user:
        if wallet.user_id not in ALLOWED_SYSTEM_USER.get(service, ()):
            raise DisallowedSystemWallet()
        is_system_wallet = True

    if not is_system_wallet:
        if amount < ZERO:  # src tx
            if wallet.type not in ALLOWED_SRC_TYPES.get(service, ()):
                raise DisallowedSrcWalletType()

        elif wallet.type not in ALLOWED_DST_TYPES.get(service, ()):  # dst tx
            raise DisallowedDstWalletType()

    # Process
    _allow_negative_balance = allow_negative_balance or wallet.pk in ALLOWED_NEGATIVE_BALANCE_WALLETS.get(service, ())
    try:
        tx = wallet.create_transaction(
            tp=tp,
            amount=amount,
            description=description,
            ref_module=_ref_module,
            ref_id=ref_id,
            service=service,
            allow_negative_balance=_allow_negative_balance,
        )
    except ValueError as ex:
        raise InvalidTransaction() from ex

    if tx is None:
        raise InsufficientBalance()

    try:
        tx.commit(allow_negative_balance=_allow_negative_balance)
    except ValueError as ex:
        raise InsufficientBalance() from ex

    return tx


@transaction.atomic
def create_batch_service_transaction(
    service: Services,
    batch_transaction_data: Sequence[TransactionInput],
) -> Tuple[List[TransactionResult], bool]:
    """Creates a batch of service transactions, reordering transactions based on specified priority,
    but preserving original order in the results.

    Returns:
        Tuple[List[TransactionResult], bool]: A tuple containing:
            - List[TransactionResult]: Results for each transaction, in the original order, with success or error details.
            - bool: A flag indicating whether any errors occurred during the transaction creation process.

    Raises:
        UserNotFound: If any user involved in the transactions is not found.
        NonZeroAmountSum: If the sum of transactions for a currency is not zero, indicating imbalance.
        DatabaseError: If some wallets are db locked.

    This function performs the following steps:
        1. Reorders transactions to prioritize:
            - Positive transactions targeting wallets with negative transactions.
            - Negative transactions.
            - Remaining positive transactions.
        2. Processes transactions based on the above priority.
        3. Returns results in the original order of `batch_transaction_data`.
    """

    _check_transactions_sum(batch_transaction_data)

    # Step 1: Annotate each transaction with its original index
    indexed_transactions = list(enumerate(batch_transaction_data))

    # Separate transactions into negative and positive with original indices
    negative_transactions = [(i, tx) for i, tx in indexed_transactions if tx.amount < 0]
    positive_transactions = [(i, tx) for i, tx in indexed_transactions if tx.amount > 0]

    # Identify wallets involved in negative transactions
    negative_wallet_keys = {f'{tx.uid}-{tx.int_currency}-{tx.int_wallet_type}' for _, tx in negative_transactions}

    # Group positive transactions targeting wallets with negative transactions
    prioritized_positive_transactions = [
        (i, tx)
        for i, tx in positive_transactions
        if f'{tx.uid}-{tx.int_currency}-{tx.int_wallet_type}' in negative_wallet_keys
    ]

    # Group remaining positive transactions
    other_positive_transactions = [
        (i, tx)
        for i, tx in positive_transactions
        if f'{tx.uid}-{tx.int_currency}-{tx.int_wallet_type}' not in negative_wallet_keys
    ]

    # Combine the transactions in the required execution order
    ordered_transactions = prioritized_positive_transactions + negative_transactions + other_positive_transactions

    # Step 2: Execute transactions in the specified order
    result_transactions = [TransactionResult() for _ in batch_transaction_data]
    has_error = False

    users = get_users(batch_transaction_data)
    wallets_dict = _get_wallets(batch_transaction_data, users)
    for original_index, transaction_data in ordered_transactions:
        user_id = users[transaction_data.uid].pk
        wallet_key = f'{user_id}-{transaction_data.int_currency}-{transaction_data.int_wallet_type}'
        is_wallet_created = False

        try:
            with transaction.atomic(savepoint=True):
                if wallet_key not in wallets_dict:
                    wallets_dict[wallet_key] = Wallet.create_user_wallet(
                        user=user_id,
                        currency=transaction_data.int_currency,
                        tp=transaction_data.int_wallet_type,
                    )
                    is_wallet_created = True

                tx = create_service_transaction(
                    service=service,
                    wallet=wallets_dict[wallet_key],
                    tp=transaction_data.tp,
                    amount=transaction_data.amount,
                    ref_module=transaction_data.ref_module,
                    ref_id=transaction_data.ref_id,
                    description=transaction_data.description,
                )
                result_transactions[original_index].tx = tx
        except TransactionException as ex:
            has_error = True
            result_transactions[original_index].error = ex
            if is_wallet_created:
                del wallets_dict[wallet_key]

            break

    if has_error:
        transaction.set_rollback(rollback=True)
        return result_transactions, True

    return result_transactions, has_error


def get_users(batch_transaction_data: Sequence[TransactionInput]) -> Dict[UUID, User]:
    """Fetches active user records based on transaction data and ensures all users exist.

    Raises:
        UserNotFound: If any users in `batch_transaction_data` are not found or inactive.
    """

    u_ids = {u.uid for u in batch_transaction_data}
    users = User.objects.filter(uid__in=u_ids, is_active=True).only('id', 'user_type', 'uid').in_bulk(field_name='uid')
    missing_users = {t.uid for t in batch_transaction_data}.difference(set(users.keys()))
    if len(missing_users) != 0:
        raise UserNotFound({str(uid) for uid in missing_users})
    return users


def _get_wallets(batch_transaction_data: Sequence[TransactionInput], users: Dict[UUID, User]) -> Dict[str, Wallet]:
    """Creates a wallet for a user if it does not exist and locks it for transaction use.

    This helper function ensures that a wallet is created and locked for transactional operations,
    preventing conflicts during concurrent transactions.

    Raises:
        DatabaseError: If some wallets are db locked.
    """

    wallet_queries = {
        Q(user_id=users[t.uid].pk, currency=t.int_currency, type=t.int_wallet_type) for t in batch_transaction_data
    }
    wallets_query = wallet_queries.pop()
    for query in wallet_queries:
        wallets_query |= query

    wallets = Wallet.objects.filter(wallets_query).select_for_update(of=('self',), nowait=True, no_key=True)
    wallets_dict = {}
    for wallet in wallets:
        wallets_dict[f'{wallet.user_id}-{wallet.currency}-{wallet.type}'] = wallet
    return wallets_dict


def _check_transactions_sum(input_transactions: Sequence[TransactionInput]):

    """This function calculates the net sum of all transaction amounts by currency, ignoring any
    transactions that resulted in errors, to ensure the total is balanced.

    Raises:
        NonZeroAmountSum: If the sum of transaction amounts for any currency is not zero.
    """

    sum_of_transactions = defaultdict(lambda: ZERO)

    for input_tx in input_transactions:
        sum_of_transactions[input_tx.currency] += input_tx.amount

    for currency, amount_sum in sum_of_transactions.items():
        if amount_sum != ZERO:
            raise NonZeroAmountSum(currency=currency)
