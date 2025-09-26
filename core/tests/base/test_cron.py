from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class RunCronsCommandTestCase(TestCase):
    @staticmethod
    def test_runcrons_success():
        """
        if there are invalid cron classes in the CRON_CLASSES property this test will fail
        e.g. adding 'exchange.accounts.crons.SyncWithProd' class that doesn't exist actually will lead to an exception
        """
        out = StringIO()
        call_command('runcrons', dry_run=True, stdout=out)
        output = out.getvalue().strip()
        assert 'Running Crons\n========================================\n' in output
        assert 'ERROR' not in output
        assert 'ModuleNotFoundError' not in output
