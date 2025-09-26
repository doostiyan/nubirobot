from exchange.base.serializers import register_serializer
from exchange.direct_debit.models import DirectDebitBank, DirectDebitContract, DirectDeposit


@register_serializer(model=DirectDebitBank)
def serialize_direct_debit_bank(bank: DirectDebitBank, opts=None):
    opts = opts or {}
    if opts.get('bank_name_only', False):
        return {
            'id': bank.id,
            'bankName': bank.name,
            'bankID': bank.bank_id,
            'isActive': bank.is_active,
        }
    return {
        'id': bank.id,
        'bankName': bank.name,
        'bankID': bank.bank_id,
        'isActive': bank.is_active,
        'dailyMaxTransactionAmount': bank.daily_max_transaction_amount,
        'dailyMaxTransactionCount': bank.daily_max_transaction_count,
        'maxTransactionAmount': bank.max_transaction_amount,
    }


@register_serializer(DirectDebitContract)
def serialize_direct_debit_contract(contract: DirectDebitContract, opts=None):
    data = {
        'id': contract.pk,
        'status': contract.get_status_display(),
        'createdAt': contract.created_at,
        'contractCode': contract.contract_code,
        'startedAt': contract.started_at,
        'expiresAt': contract.expires_at,
        'dailyMaxTransactionCount': contract.daily_max_transaction_count,
        'dailyMaxTransactionAmount': contract.bank.daily_max_transaction_amount,
        'maxTransactionAmount': contract.max_transaction_amount,
        'bank': serialize_direct_debit_bank(contract.bank, opts),
    }
    if hasattr(contract, 'today_transaction_count'):
        data.update({'todayTransactionCount': contract.today_transaction_count})
    if hasattr(contract, 'today_transaction_amount'):
        data.update({'todayTransactionAmount': contract.today_transaction_amount})
    return data


@register_serializer(DirectDeposit)
def serialize_direct_debit_deposit(deposit: DirectDeposit, opts):
    return {
        'id': deposit.pk,
        'status': deposit.get_status_display(),
        'date': deposit.effective_date,
        'traceID': deposit.trace_id,
        'referenceID': deposit.reference_id,
        'amount': deposit.amount,
        'fee': deposit.fee,
        'depositType': 'directDeposit',
        'bank': deposit.contract.bank,
    }
