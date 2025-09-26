from exchange.base.constants import MAX_32_INT, MAX_POSITIVE_32_INT


def encode_id(id_: int) -> int:
    """Convert a negative ID to a positive number by adding 2 * 32 to it.

    Note: We are treating zero as a negative number to avoid an edge case
          when a transaction with zero id inserted into db, it should
          be considered newer than the positive ones in the backend.
    """
    if id_ > 0:
        return id_
    return id_ + MAX_POSITIVE_32_INT


def decode_id(id_: int) -> int:
    """Convert a positive ID received from the client back to its original
    negative or positive value as stored in the database.

    If the ID exceeds MAX_32_INT (indicating it was encoded using encode_id),
    the function subtracts MAX_POSITIVE_32_INT to revert to the original
    negative ID. Otherwise, it returns the ID unchanged as it is already
    a valid positive ID.
    """
    if id_ > MAX_32_INT:
        return id_ - MAX_POSITIVE_32_INT
    return id_
