from exchange.base.calendar import ir_today
from exchange.base.constants import ZERO
from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer, serialize_choices
from exchange.margin.models import Position
from exchange.market.markprice import MarkPriceCalculator


@register_serializer(model=Position)
def serialize_position(position: Position, opts):
    opts = opts or {}
    data = {
        'id': position.id,
        'createdAt': position.created_at,
        'side': serialize_choices(Position.SIDES, position.side),
        'srcCurrency': get_currency_codename(position.src_currency),
        'dstCurrency': get_currency_codename(position.dst_currency),
        'status': position.get_status_display(),
        'marginType': position.get_margin_type_display(),
        'collateral': position.collateral,
        'leverage': position.leverage,
        'openedAt': position.opened_at,
        'closedAt': position.closed_at,
        'liquidationPrice': position.liquidation_price,
        'entryPrice': position.entry_price,
        'exitPrice': position.exit_price,
    }
    if position.pnl is None:
        get_mark_price = opts.get('get_mark_price', MarkPriceCalculator.get_mark_price)
        data.update(
            {
                'delegatedAmount': position.delegated_amount,
                'liability': position.liability,
                'totalAsset': position.total_asset,
                'marginRatio': position.margin_ratio,
                'liabilityInOrder': position.liability_in_order,
                'assetInOrder': position.asset_in_order,
                'unrealizedPNL': position.unrealized_pnl,
                'unrealizedPNLPercent': position.unrealized_pnl_percent,
                'expirationDate': position.expiration_date,
                'markPrice': get_mark_price(position.src_currency, position.dst_currency) or ZERO,
            }
        )
        if (position.expiration_date - ir_today()).days > 1:
            data['extensionFee'] = position.extension_fee_amount
    else:
        data.update({
            'PNL': position.pnl,
            'PNLPercent': position.pnl_percent,
        })
    return data
