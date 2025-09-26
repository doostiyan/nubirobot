import time

from exchange.accounts.models import User
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_event
from exchange.web_engage.services.esp import cleanup_email_logs
from exchange.web_engage.services.ssp import batch_and_send_sms_messages, inquire_sent_batch_sms
from exchange.web_engage.services.user import get_users_have_trade_last_day, send_user_data_to_webengage


class UpdateWebEngageUserData(CronJob):
    schedule = Schedule(run_at_times=['4:00'])
    code = 'web_engage_update_user_data'

    def run(self):
        user_ids = get_users_have_trade_last_day()
        report_event('WebEngage.UpdateWebEngageUserData', extras={'number_of_users': str(len(user_ids))})
        for user_id in user_ids:
            time.sleep(0.05)
            send_user_data_to_webengage(user=User.objects.get(id=user_id))


class CreateAndSendBatchSMS(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'send_webengage_batch_sms'

    def run(self):
        batch_and_send_sms_messages()


class InquireSentBatchSMSStatus(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'inquire_webengage_sent_messages_status'

    def run(self):
        inquire_sent_batch_sms()


class CleanUpEmailLogs(CronJob):
    schedule = Schedule(run_every_mins=120)
    code = 'clean_up_webengage_email_logs'

    def run(self):
        cleanup_email_logs()
