from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from django.db.models import Model

from exchange.base.logging import metric_incr
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.converters.universal_statement_converter import UniversalStatementConverter
from exchange.corporate_banking.integrations.jibit.statements import JibitBankStatementClient
from exchange.corporate_banking.integrations.toman.dto import StatementItemDTO
from exchange.corporate_banking.integrations.toman.statements import TomanBankStatementClient
from exchange.corporate_banking.models import (
    BANK_ID_TO_ENGLISH_NAME,
    COBANK_PROVIDER,
    CoBankAccount,
    CoBankStatement,
    ThirdpartyLog,
)


class Banker:
    providers = {
        COBANK_PROVIDER.toman: TomanBankStatementClient,
        COBANK_PROVIDER.jibit: JibitBankStatementClient,
    }
    metric_name = 'metric_cobanking_core_services_count__statements'

    def __init__(
        self, provider: COBANK_PROVIDER, from_time: Optional[datetime] = None, to_time: Optional[datetime] = None
    ):
        self.from_time = from_time
        self.to_time = to_time
        self.client = None
        self.provider = provider
        self.third_party_log_provider = ThirdpartyLog.COBANK_TO_THIRDPARTY_PROVIDER.get(self.provider)

    def get_statements(self):
        # We should get the statement of all banks but only settle the deposits of operational accounts
        banks = CoBankAccount.objects.filter(provider=self.provider)
        for bank in banks:
            self.get_bank_statements(bank)

    def get_bank_statements(self, bank: CoBankAccount):
        client_cls = self.providers.get(bank.provider, None)
        if not client_cls:
            return

        self.client = client_cls(bank, self.from_time, self.to_time)

        for statements, page in self.client.get_statements():
            try:
                self.store_statements(bank, statements, page)
            except ThirdPartyClientUnavailable as e:
                raise e

    def store_statements(self, bank: CoBankAccount, statement_dtos: List[StatementItemDTO], page: int):
        valid_statements, invalid_statements, created_statements, created_logs = [], [], [], []
        updated_statements_count = 0

        for dto in statement_dtos:
            statement = UniversalStatementConverter(dto).convert()
            if statement:
                statement.destination_account = bank
                valid_statements.append(statement)

            else:
                invalid_statements.append(
                    ThirdpartyLog(
                        content_object=bank,
                        retry=0,
                        api_url=self.client.get_request_url(),
                        request_details={
                            'from_time': self.from_time.isoformat(),
                            'to_time': self.to_time.isoformat(),
                            'page': page,
                        },
                        response_details=asdict(dto),
                        status=ThirdpartyLog.STATUS.failure,
                        provider=self.third_party_log_provider,
                        service=ThirdpartyLog.SERVICE.cobank_statements,
                        status_code=200,
                    ),
                )

        if valid_statements:
            created_statements, updated_statements_count = CoBankStatement.objects.bulk_update_or_create(
                valid_statements,
                unique_fields=['provider_statement_id', 'destination_account'],
                update_fields=CoBankStatement.UPDATABLE_FIELDS,
            )

        if invalid_statements:
            created_logs, _ = ThirdpartyLog.objects.bulk_get_or_create(
                invalid_statements, unique_fields=['api_url', 'request_details']
            )

        self._log_number_of_statements(bank, created_statements, created_logs, updated_statements_count)

    def _log_number_of_statements(
        self,
        bank: CoBankAccount,
        valid_statements: List[Model],
        invalid_statements: List[Model],
        updated_statements_count: int,
    ):
        bank_english_name = BANK_ID_TO_ENGLISH_NAME[bank.bank]
        provider = bank.get_provider_display()
        if valid_statements:
            metric_incr(f'{self.metric_name}_{provider}_{bank_english_name}_valid', amount=len(valid_statements))
        if invalid_statements:
            metric_incr(f'{self.metric_name}_{provider}_{bank_english_name}_invalid', amount=len(invalid_statements))
        if updated_statements_count != 0:
            metric_incr(f'{self.metric_name}_{provider}_{bank_english_name}_updated', amount=updated_statements_count)
