"""Metric keys are defined here."""
import enum


class Metrics(enum.Enum):
    # Update cron queries metrics:
    PLANS_TO_CREATE_CHECK_STAKE_AMOUNT_TRANSACTION_QUERY_TIME = \
        'query_plansToCreateCheckStakeAmountTransaction'
    PLANS_TO_STAKE_QUERY_TIME = 'query_plansToStake'
    PLANS_TO_ASSIGN_STAKING_TO_USERS_QUERY_TIME = 'query_plansToAssignQueryToUsers'
    PLANS_TO_END_ITS_USER_STAKING_QUERY_TIME = 'query_plansToEndItsUser'
    PLANS_TO_RELEASE_ITS_USER_ASSETS_QUERY_TIME = 'query_plansToReleaseItsUserAssets'
    PLANS_TO_APPROVE_STAKE_AMOUNT_QUERY_TIME = 'query_plansToApproveStakeAmount'
    PLANS_TO_FETCH_REWARDS_QUERY_TIME = 'query_plansToFetchRewards'
    PLANS_TO_ANNOUNCE_REWARDS_QUERY_TIME = 'query_plansToAnnounceRewards'
    PLANS_TO_PAY_REWARDS_QUERY_TIME = 'query_plansToPayRewards'
    PLANS_TO_CREATE_EXTEND_OUT_TRANSACTION_QUERY_TIME = 'query_plansToCreateExtendOutTransaction'
    PLANS_TO_EXTEND_STAKING_QUERY_TIME = 'query_plansToExtend'
    PLANS_TO_EXTEND_USERS_ASSETS_QUERY_TIME = 'query_plansToExtendUsersAssets'
    PLANS_TO_CREATE_RELEASE_TRANSACTION_QUERY_TIME = 'query_plansToCreateReleaseTransaction'
    USERS_TO_APPLY_END_REQUESTS_QUERY_TIME = 'query_UsersToApplyInstantEndRequests'

    # Waiting for DB lock Metrics:
    STAKING_LOCK_WAIT_TIME = 'dbLockWait_staking'
    PLAN_LOCK_WAIT_TIME = 'dbLockWait_plan'

    # Tasks
    TASK_STAKE_ASSETS_TIME = 'task_stakeAssets'
    TASK_ASSIGN_USER_STAKING_TIME = 'task_assignStakingToUsers'
    TASK_END_USER_STAKING_TIME = 'task_endUserStaking'
    TASK_RELEASE_USER_ASSETS_TIME = 'task_releaseUserAssets'
    TASK_SYSTEM_APPROVE_STAKE_AMOUNT_TIME = 'task_systemApproveStakeAmount'
    TASK_FETCH_REWARD_TIME = 'task_fetchReward'
    TASK_ANNOUNCE_REWARD_TIME = 'task_announceReward'
    TASK_PAY_REWARD_TIME = 'task_payReward'
    TASK_CREATE_EXTEND_OUT_TIME = 'task_createExtendOutTransaction'
    TASK_CREATE_EXTEND_IN_TIME = 'task_createExtendInTransaction'
    TASK_EXTEND_STAKING_TIME = 'task_extendStaking'
    TASK_CREATE_RELEASE_TRX_TIME = 'task_createReleaseTransaction'

    # External
    EXTERNAL_STAKE_FETCH_REWARD_TIME = 'external_stakeFetchReward'

    # Notifications
    NOTIFICATION_USER_WATCH_PLAN_CAPACITY_INCREASE_TIME = 'notification_userWatchPlanCapacityIncrease'
    NOTIFICATION_SEND_USER_NOTIFICATION_TIME = 'notification_sendUserNotification'

    def __str__(self) -> str:
        return 'staking__' + self.value
