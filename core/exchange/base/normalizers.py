"""Utilities to create a unified normal form for different user input types."""
import re


def normalize_digits(s):
    if not s:
        return s
    digits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
    for i, digit in enumerate(digits):
        s = s.replace(digit, str(i))
    return s


def normalize_mobile(s):
    if not s:
        return s
    mobile = normalize_digits(s)
    if mobile.startswith('+'):
        mobile = mobile[1:]
    if mobile.startswith('98'):
        mobile = mobile[2:]
    if mobile.startswith('00'):
        mobile = mobile[2:]
    if mobile and mobile[0] != '0':
        mobile = '0' + mobile
    return mobile


def normalize_email(email):
    """
    Normalize the email address by lowercasing both parts of it and trimming its whitespaces.
    """
    email = email or ''
    email = email.strip().replace('\u200c', '').replace('\u200b', '')
    try:
        email_name, domain_part = email.rsplit('@', 1)
    except ValueError:
        pass
    else:
        email = email_name.lower() + '@' + domain_part.lower()
    return email


def normalize_phone(s):
    if not s:
        return s
    phone = normalize_digits(s)
    phone = re.sub(r'([+-]|\s)', '', phone)
    return phone


def normalize_name(s):
    if not s:
        return s
    s = s.strip()
    same_chars = [
        ('ي', 'ی'),
        ('ك', 'ک'),
        ('ٸ', 'ئ'),
        ('إ', 'ا'),
        ('ـ', ''),
        ('\n', ' '),
        ('\t', ' '),
    ]
    for ch1, ch2 in same_chars:
        s = s.replace(ch1, ch2)
    return s


def fully_normalize_name(name, delete_spaces=False):
    same_chars = [
        ('ي', 'ی'),
        ('ك', 'ک'),
        ('ئ', 'ی'),
        ('ٸ', 'ی'),
        ('ؤ', 'و'),
        ('آ', 'ا'),
        ('أ', 'ا'),
        ('إ', 'ا'),
        ('ـ', ''),   # U+0640 ARABIC TATWEEL
        ('٠', '?'),  # U+0660 ARABIC-INDIC DIGIT ZERO
    ]
    re_replace = [
        (r'الله\b', 'اله'),
    ]
    if name is None:
        return ''
    for ch1, ch2 in same_chars:
        name = name.replace(ch1, ch2)
    for pattern, repl in re_replace:
        name = re.sub(pattern, repl, name)
    if delete_spaces:
        name = re.sub(r'(\s|[\u200c])', '', name, flags=re.UNICODE)
    return name


def compare_farsi_strings(s, t):
    """Compare two strings of Farsi text ignoring single character writing differences"""
    i = j = 0
    n = len(s)
    m = len(t)
    chars_hamza = ['ا', 'و', 'ی']
    chars_question = ['?', '؟']
    while i < n:
        ch1 = s[i]
        ch2 = t[j] if j < m else ''
        if ch1 == ch2:
            i += 1
            j += 1
            continue
        if ch1 in chars_question or ch2 in chars_question:
            i += 1
            j += 1
            continue
        if ch1 == 'ء':
            if ch2 in chars_hamza:
                i += 1
                j += 1
                continue
            if i + 1 < n:
                if s[i + 1] == ch2:
                    i += 2
                    j += 1
                    continue
            else:
                if ch2 == '':
                    i += 1
                    continue
        if ch2 == 'ء':
            if ch1 in chars_hamza:
                i += 1
                j += 1
                continue
            if j + 1 < m:
                if t[j + 1] == ch1:
                    i += 1
                    j += 2
                    continue
            else:
                if ch1 == '':
                    j += 1
                    continue
        return False
    return i == n and j == m


def compare_names(first_name_a, last_name_a, first_name_b, last_name_b):
    """ Compare two full names given as separate first and last names, ignoring
         common writing differences
    """
    first_a = fully_normalize_name(first_name_a, delete_spaces=True)
    first_b = fully_normalize_name(first_name_b, delete_spaces=True)
    last_a = fully_normalize_name(last_name_a, delete_spaces=True)
    last_b = fully_normalize_name(last_name_b, delete_spaces=True)
    return compare_farsi_strings(first_a, first_b) and compare_farsi_strings(last_a, last_b)


def compare_full_names(name_a, name_b):
    """ Compare two full names ignoring common writing differences
    """
    name_a = fully_normalize_name(name_a, delete_spaces=True)
    name_b = fully_normalize_name(name_b, delete_spaces=True)
    return compare_farsi_strings(name_a, name_b)
