from cryptography.fernet import Fernet

from .main import env

MASTER_KEY = env('MASTERKEY').encode('ascii')


# Secret Management
def decrypt_string(s):
    if not MASTER_KEY:
        return ''
    f = Fernet(MASTER_KEY)
    return f.decrypt(s.encode('ascii')).decode('ascii')


def encrypt_string(s):
    if not MASTER_KEY:
        return ''
    f = Fernet(MASTER_KEY)
    return f.encrypt(s.encode('ascii')).decode('ascii')


SECRET_KEY = decrypt_string(env.str('SECRET_KEY'))
