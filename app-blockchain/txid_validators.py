def btc_validate_txid(txid):
    # btc txid is a standard SHA256 digest
    txid = str(txid)
    try:
        int(txid, 16)
    except ValueError:
        print('TxID is not a proper hexadecimal.')
    length = len(txid)
    try:
        assert length == 64
    except AssertionError:
        print('TxID not 64 characters long. TxID length is: ' + str(length))
    try:
        assert txid.islower()
    except AssertionError:
        print('TxID not lowercase. Lowercase TxID expected for this coin')


def bch_validate_txid(txid):
    # bch and btc have same txid hash protocol
    return btc_validate_txid(txid)


def ltc_validate_txid(txid):
    # ltc and btc have same txid hash protocol
    return ltc_validate_txid(txid)


def xrp_validate_txid(txid):
    # xrp txid is an upercase SHA-512Half
    txid = str(txid)
    try:
        assert txid.isupper()
    except AssertionError:
        print('TxID not uppercase. Uppercase TxID expected for XRP')
    return btc_validate_txid(txid)


def eth_validate_txid(txid):
    # Keccak-256 hash with 0x padding
    txid = str(txid)
    try:
        assert txid[:2] == '0x'
    except AssertionError:
        print('TxID does not begin with 0x but it should.')
    length = len(txid)
    try:
        assert length == 66
    except AssertionError:
        print('TxID not 66 characters long. TxID length is: ' + str(length))
    try:
        int(txid, 16)
    except ValueError:
        print('TxID is not a proper hexadecimal.')
    try:
        assert txid.islower()
    except AssertionError:
        print('TxID not lowercase. Lowercase TxID expected for ETH')


def etc_validate_txid(txid):
    # same as Ethereum
    return eth_validate_txid(txid)


def usdt_validate_txid(txid):
    # same as Ethereum
    return eth_validate_txid(txid)


def bnb_validate_txid(txid):
    # same as Ehtereum
    return eth_validate_txid(txid)


def xlm_validate_txid(txid):
    # Could not find concrete information on hashing algorithm, but the hash IDs look like btc txIDs
    return btc_validate_txid(txid)


def eos_validate_txid(txid):
    # TxID is standard lower case SHA-256 digest like btc
    return btc_validate_txid(txid)
