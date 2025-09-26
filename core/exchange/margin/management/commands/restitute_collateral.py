from django.core.management.base import BaseCommand

from exchange.base.formatting import format_money
from exchange.base.models import AMOUNT_PRECISIONS_V2, get_market_symbol
from exchange.base.parsers import parse_int
from exchange.base.tasks import run_admin_task
from exchange.margin.models import Position
from exchange.wallet.models import Transaction, Wallet


class Command(BaseCommand):
    """
    Examples:
        python manage.py restitute_collateral --pids 32,45
    """

    help = 'Fix position pnl calculations.'

    def add_arguments(self, parser):
        parser.add_argument('--pids', type=str, help='list of position ids')

    def handle(self, pids, **options):
        pids = {parse_int(pid) for pid in pids.split(',')}
        positions = Position.objects.filter(id__in=pids, status=Position.STATUS.liquidated).select_related('user')
        missing_positions = pids - {p.id for p in positions}
        if missing_positions:
            print(f'Positions with ids of {missing_positions} are not found or not liquidated')
        for position in positions:
            precision = AMOUNT_PRECISIONS_V2[position.dst_currency]
            restitution_amount = (position.collateral * position.leverage / 10).quantize(precision)
            wallet = Wallet.get_user_wallet(position.user_id, position.dst_currency, tp=Wallet.WALLET_TYPE.margin)
            print(
                'Restitute',
                format_money(restitution_amount, wallet.currency, show_currency=True, use_en=True),
                'to',
                position.user,
            )
            run_admin_task(
                'admin.create_transaction_request',
                wallet_id=wallet.id,
                tp=Transaction.TYPE.manual,
                amount=str(restitution_amount),
                description=(
                    'تراکنش اصلاحی توافقی موقعیت '
                    f'{"خرید" if position.side == Position.SIDES.buy else "فروش"} '
                    f'{get_market_symbol(position.src_currency, position.dst_currency)} #{position.id}'
                ),
                ref_module=Transaction.REF_MODULES['PositionCollateralRestitution'],
                ref_id=position.id,
            )
