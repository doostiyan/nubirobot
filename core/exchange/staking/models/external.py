"""ExternalEarningPlatform Model"""
from django.db import models
from model_utils import Choices

from exchange.base.models import Currencies


class ExternalEarningPlatform(models.Model):
    TYPES = Choices(
        (101, 'staking', 'Staking'),
        (201, 'margin_trading', 'Margin Trading'),
        (301, 'yield_aggregator', 'Yield Aggregator'),
    )

    tp = models.SmallIntegerField(choices=TYPES)
    currency = models.SmallIntegerField(choices=Currencies)
    is_available = models.BooleanField(default=True)

    # pos credentials
    network = models.CharField(max_length=32, default='')
    address = models.CharField(max_length=128, default='')
    tag = models.CharField(max_length=128, default='')

    @classmethod
    def get_type_machine_display(cls, tp: int):
        return next(name for name, value in cls.TYPES._identifier_map.items() if value == tp)

    @property
    def type_fa_display(self):
        return {
            101: 'استیکینگ',
            301: 'ییلد فارمینگ',
        }[self.tp]
