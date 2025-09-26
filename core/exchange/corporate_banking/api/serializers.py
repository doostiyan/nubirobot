from exchange.base.serializers import register_serializer, serialize_choices
from exchange.corporate_banking.data_models import BluCoBankDepositInfo, CoBankDepositInfo
from exchange.corporate_banking.models import (
    REJECTION_REASONS,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankCard,
    CoBankStatement,
    CoBankUserDeposit,
)


@register_serializer(model=CoBankDepositInfo)
def serialize_cobank_deposit_info(cobank_deposit_info: CoBankDepositInfo, opts: dict) -> dict:
    return {
        'bank': cobank_deposit_info.bank,
        'bankAccountNumber': cobank_deposit_info.cobank_account_number,
        'bankOwner': cobank_deposit_info.cobank_owner,
        'userBankAccounts': cobank_deposit_info.user_accounts,
    }

@register_serializer(model=BluCoBankDepositInfo)
def serialize_blu_deposit_info(cobank_deposit_info: CoBankDepositInfo, opts: dict) -> dict:
    return {**serialize_cobank_deposit_info(cobank_deposit_info, opts), 'bank': 'بلو'}


@register_serializer(model=CoBankCard)
def serialize_cobank_card_deposit_info(cobank_card: CoBankCard, opts: dict) -> dict:
    return {
        'bank': cobank_card.bank_account.get_bank_display(),
        'bankCardNumber': cobank_card.card_number,
        'bankOwner': cobank_card.name or cobank_card.bank_account.account_owner,
    }


@register_serializer(model=CoBankUserDeposit)
def serialize_cobank_user_deposit(cobank_user_deposit: CoBankUserDeposit, opts: dict) -> dict:
    return {
        'id': cobank_user_deposit.id,
        'userBankAccount': cobank_user_deposit.user_bank_account,
        'depositType': 'cobankDeposit',
        'amount': cobank_user_deposit.amount,
        'fee': cobank_user_deposit.fee,
        'createdAt': cobank_user_deposit.created_at,
        'statement': cobank_user_deposit.cobank_statement,
    }



@register_serializer(model=CoBankStatement)
def serialize_cobank_statement(cobank_statement: CoBankStatement, opts: dict) -> dict:
    return {
        'amount': cobank_statement.amount,
        'tp': serialize_choices(STATEMENT_TYPE, cobank_statement.tp),
        'createdAt': cobank_statement.created_at,
        'tracingNumber': cobank_statement.tracing_number,
        'transactionDatetime': cobank_statement.transaction_datetime,
        'paymentId': cobank_statement.payment_id,
        'status': serialize_choices(STATEMENT_STATUS, cobank_statement.status),
        'rejection_reason': serialize_choices(REJECTION_REASONS, cobank_statement.rejection_reason),
    }
