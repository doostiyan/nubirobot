import datetime

import pytz
from django.db import models
from django.db.models import Q, FloatField, Func
from django.db.models.functions import Cast
from django.conf import settings

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.explorer.utils.dto import get_dto_data
from exchange.explorer.utils.blockchain import high_transaction_networks


class Upper(Func):
    function = 'UPPER'
    output_field = models.CharField()


class TransferManager(models.Manager):
    def for_network(self, network):
        if settings.ENABLE_HIGH_TX_NETWORKS_DB and network.upper() in high_transaction_networks:
            db = 'high_tx'
        else:
            db = 'default'

        return super().get_queryset().using(db)


class Transfer(models.Model):
    objects = TransferManager()

    tx_hash = models.CharField(max_length=200)
    success = models.BooleanField()
    from_address_str = models.CharField(max_length=200, null=True, db_index=True)
    to_address_str = models.CharField(max_length=200, null=True, db_index=True)
    value = models.CharField(max_length=100)
    network = models.ForeignKey('networkproviders.Network', on_delete=models.CASCADE, db_index=True)
    symbol = models.CharField(max_length=20)
    block_height = models.BigIntegerField(db_index=True, null=True)
    block_hash = models.CharField(max_length=100, null=True)
    date = models.DateTimeField(null=True)
    memo = models.CharField(max_length=100, default='')
    tx_fee = models.CharField(max_length=50, null=True)
    token = models.CharField(max_length=100, null=True)
    index = models.IntegerField(default=0)
    source_operation = models.CharField()
    created_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['network', 'tx_hash', 'from_address_str', 'to_address_str', 'value', 'block_height', 'index', 'memo'],
                name='unique_tx')
        ]
        index_together = [
            ('source_operation', 'created_at'),
        ]
        indexes = [
            models.Index(
                Upper('from_address_str'),
                Upper('to_address_str'),
                name='idx_upper_from_to'
            ),
            models.Index(
                fields=['network_id', 'source_operation'],
                name='idx_network_source',
            ),
        ]

    @classmethod
    def from_transfer_dto(cls, dto: TransferTx, network_id, source_operation=None):
        data = get_dto_data(dto)
        data.pop('confirmations')
        data['created_at'] = datetime.datetime.now(tz=pytz.UTC)
        data['network_id'] = network_id
        if source_operation:
            data['source_operation'] = source_operation
        return cls(**data)

    @classmethod
    def get_address_transfers_by_network_and_source_operation(cls, network_id, address, source_operation):
        # deprecated ...................................................................................................
        # address = Address.objects.get_or_create(network_id=network_id, blockchain_address=address)[0]
        # withdraw_transfers = list(address.withdraw_transactions.filter(network_id=network_id,
        #                                                                source_operation=source_operation)
        #                           .annotate(value_float=Cast('value', FloatField()))
        #                           .values_list('tx_hash',
        #                                        'from_address__blockchain_address',
        #                                        'to_address__blockchain_address',
        #                                        'value_float'))
        # deposit_transfers = list(address.deposit_transactions.filter(network_id=network_id,
        #                                                              source_operation=source_operation)
        #                          .annotate(value_float=Cast('value', FloatField()))
        #                          .values_list('tx_hash',
        #                                       'from_address__blockchain_address',
        #                                       'to_address__blockchain_address',
        #                                       'value_float'))
        # return set(withdraw_transfers + deposit_transfers)
        # ..............................................................................................................

        transfers = (
            Transfer.objects
            .filter(network_id=network_id)
            .filter(source_operation=source_operation)
            .filter(Q(from_address_str__iexact=address) | Q(to_address_str__iexact=address))
            .annotate(value_float=Cast('value', FloatField()))
            .values_list('tx_hash',
                         'from_address_str',
                         'to_address_str',
                         'value_float')
        )
        return transfers



class Pointer(models.Model):
    point = models.CharField(max_length=50, null=True)
    name = models.CharField(max_length=50, null=True, unique=True)
    processed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pointer[name={self.name}, point={self.point}, processed_at={self.processed_at.isoformat()}]"


class PointerProcessingRange(models.Model):
    start_at = models.CharField(max_length=64)
    end_at = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    last_processed_at = models.DateTimeField()