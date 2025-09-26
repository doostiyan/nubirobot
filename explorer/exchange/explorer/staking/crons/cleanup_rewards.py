from datetime import timedelta

from django.utils import timezone
from django_cron import Schedule

from exchange.blockchain.models import Currencies, CurrenciesNetworkName
from exchange.explorer.staking.models import StakingReward
from exchange.explorer.utils.cron import CronJob, set_cron_code
from exchange.explorer.utils.logging import get_logger

code_fmt = 'cleanup_staking_rewards'
set_code = set_cron_code

class CleanupStakingRewardsCron(CronJob):
    code_fmt = 'cleanup_staking_rewards'

    def run(self) -> None:
        logger = get_logger()
        try:
            logger.info('Starting staking rewards cleanup')
            cutoff_date = timezone.now() - timedelta(minutes=1)
            logger.info('Cutoff date: %s', cutoff_date)
            old_rewards = StakingReward.objects.filter(created_at__lt=cutoff_date)
            deleted_count = old_rewards.delete()
            logger.info('Deleted %s old rewards', deleted_count)
            logger.info('Staking rewards cleanup completed successfully')
        except Exception:
            logger.exception('Error in staking rewards cleanup')

@set_code
class CleanupBSCStakingRewardsCron(CleanupStakingRewardsCron):
    schedule = Schedule(run_at_times=['00:00'])
    network = CurrenciesNetworkName.BSC
    symbol = Currencies.bnb
