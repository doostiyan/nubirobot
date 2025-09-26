from django.db import models


class Network(models.Model):
    MEMO_BASED = 'memo_based'
    ACCOUNT_BASED = 'account_based'
    UTXO_BASED = 'utxo_based'

    NETWORK_TYPES = [
        (MEMO_BASED, 'Memo Based'),
        (ACCOUNT_BASED, 'Account Based'),
        (UTXO_BASED, 'UTXO Based'),
    ]
    name = models.CharField(max_length=10, unique=True)
    block_limit_per_req = models.PositiveSmallIntegerField(default=1)
    use_db = models.BooleanField(default=False)
    save_address_txs = models.BooleanField(default=False)
    block_time = models.PositiveIntegerField(default=1.0)
    type = models.CharField(max_length=20, choices=NETWORK_TYPES, null=True, blank=True)

    def __str__(self):
        return self.name
