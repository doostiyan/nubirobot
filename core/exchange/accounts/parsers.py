import re
import uuid
from typing import List

from django.shortcuts import get_object_or_404

from exchange.base.parsers import parse_choices, parse_str
from exchange.base.api import ParseError, NobitexAPIError
from .models import User, UploadedFile, VerificationRequest, BaseBankAccount, UserOTP


def parse_gender(s, **kwargs):
    return parse_choices(User.GENDER, s, **kwargs)


def parse_verification_tp(s, **kwargs):
    return parse_choices(VerificationRequest.TYPES, s, **kwargs)


def parse_otp_tp(s, **kwargs):
    return parse_choices(User.OTP_TYPES, s, **kwargs)


def parse_otp_usage(s, **kwargs):
    return parse_choices(UserOTP.OTP_Usage, s, **kwargs)


def parse_files(s, required=False, *_) -> List[UploadedFile]:
    file_ids = (s or '').split(',')
    files = []
    for file_id in file_ids:
        file_id = file_id.strip()
        if not file_id:
            continue
        filename = uuid.UUID(file_id)
        files.append(get_object_or_404(UploadedFile, filename=filename))
    if not files and required:
        raise ParseError('No file uploaded')
    return files


def parse_telegram_chat_id(s):
    s = (s or '').strip()
    if not re.match(r'(@[a-zA-Z0-9_]{4,19}|[0-9-]{5,20})$', s):
        raise NobitexAPIError('InvalidChatID', 'Invalid Chat ID')
    return s


def parse_account_id(s, **kwargs):
    s = parse_str(s, **kwargs)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{3,40}', s):
        raise ParseError('Invalid Account ID')
    return s


def parse_bank_id(s, **kwargs):
    return parse_choices(BaseBankAccount.BANK_ID, s, **kwargs)
