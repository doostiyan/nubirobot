import re

from django.db import connection
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email

from exchange.base.logging import report_event


def validate_email(email):
    if not email:
        return False
    email = email.lower().strip()
    try:
        django_validate_email(email)
    except ValidationError:
        return False
    domain = email.split('@')[1]
    invalid_domains = [
        # Spelling Errors
        'gmil.com', 'gamil.com', 'gmai.com', 'jmail.com', 'gmail.con', 'gmali.com',
        'gmial.com', 'gimil.com', 'gimail.com', 'gnail.com', 'gmal.com', 'gimal.com',
        'gmaile.com', 'gmail.co', 'gmile.com', 'gmsil.com', 'gmail.cim', 'gmail.ir',
        'gmaill.com', 'gemail.com', 'gemil.com', 'gmeil.com', 'gamail.com', 'jmil.com',
        'gmamil.com',
        'yahoo.con', 'yahoo.co', 'yaho.com', 'yhaoo.com',
        # Temporary emails, relays, and other unacceptable domains
        'example.com', 'mail.com', 'email.com', 'aol.com', 'hi2.in', 'tutanota.com',
        'relay.mozmail.com',
    ]
    if domain in invalid_domains:
        return False
    return True


def validate_mobile(mobile, strict=False):
    if not mobile:
        return False
    if len(mobile) > 12 or len(mobile) < 10:
        return False
    if not mobile.isdigit():
        if not (mobile[0] == '+' and mobile[1:].isdigit()):
            return False
    if strict:
        if not mobile.startswith('09'):
            return False
    return True


def validate_phone(phone, code=None):
    if not phone:
        return False
    if code and not phone.startswith(code):
        return False
    if phone.startswith('09') or phone.startswith('9'):
        return False
    if len(phone) != 11:
        return False
    return True


def validate_national_code(ncode):
    ncode = str(ncode)
    if not re.match(r'[0-9]{10}', ncode):
        return False
    total = 0
    for i, c in enumerate(ncode[:9]):
        try:
            c = int(c)
        except:
            return False
        total += c * (10 - i)
    if not total:
        return False
    r = total % 11
    ctrl_digit = r if r < 2 else 11 - r
    return int(ncode[9]) == ctrl_digit


def validate_postal_code(code):
    return len(code) == 10


def validate_iban(iban):
    """Check validity of an IBAN number, including the initial IR."""
    return iban and re.match(r'IR[0-9]{24}$', iban)


def validate_name(name):
    """Check the given first or last name contain valid characters and formatting."""
    if not name:
        return False
    if re.search(r'[a-zA-Z0-9_\n\t-]', name):
        return False
    return len(name.strip()) >= 2


def validate_transaction_is_atomic() -> None:
    if not connection.in_atomic_block:
        report_event(message='failed validate_transaction_is_atomic', level='error',)
        raise ValidationError('InvalidDBTransaction')
