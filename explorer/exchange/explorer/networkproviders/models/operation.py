from django.db import models


class Operation(models.TextChoices):
    BALANCE = 'balance'
    TOKEN_BALANCE = 'token_balance'
    TX_DETAILS = 'tx_details'
    TOKEN_TX_DETAILS = 'token_tx_details'
    ADDRESS_TXS = 'address_txs'
    TOKEN_TXS = 'token_txs'
    BLOCK_TXS = 'block_txs'
    BLOCK_HEAD = 'block_head'
