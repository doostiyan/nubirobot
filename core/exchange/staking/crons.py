"""Staking Crons"""
from collections import defaultdict

from celery import chain
from django.conf import settings

from exchange.base.crons import CronJob, Schedule
from exchange.staking.models import Plan, UserWatch
from exchange.staking.tasks import (
    announce_rewards_task,
    assign_staking_to_users_task,
    create_extend_in_transaction_task,
    create_extend_out_transaction_task,
    create_release_transaction_task,
    end_users_staking_task,
    extend_stakings_task,
    fetch_reward_task,
    pay_rewards_task,
    release_users_assets_task,
    stake_assets_task,
    system_approve_stake_amount_task,
)


class UpdatePlansCron(CronJob):
    schedule = Schedule(run_every_mins=5 if settings.ENV == 'prod' else 1)
    code = 'update_staking_plans_cron'

    def run(self):
        tasks_per_plan = defaultdict(list)

        for plan_id in Plan.get_plan_ids_to_stake():
            tasks_per_plan[plan_id].append(stake_assets_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_assign_staking_to_users():
            tasks_per_plan[plan_id].append(assign_staking_to_users_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_end_its_user_staking():
            tasks_per_plan[plan_id].append(end_users_staking_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_release_its_user_assets():
            tasks_per_plan[plan_id].append(release_users_assets_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_approve_stake_amount():
            tasks_per_plan[plan_id].append(system_approve_stake_amount_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_fetch_rewards():
            tasks_per_plan[plan_id].append(fetch_reward_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_announce_rewards():
            tasks_per_plan[plan_id].append(announce_rewards_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_pay_rewards():
            tasks_per_plan[plan_id].append(pay_rewards_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_create_extend_out_transaction():
            tasks_per_plan[plan_id].append(create_extend_out_transaction_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_extend_staking():
            tasks_per_plan[plan_id].append(create_extend_in_transaction_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_extend_users_assets():
            tasks_per_plan[plan_id].append(extend_stakings_task.si(plan_id))

        for plan_id in Plan.get_plan_ids_to_create_release_transaction():
            tasks_per_plan[plan_id].append(create_release_transaction_task.si(plan_id))

        for plan_id, tasks in tasks_per_plan.items():
            chain(*tasks).apply_async()


class UserWatchCron(CronJob):
    schedule = Schedule(run_every_mins=20)
    code = 'staking_user_watch_cron'

    def run(self):
        UserWatch.extend_watches()
        UserWatch.clean_up()
        for plan_id in Plan.get_open_plan_ids():
            UserWatch.notify_users(plan_id)
