import random
import string
import uuid


def random_string(l):
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(l))


def unique_random_string():
    return uuid.uuid4().hex


def random_string_digit(l):
    return ''.join(random.SystemRandom().choice(string.digits) for _ in range(l))
