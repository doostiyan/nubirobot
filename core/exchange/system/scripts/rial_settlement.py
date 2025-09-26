""" Helper methods for sending IRT withdraws
"""
import datetime
import time
import traceback

from django.utils.timezone import now

from exchange.accounts.models import BankAccount
from exchange.base.helpers import context_flag
from exchange.base.logging import report_exception
from exchange.base.models import RIAL, Settings
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.settlement import settle_withdraw

withdraws_retry_count = {}


def do_settlement(withdraw: WithdrawRequest, gateway: str, direct=False):
    """ Perform Rial settlement with the corresponding gateway API
    """
    settle_method = getattr(WithdrawRequest.SETTLE_METHOD, gateway, None)
    if settle_method is None:
        raise ValueError('Unknown gateway: "{}"'.format(gateway))

    is_vandar = withdraw.target_account.bank_id == BankAccount.BANK_ID.vandar if withdraw.target_account else False
    if is_vandar and settle_method != WithdrawRequest.SETTLE_METHOD.vandar:
        raise ValueError('Vandar withdraw cannot be processed with another gateway!')

    print('{} {} #{}'.format(gateway.upper(), 'DIRECT' if direct else 'ACH', withdraw.id))
    options = {}
    if gateway in ['jibit', 'jibit_v2']:
        can_withdraw_over_shaba_limit = withdraw.wallet.user.tags.filter(name='برداشت بیشتر از محدودیت شبا').exists() \
                                        and WithdrawRequest.is_over_shaba_limit(withdraw.wallet,
                                                                                withdraw.amount,
                                                                                withdraw.target_account,
                                                                                just_committed_statuses=True)
        submission_mode = 'BRANCH' if can_withdraw_over_shaba_limit else 'BATCH'
        options = {
            'cancellable': submission_mode == 'BRANCH',
            'transfer_mode': 'instant' if direct else 'ACH',
            'submission_mode': submission_mode,
        }
    return settle_withdraw(withdraw, settle_method, options=options)


def get_candid_withdraws(allow_small=False):
    """ Return all withdraws that can be settled
    """
    return WithdrawRequest.objects.filter(
        tp=WithdrawRequest.TYPE.normal,
        status__in=[WithdrawRequest.STATUS.verified, WithdrawRequest.STATUS.accepted],
        wallet__currency=RIAL,
        created_at__gte=now() - datetime.timedelta(hours=6),
        created_at__lte=now() - datetime.timedelta(minutes=3),
        amount__gte=0 if allow_small else 110000,
    )


def do_auto_settlement_round(reversed_order=False):
    """ Pick a withdraw and settle it
    """
    # Load options from Settings
    options = Settings.get_dict('rial_settlement')
    is_ayandeh_hourly_enabled = options.get('ayandeh_hourly_enabled') is True
    ayandeh_hourly_gateway = options.get('ayandeh_hourly_gateway', 'vandar')
    is_paya_enabled = options.get('paya_enabled') is True
    paya_gateway = options.get('paya_gateway', 'jibit_v2')
    is_direct_enabled = options.get('direct_enabled') is True
    direct_jibit_banks = options.get('direct_jibit_banks', [])
    direct_vandar_banks = options.get('direct_vandar_banks', [])
    direct_toman_banks = options.get('direct_toman_banks', [])
    direct_pay_saman_enabled = options.get('direct_pay_saman_enabled') is True
    send_small_amounts_with_pay = options.get('send_small_amounts_with_pay') is True
    excluded_banks = options.get('excluded_banks') or []
    excluded_users = options.get('excluded_users') or []
    excluded_withdraws = options.get('excluded_withdraws') or []
    # Select one withdraw and settle it based on module's parameters
    print('.', end=' ', flush=True)
    candid_withdraws = get_candid_withdraws(allow_small=send_small_amounts_with_pay)
    # Filter target banks if we are not sending all requests
    if not is_paya_enabled:
        selected_banks = []
        if is_direct_enabled:
            selected_banks += direct_jibit_banks
            selected_banks += direct_vandar_banks
            selected_banks += direct_toman_banks
            if direct_pay_saman_enabled:
                selected_banks.append(56)
        if is_ayandeh_hourly_enabled:
            selected_banks.append(62)
        candid_withdraws = candid_withdraws.filter(
            target_account__bank_id__in=selected_banks,
        )
    # Excluded banks
    if excluded_banks:
        candid_withdraws = candid_withdraws.exclude(
            target_account__bank_id__in=excluded_banks,
        )
    # Excluded users
    if excluded_users:
        candid_withdraws = candid_withdraws.exclude(
            wallet__user_id__in=excluded_users,
        )
    # Excluded withdraws
    if excluded_withdraws:
        candid_withdraws = candid_withdraws.exclude(
            id__in=excluded_withdraws,
        )
    # Select a single withdraw to send
    withdraw = candid_withdraws.order_by(
        ('-' if reversed_order else '') + 'created_at',
    ).first()
    # Wait when there is no request
    if not withdraw:
        print('No request, waiting...')
        time.sleep(60)
        return
    # Now Sending the selected withdraw
    try:
        # Accept verified withdraws
        if withdraw.status == withdraw.STATUS.verified:
            withdraw.status = withdraw.STATUS.accepted
            withdraw.save(update_fields=['status'])
        # Select gateway and do the settlement
        bank_id = withdraw.target_account.bank_id
        is_small_withdraw = withdraw.amount < 110000
        if is_small_withdraw and bank_id != 998:
            if send_small_amounts_with_pay:
                do_settlement(withdraw, 'payir')
            else:
                print('Small!', end=' ')
        elif is_direct_enabled and bank_id in direct_jibit_banks:
            do_settlement(withdraw, 'jibit_v2', direct=True)
        elif is_direct_enabled and bank_id in direct_vandar_banks:
            do_settlement(withdraw, 'vandar', direct=True)
        elif is_direct_enabled and bank_id in direct_toman_banks:
            do_settlement(withdraw, 'toman', direct=True)
        elif is_direct_enabled and bank_id == 56 and direct_pay_saman_enabled:
            do_settlement(withdraw, 'payir', direct=True)
        elif bank_id == 62 and is_ayandeh_hourly_enabled:
            do_settlement(withdraw, ayandeh_hourly_gateway, direct=True)
        else:
            if is_paya_enabled:
                do_settlement(withdraw, paya_gateway)
            else:
                print('PayaDisabled!', end=' ')
                time.sleep(20)
        print(withdraw.id, bank_id, withdraw.updates, '\n')
    except:
        traceback.print_exc()
        report_exception()
        wid = withdraw.id
        print('WithdrawFailed: #{}'.format(wid))
        withdraws_retry_count[wid] = withdraws_retry_count.get(wid, 0) + 1
        if withdraws_retry_count[wid] >= 3:
            options = Settings.get_dict('rial_settlement')
            excluded_withdraws = options.get('excluded_withdraws') or []
            excluded_withdraws.append(wid)
            options['excluded_withdraws'] = excluded_withdraws
            Settings.set_dict('rial_settlement', options)
        time.sleep(10)


@context_flag(NOTIFY_NON_ATOMIC_TX_COMMIT=False)
def run_rial_settlement(worker=1):
    """ Run Rial withdraw settlement daemon
    """
    is_worker2 = worker == 2
    i = 0
    while True:
        # Check if running more workers is needed
        if i == 0:
            if is_worker2:
                queue_len = get_candid_withdraws().count()
                if queue_len < 150:
                    print(f'Short queue ({queue_len}), waiting for 5m...')
                    time.sleep(300)
                    continue
                print('Queue Len:', queue_len)
        # Run a settlement round
        try:
            do_auto_settlement_round(reversed_order=is_worker2)
        except KeyboardInterrupt:
            print('Interrupted.')
            break
        except:
            # The method should handle common exceptions, so any exception here
            # means there is something wrong and should be manually inspected
            traceback.print_exc()
            report_exception()
            print('Waiting for 1m due to unexpected exception...')
            time.sleep(60)
        i = (i + 1) % 50
