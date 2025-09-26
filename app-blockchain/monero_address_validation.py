
def _binToHex(bin_):
    return "".join("%02x" % int(b) for b in bin_)


def _uint64_to_8be(num, size):
    if size < 1 or size > 8:
        return False
    res = [0] * size

    twopow8 = 2 ** 8
    for i in range(size - 1, -1, -1):
        res[i] = num % twopow8
        num = num // twopow8

    return res


def decode_block(data, buf, index):
    __alphabet = [
        ord(s) for s in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    ]
    __b58base = 58
    __UINT64MAX = 2 ** 64
    __encodedBlockSizes = [0, 2, 3, 5, 6, 7, 9, 10, 11]
    __fullBlockSize = 8
    __fullEncodedBlockSize = 11
    l_data = len(data)

    if l_data < 1 or l_data > __fullEncodedBlockSize:
        return False

    res_size = __encodedBlockSizes.index(l_data)
    if res_size <= 0:
        return False

    res_num = 0
    order = 1
    for i in range(l_data - 1, -1, -1):
        digit = __alphabet.index(data[i])
        if digit < 0:
            return False

        product = order * digit + res_num
        if product > __UINT64MAX:
            return False

        res_num = product
        order = order * __b58base

    if res_size < __fullBlockSize and 2 ** (8 * res_size) <= res_num:
        return False

    tmp_buf = _uint64_to_8be(res_num, res_size)
    buf[index: index + len(tmp_buf)] = tmp_buf

    return buf


def decode(enc):
    """Decode a base58 string (ex: a Monero address) into hexidecimal form."""
    enc = bytearray(enc, encoding="ascii")
    l_enc = len(enc)
    __alphabet = [
        ord(s) for s in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    ]
    __b58base = 58
    __UINT64MAX = 2 ** 64
    __encodedBlockSizes = [0, 2, 3, 5, 6, 7, 9, 10, 11]
    __fullBlockSize = 8
    __fullEncodedBlockSize = 11
    if l_enc == 0:
        return ""

    full_block_count = l_enc // __fullEncodedBlockSize
    last_block_size = l_enc % __fullEncodedBlockSize
    try:
        last_block_decoded_size = __encodedBlockSizes.index(last_block_size)
    except ValueError:
        return False

    data_size = full_block_count * __fullBlockSize + last_block_decoded_size

    data = bytearray(data_size)
    for i in range(full_block_count):
        data = decode_block(
            enc[
                (i * __fullEncodedBlockSize) : (
                    i * __fullEncodedBlockSize + __fullEncodedBlockSize
                )
            ],
            data,
            i * __fullBlockSize,
        )

    if last_block_size > 0:
        data = decode_block(
            enc[
                (full_block_count * __fullEncodedBlockSize) : (
                    full_block_count * __fullEncodedBlockSize + last_block_size
                )
            ],
            data,
            full_block_count * __fullBlockSize,
        )

    return _binToHex(data)
