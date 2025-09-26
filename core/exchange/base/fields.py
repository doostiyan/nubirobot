import decimal

from django.db import models


class RoundedDecimalField(models.DecimalField):
    def __init__(self, *args, **kwargs):
        super(RoundedDecimalField, self).__init__(*args, **kwargs)
        self.decimal_ctx = decimal.Context(prec=self.max_digits, rounding=decimal.ROUND_HALF_EVEN)

    def to_python(self, value):
        res = super(RoundedDecimalField, self).to_python(value)
        if res is None:
            return res
        return self.decimal_ctx.create_decimal(res).quantize(
            decimal.Decimal(10) ** -self.decimal_places, context=self.decimal_ctx
        )
