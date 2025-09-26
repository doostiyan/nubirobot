from django_cron import CronJobBase
from django.conf import settings
from django.utils.functional import cached_property

from exchange.blockchain.metrics import metric_incr
from exchange.base.logging import report_exception

from ..utils.blockchain import get_currency_symbol_from_currency_code


class CronJob(CronJobBase):
    schedule = None
    currency = None
    network = None
    code = None

    @cached_property
    def symbol(self):
        return get_currency_symbol_from_currency_code(self.currency) if self.currency else self.network

    @cached_property
    def module_name(self):
        """Return module name of running cron class, used for reporting and metrics."""
        module_name = self.__class__.__module__.split('.')
        if len(module_name) < 2:
            return 'other'
        return module_name[1]

    def set_process_title(self, status):
        if settings.IS_TEST_RUNNER:
            return
        try:
            from setproctitle import setproctitle
        except ImportError:
            return
        setproctitle(f'runcrons - {self.module_name} - {self.code} - {status}')

    def do(self):
        try:
            self.set_process_title('running')
            self.run()
            metric_incr(f'metric_runcrons_total__{self.module_name}_ok', labels=[self.symbol, self.network])
            self.set_process_title('done')
        except Exception:
            metric_incr(f'metric_runcrons_total__{self.module_name}_failed', labels=[self.symbol, self.network])
            report_exception()
            raise

    def run(self):
        raise NotImplementedError


def set_cron_code(cls, code_fmt):
    cls.code = code_fmt.format(cls.network.lower())
    return cls


