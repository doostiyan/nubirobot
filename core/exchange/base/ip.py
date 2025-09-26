def ip_mask(ip):
    mask = 64 if ':' in ip else 32
    return f'{ip}/{mask}'
