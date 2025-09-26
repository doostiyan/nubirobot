import datetime

from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.base.calendar import ir_dst
from exchange.base.constants import MAX_32_INT
from exchange.corporate_banking.models import STATEMENT_STATUS, CoBankStatement, CoBankUserDeposit
from exchange.wallet.deposit import Currencies
from exchange.wallet.models import Transaction, Wallet


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, dry_run, **options):
        deposits = CoBankUserDeposit.objects.filter(
            cobank_statement__destination_account__account_number='10.8593617.1',
            created_at__date__gte=datetime.datetime.now(ir_dst).date() - datetime.timedelta(days=3),
        ).order_by('-created_at')

        print(f'Total deposits: {deposits.count()}')
        tx_count = 0
        dup_deposit_count = 0
        not_executed_dup_statements = []

        for deposit in tqdm(deposits):
            is_duplicate = (
                CoBankStatement.objects.filter(
                    tracing_number=deposit.cobank_statement.tracing_number,
                    amount=deposit.cobank_statement.amount,
                    source_account=deposit.cobank_statement.source_account,
                    created_at__date__gte=datetime.datetime.now(ir_dst).date() - datetime.timedelta(days=3),
                )
                .exclude(id=deposit.cobank_statement.id)
                .exists()
            )

            if is_duplicate:
                dup_deposit_count += 1

                wallet = Wallet.get_user_wallet(user=deposit.user, currency=Currencies.rls)
                ref_id = (
                    hash(
                        ','.join(
                            [
                                str(deposit.transaction.amount),
                                deposit.cobank_statement.tracing_number,
                                deposit.cobank_statement.source_account,
                            ]
                        )
                    )
                    % MAX_32_INT
                ) - 1

                ref_module = Transaction.REF_MODULES['ReverseTransaction']
                has_reverse_tx = Transaction.objects.filter(
                    wallet=wallet,
                    tp=Transaction.TYPE.manual,
                    ref_id=ref_id,
                    ref_module=ref_module,
                ).exists()

                if has_reverse_tx:
                    continue

                dup_statement = (
                    CoBankStatement.objects.filter(
                        tracing_number=deposit.cobank_statement.tracing_number,
                        amount=deposit.cobank_statement.amount,
                        source_account=deposit.cobank_statement.source_account,
                        created_at__date__gte=datetime.datetime.now(ir_dst).date() - datetime.timedelta(days=3),
                    )
                    .exclude(id=deposit.cobank_statement.id)
                    .first()
                )

                if not dup_statement:
                    continue

                if dup_statement.status != STATEMENT_STATUS.executed:
                    not_executed_dup_statements.append(dup_statement.tracing_number)

                if not dry_run:
                    tx = wallet.create_transaction(
                        tp='manual',
                        amount=-deposit.transaction.amount,
                        ref_id=ref_id,
                        ref_module=ref_module,
                        allow_negative_balance=True,
                        description=f'کسر بابت واریز دابل اسپند کوبنک رسالت شناسه {deposit.id} با شماره پیگیری {deposit.cobank_statement.tracing_number}',
                    )
                    tx.commit(allow_negative_balance=True)

                tx_count += 1

        print(f'Created {tx_count} reverse tx for {dup_deposit_count} duplicate deposit')
        print('Duplicate statements that are not executed:')
        print(not_executed_dup_statements)
