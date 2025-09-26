from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import jdatetime
from django.core.exceptions import ValidationError

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.types import (
    MTI,
    CreditWalletBulkWithdrawCreateRequest,
    DebitCardEnableData,
    TransactionRequest,
    WalletType,
    WalletWithdrawInput,
)
from exchange.base.api import ParseError, get_data
from exchange.base.parsers import (
    parse_choices,
    parse_currency,
    parse_decimal,
    parse_item_list,
    parse_money,
    parse_str,
    parse_uuid,
)
from exchange.wallet.models import Wallet as ExchangeWallet


def parse_abc_service_type(s, **kwargs):
    return parse_choices(Service.TYPES, s, **kwargs)


def parse_abc_provider(s, **kwargs):
    return parse_choices(Service.PROVIDERS, s, **kwargs)


def parse_withdraw_create_request(
    data: dict,
    max_len: int,
) -> Optional[CreditWalletBulkWithdrawCreateRequest]:
    if not isinstance(data, dict):
        raise ParseError(f'Input should be a dict: "{data}"')

    if len(data.get('transfers', [])) > max_len:
        raise ParseError(f'List is too long, max len is {max_len}')

    withdraw_input = WalletWithdrawInput.model_validate(data)

    if withdraw_input.dst_type == WalletType.SPOT:
        dst_type = ExchangeWallet.WALLET_TYPE.spot
    elif withdraw_input.dst_type == WalletType.MARGIN:
        dst_type = ExchangeWallet.WALLET_TYPE.margin
    else:
        raise ValueError

    if withdraw_input.src_type in [WalletType.COLLATERAL, WalletType.CREDIT]:
        src_type = ExchangeWallet.WALLET_TYPE.credit
    elif withdraw_input.src_type == WalletType.DEBIT:
        src_type = ExchangeWallet.WALLET_TYPE.debit
    else:
        raise ValueError

    return CreditWalletBulkWithdrawCreateRequest(
        src_type=src_type,
        dst_type=dst_type,
        transfers={
            parse_currency(item.currency, required=True): parse_money(item.amount, required=True)
            for item in withdraw_input.transfers
        },
    )


def parse_wallet_withdraw_transfers(wallet_transfers) -> Dict[int, Decimal]:
    return {int(currency): Decimal(amount) for currency, amount in wallet_transfers.items()}


def parse_transaction_request(request) -> TransactionRequest:
    data, _ = get_data(request)
    if data is None:
        raise ParseError('request body is missing')

    mti = parse_str(data.get('MTI'), required=True)
    try:
        mti = MTI.from_value(mti)
    except KeyError:
        raise ParseError(f'MTI: {mti} is not valid')

    pan = parse_str(data.get('PAN'), required=True)
    rrn = parse_str(data.get('RRN'), required=True)
    trace_id = parse_str(data.get('Trace'), required=True)
    date = parse_str(data.get('Date'), required=True)
    try:
        jdatetime.datetime.strptime(date, '%Y/%m/%d').date()
    except ValueError:
        raise ValidationError('Invalid date format. Please use the format YYYY/MM/DD.')

    time = parse_str(data.get('Time'), required=True)
    try:
        datetime.strptime(time, '%H:%M:%S').time()
    except ValueError:
        raise ValidationError('Invalid time format. Please use the format hh:mm:ss.')

    process_code = parse_str(data.get('PRCode'), required=True)
    terminal_id = parse_str(data.get('TerminalID'), required=True)
    terminal_owner = parse_str(data.get('TerminalOwner'), required=True)

    amount = parse_decimal(data.get('Price'), required=True)
    if amount <= 0:
        raise ParseError(f'amount: {amount} is not valid')

    rid = parse_str(data.get('RID'), required=True)
    description = parse_str(data.get('Description'))
    additional_data = parse_str(data.get('AdditionalData'))

    return TransactionRequest(
        mti=mti,
        pan=pan,
        rrn=rrn,
        trace_id=trace_id,
        date=date,
        time=time,
        process_code=process_code,
        terminal_id=terminal_id,
        terminal_owner=terminal_owner,
        amount=amount,
        rid=rid,
        description=description,
        additional_data=additional_data,
    )


def parse_pan(request):
    data, _ = get_data(request)
    if data is None:
        raise ParseError('request body is missing')

    return parse_str(data.get('PAN'), required=True)


def parse_enable_debit_card_batch_request(request) -> List[DebitCardEnableData]:
    def clean_data(item: dict):
        user_id = parse_uuid(item.get('userId'), required=True)
        pan = parse_str(item.get('pan'), required=True)
        return DebitCardEnableData(user_id, pan)

    data = parse_item_list(request.g('data'), item_type=dict, required=True)
    if len(data) > 1000:
        raise ParseError('data is too large')

    return [clean_data(item) for item in data]
