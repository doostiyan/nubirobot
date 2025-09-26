import functools
from random import random

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Case, Q, When
from django.db.models.fields import IntegerField
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.generic.list import MultipleObjectMixin
from django_ratelimit.decorators import ratelimit
from rest_framework.viewsets import ViewSetMixin

from exchange.base.api import APIView, NobitexAPIError, ParseError, PublicAPIView, SemanticAPIError
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import build_frontend_url, paginate
from exchange.base.models import Settings
from exchange.base.parsers import parse_date, parse_int, parse_money, parse_str
from exchange.direct_debit.api.permissions import validate_user_eligibility
from exchange.direct_debit.exceptions import (
    ContractIntegrityError,
    ContractStatusError,
    DailyMaxTransactionCountError,
    DirectDebitBankNotActiveError,
    DirectDebitBankNotFoundError,
    MaxAmountBankExceededError,
    MaxAmountExceededError,
    MaxDailyAmountExceededError,
    MaxDailyCountExceededError,
    MaxTransactionAmountError,
    MinAmountNotMetError,
    StatusUnchangedError,
    ThirdPartyClientError,
    ThirdPartyConnectionError,
    ThirdPartyError,
)
from exchange.direct_debit.models import ContractStatus, DirectDebitBank, DirectDebitContract
from exchange.direct_debit.tasks import direct_debit_activate_contract_task
from exchange.features.utils import BetaFeatureMixin


class DirectDebitView(BetaFeatureMixin, ViewSetMixin, APIView):
    feature = 'direct_debit'


class DirectDebitBankView(MultipleObjectMixin, DirectDebitView):
    model = DirectDebitBank
    ordering = ('-created_at', 'daily_max_transaction_amount')

    @method_decorator(ratelimit(key='user_or_ip', rate='50/m', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitListBanks'))
    def get(self, request):
        return self.response({'status': 'ok', 'banks': self.get_queryset()})


class DirectDebitContractView(DirectDebitView):
    @method_decorator(ratelimit(key='ip', rate='30/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitListContracts'))
    def get(self, request):
        contracts = DirectDebitContract.objects.filter(user=request.user).select_related('bank')
        contracts = self._apply_status_filter(request, contracts)
        contracts = (
            contracts.annotate_today_transaction_count()
            .annotate_today_transaction_amount()
            .exclude(
                status__in=[
                    DirectDebitContract.STATUS.waiting_for_update,
                    DirectDebitContract.STATUS.failed_update,
                ]
            )
            .order_by('-created_at')
        )
        contracts = self._order_contracts(contracts)

        response_data = self._get_paginated_response(request, contracts)
        return self.response(response_data, opts={'bank_name_only': True})

    @staticmethod
    def _apply_status_filter(request, contracts):
        status_filter = request.GET.get('status')
        if not status_filter:
            return contracts
        filter_statuses = [s.strip() for s in status_filter.split(',') if s.strip()]
        lower_to_internal = {
            display_text.lower(): internal_status
            for internal_status, display_text in DirectDebitContract.STATUS._display_map.items()
        }
        valid_internal_statuses = [
            lower_to_internal[s.lower()] for s in filter_statuses if s.lower() in lower_to_internal
        ]
        if not valid_internal_statuses:
            return contracts
        return contracts.filter(status__in=valid_internal_statuses)

    @staticmethod
    def _order_contracts(contracts):
        return contracts.annotate(
            status_order=Case(
                When(status=DirectDebitContract.STATUS.active, then=0),  # Actives first
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('status_order', '-created_at')

    def _get_paginated_response(self, request, contracts):
        page = request.GET.get('page')
        page_size = request.GET.get('pageSize')
        paginated = page or page_size

        if paginated:
            contracts, has_next = paginate(
                data=contracts,
                page=page or 1,
                page_size=page_size or 50,
                request=self,
                check_next=True,
            )
            return {
                'status': 'ok',
                'contracts': contracts,
                'has_next': has_next,
            }
        return {'status': 'ok', 'contracts': contracts}


class DirectDebitCreateContractView(DirectDebitView):
    @method_decorator(ratelimit(key='user_or_ip', method='POST', rate='60/h', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitCreateContract'))
    def post(self, request, *args, **kwargs):
        validate_user_eligibility(request.user)

        user = request.user
        message = None
        code = None
        status_code = 400

        bank_id = parse_int(self.g('bankId'), required=True)
        from_date = parse_date(self.g('fromDate'))
        to_date = parse_date(self.g('toDate'), required=True)
        daily_max_transaction_count = parse_int(self.g('dailyMaxTransactionCount'), required=True)
        max_transaction_amount = parse_money(self.g('maxTransactionAmount'), required=True)
        from exchange.direct_debit.exceptions import ContractEndDateError, ContractStartDateError

        try:
            with transaction.atomic():
                contract = DirectDebitContract.create(
                    user=user,
                    bank_id=bank_id,
                    from_date=from_date,
                    to_date=to_date,
                    daily_max_transaction_count=daily_max_transaction_count,
                    max_transaction_amount=max_transaction_amount,
                )
                if contract and contract.location:
                    return self.response(
                        {
                            'status': 'ok',
                            'location': contract.location,
                        }
                    )
        except ThirdPartyError as e:
            raise e.convert_to_api_error() from e
        except DirectDebitBankNotFoundError:
            code = 'DirectDebitBankNotFoundError'
            message = 'You choose an invalid bank!'
            status_code = 404
        except DirectDebitBankNotActiveError:
            code = 'DeactivatedBankError'
            message = 'The bank is not active'
            status_code = 422
        except ThirdPartyClientError:
            code = 'ThirdPartyClientError'
            message = 'An error occurred when trying to connect to third-party API'
            status_code = 503
        except ThirdPartyConnectionError:
            code = 'ThirdPartyConnectionError'
            message = 'Third-party has connection error!'
            status_code = 503
        except MaxTransactionAmountError:
            code = 'MaxTransactionAmountError'
            message = 'Max transaction amount is more than the bank limit!'
        except DailyMaxTransactionCountError:
            code = 'DailyMaxTransactionCountError'
            message = 'Daily max transaction count is more than the bank limit!'
        except ContractStartDateError:
            code = 'FromDateInvalidError'
            message = 'fromDate should be greater than now'
        except ContractEndDateError:
            code = 'ToDateInvalidError'
            message = 'toDate should be greater than the fromDate'
        except ContractIntegrityError:
            code = 'ContractIntegrityError'
            message = 'The user has an active contract with this bank'
            status_code = 422

        raise NobitexAPIError(message=code, description=message, status_code=status_code)


class ContractCallbackView(PublicAPIView):
    @method_decorator(ratelimit(key='user_or_ip', method='GET', rate='100/m', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitCreateContractCallback'))
    def get(self, request, trace_id, *args, **kwargs):
        template_name = 'direct_debit_callback.html'
        retry_action_button_url = build_frontend_url(request, '/panel/profile/bank-info/direct-debit/create/')
        retry_action_button_text = 'تلاش دوباره'
        setting_button_url = build_frontend_url(request, '/panel/profile/bank-info/direct-debit/')
        deposit_button_url = build_frontend_url(request, '/panel/balance/deposit/direct-debit/')
        deposit_button_text = 'برو به واریز'
        default_context = {
            'button_url': retry_action_button_url,
            'button_text': retry_action_button_text,
            'setting_button_url': setting_button_url,
            'page_title': 'ایجاد قرارداد ناموفق',
            'title': '',
            'message': '',
        }

        try:
            contract_code = parse_str(self.g('payman_code'), required=True)
            status = parse_str(self.g('status'), required=True).upper()
            contract = DirectDebitContract.objects.select_for_update(of=('self',)).get(
                trace_id=trace_id,
                status=DirectDebitContract.STATUS.initializing,
            )
        except (ParseError, DirectDebitContract.DoesNotExist):
            default_context['title'] = 'ایجاد قرارداد ناموفق بود'
            default_context['message'] = 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.'
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        if contract.status != DirectDebitContract.STATUS.initializing:  # TODO: should be deleted; it can never be true
            default_context['title'] = 'قرارداد تکراری است'
            default_context[
                'message'
            ] = 'قبلا قرارداد واریز مستقیم برای این بانک را ایجاد کرده‌اید و از «مدیریت قراردادها» در دسترس است.'
            default_context['button_url'] = deposit_button_url
            default_context['button_text'] = deposit_button_text
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        if status == 'CREATED':
            with transaction.atomic():
                contract.contract_code = contract_code
                contract.status = DirectDebitContract.STATUS.waiting_for_confirm
                contract.save(update_fields=['contract_code', 'status'])
                transaction.on_commit(
                    functools.partial(
                        direct_debit_activate_contract_task.apply_async,
                        args=(contract.id, 0),
                    )
                )
            default_context['page_title'] = 'ایجاد قرارداد موفق'
            default_context['status'] = 'success'
            default_context['title'] = 'قرارداد با موفقیت ایجاد شد'
            default_context['button_url'] = deposit_button_url
            default_context['button_text'] = deposit_button_text
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        if status == 'CANCELED':
            contract.cancel()
            contract.notify_on_error()
            default_context['title'] = 'قرارداد لغو شد'
            default_context['button_url'] = deposit_button_url
            default_context['button_text'] = deposit_button_text
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        contract.status = DirectDebitContract.STATUS.failed
        contract.save(update_fields=['status'])
        contract.notify_on_error()

        title = 'ایجاد قرارداد ناموفق بود'
        if status == 'INTERNAL_ERROR':
            message = 'خطای فنی در هنگام ایجاد قرارداد رخ داده است. لطفا دقایقی بعد مجددا تلاش کنید.'
        else:  # timeout and unknown statuses
            message = 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.'

        default_context['title'] = title
        default_context['message'] = message
        return render(
            request=self.request,
            template_name=template_name,
            context=default_context,
        )


class DirectDebitDepositView(DirectDebitView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitDeposit'))
    def post(self, request):
        validate_user_eligibility(request.user)

        contract = parse_int(self.g('contract'), required=True)
        amount = parse_money(self.g('amount'), required=True)
        try:
            contract = DirectDebitContract.objects.select_related('bank').get(
                pk=contract,
                user=request.user,
                status=DirectDebitContract.STATUS.active,
                expires_at__gte=ir_now(),
                started_at__lte=ir_now(),
            )

            throttled_banks = Settings.get_cached_json(
                'direct_debit_throttled_banks',
                {
                    'BKMTIR': 0.1,
                },
            )

            is_bank_throttled = throttled_banks.get(contract.bank.bank_id, 1) < random()

            if not contract.bank.is_active or is_bank_throttled:
                raise NobitexAPIError(
                    message='DeactivatedBankError',
                    description='The bank is not active',
                    status_code=422,
                )

        except ObjectDoesNotExist as e:
            raise NobitexAPIError(
                status_code=404,
                message='ContractDoesNotExist',
                description='Contract does not exist.',
            ) from e

        try:
            deposit = contract.deposit(amount)
        except ThirdPartyError as e:
            raise e.convert_to_api_error() from e
        except ThirdPartyClientError as e:
            raise NobitexAPIError(
                status_code=503,
                message='ThirdPartyClientError',
                description='An error occurred when trying to connect to third-party API',
            ) from e
        except MaxDailyAmountExceededError as e:
            raise NobitexAPIError(
                status_code=400,
                message='DailyAmountExceededError',
                description='The amount is out of range of the total daily amount in your contract.',
            ) from e
        except MaxDailyCountExceededError as e:
            raise NobitexAPIError(
                status_code=400,
                message='DailyCountExceededError',
                description='The number of transactions is out of range of the total daily amount in your contract.',
            ) from e
        except MaxAmountExceededError as e:
            raise NobitexAPIError(
                status_code=400,
                message='MaxAmountExceededError',
                description='The amount of transactions is greater '
                'than the maximum transaction amount in your contract.',
            ) from e
        except MaxAmountBankExceededError as e:
            raise NobitexAPIError(
                status_code=400,
                message='MaxAmountBankExceededError',
                description='The amount of transactions is greater than the bank maximum transaction amount.',
            ) from e
        except MinAmountNotMetError as e:
            raise NobitexAPIError(
                status_code=400,
                message='MinAmountNotMetError',
                description='The amount of transactions is lower than the minimum transaction amount',
            ) from e
        return self.response(
            {
                'status': 'ok',
                'deposit': deposit,
            },
            opts={
                'bank_name_only': True,
            },
        )


class DirectDebitEditContractView(DirectDebitView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitEditContractStatus'))
    def change_status(self, request, pk: int):
        new_status = parse_str(self.g('newStatus'), required=True)
        if new_status != DirectDebitContract.STATUS.cancelled:
            validate_user_eligibility(request.user)

        try:
            contract = (
                DirectDebitContract.objects.select_for_update(of=('self',))
                .select_related('bank')
                .get(
                    Q(user=request.user),
                    Q(pk=pk),
                    ~Q(status=ContractStatus.replaced),
                )
            )
            contract.change_status(new_status)
        except ThirdPartyError as e:
            raise e.convert_to_api_error() from e
        except ParseError as e:
            raise NobitexAPIError(
                status_code=400,
                message='NewStatusValidationError',
                description='The new_status is not valid!',
            ) from e
        except ThirdPartyClientError as e:
            raise NobitexAPIError(
                status_code=503,
                message='ThirdPartyClientError',
                description='An error occurred when trying to connect to third-party API',
            ) from e
        except ValueError as e:
            raise NobitexAPIError(
                status_code=400,
                message='ValueError',
                description=str(e),
            ) from e
        except ContractStatusError as e:
            raise SemanticAPIError(
                message='InvalidStatusError',
                description='Current contract status is not changeable',
            ) from e
        except StatusUnchangedError as e:
            raise SemanticAPIError(
                message='ThirdPartyError',
                description='The third-party could not change the status',
            ) from e
        except ContractIntegrityError as e:
            raise NobitexAPIError(
                status_code=400,
                message='ContractIntegrityError',
                description='The user has an active contract with this bank',
            ) from e
        except DirectDebitContract.DoesNotExist as e:
            raise NobitexAPIError(
                status_code=404,
                message='ContractDoesNotExist',
                description='Contract does not exist.',
            ) from e
        except DirectDebitBankNotActiveError as e:
            raise NobitexAPIError(
                message='DeactivatedBankError',
                description='The bank is not active',
                status_code=422,
            ) from e

        return self.response(
            {'status': 'ok', 'contract': contract},
        )

    @method_decorator(ratelimit(key='user_or_ip', method='PUT', rate='60/h', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitEditContract'))
    def update_contract(self, request, pk: int, *args, **kwargs):
        from exchange.direct_debit.exceptions import ContractEndDateError

        validate_user_eligibility(request.user)

        contract = get_object_or_404(
            DirectDebitContract, status=DirectDebitContract.STATUS.active, user=request.user, pk=pk
        )

        if not contract.bank.is_active:
            raise NobitexAPIError(
                message='DeactivatedBankError',
                description='The bank is not active',
                status_code=422,
            )

        waiting_contract = DirectDebitContract.objects.filter(
            contract_code=contract.contract_code, status=DirectDebitContract.STATUS.waiting_for_update
        ).first()

        if waiting_contract:
            raise NobitexAPIError(
                message='ContractCannotBeUpdatedError',
                description='There is already a waiting contract',
                status_code=409,
            )

        to_date = parse_date(self.g('toDate'))
        daily_max_transaction_count = parse_int(self.g('dailyMaxTransactionCount'))
        max_transaction_amount = parse_money(self.g('maxTransactionAmount'))

        params = {}

        if to_date and to_date.date() != contract.expires_at.date():
            params['expires_at'] = to_date
        if daily_max_transaction_count and daily_max_transaction_count != contract.daily_max_transaction_count:
            params['daily_max_transaction_count'] = daily_max_transaction_count
        if max_transaction_amount and max_transaction_amount != contract.max_transaction_amount:
            params['max_transaction_amount'] = max_transaction_amount

        message = None
        code = None
        status_code = 400

        if not params:
            message = 'No changes detected'
            code = 'InvalidParams'
            status_code = 400
        else:
            try:
                with transaction.atomic():
                    location = contract.update_contract(**params)
                    if location:
                        return self.response(
                            {
                                'status': 'ok',
                                'location': location,
                            }
                        )
            except ThirdPartyError as e:
                raise e.convert_to_api_error() from e
            except ThirdPartyClientError:
                code = 'ThirdPartyClientError'
                message = 'An error occurred when trying to connect to third-party API'
                status_code = 503
            except ThirdPartyConnectionError:
                code = 'ThirdPartyConnectionError'
                message = 'Third-party client has connection error!'
                status_code = 503
            except DailyMaxTransactionCountError:
                code = 'DailyMaxTransactionCountError'
                message = 'Daily max transaction count is more than the bank limit!'
            except MaxTransactionAmountError:
                code = 'MaxTransactionAmountError'
                message = 'Max transaction amount is more than the bank limit!'
            except ContractEndDateError:
                code = 'ToDateInvalidError'
                message = 'toDate should be greater than now'

        raise NobitexAPIError(message=code, description=message, status_code=status_code)


class UpdateContractCallbackView(PublicAPIView):
    @method_decorator(ratelimit(key='user_or_ip', method='GET', rate='100/m', block=True))
    @method_decorator(measure_api_execution(api_label='directdebitUpdateContractCallback'))
    def get(self, request, trace_id, *args, **kwargs):
        template_name = 'direct_debit_callback.html'
        retry_action_button_url = ''
        retry_action_button_text = 'تلاش دوباره'
        setting_button_url = build_frontend_url(request, '/panel/profile/bank-info/direct-debit/')
        deposit_button_url = build_frontend_url(request, '/panel/balance/deposit/direct-debit/')
        deposit_button_text = 'برو به واریز'
        default_context = {
            'button_url': retry_action_button_url,
            'button_text': retry_action_button_text,
            'setting_button_url': setting_button_url,
            'page_title': 'ویرایش قرارداد ناموفق',
            'title': '',
            'message': '',
        }

        try:
            status = parse_str(self.g('status'), required=True).upper()
            contract = DirectDebitContract.objects.get(
                status=DirectDebitContract.STATUS.waiting_for_update, trace_id=trace_id
            )
            default_context['button_url'] = build_frontend_url(
                request, f'/panel/profile/bank-info/direct-debit/{contract.id}/'
            )
        except (ParseError, DirectDebitContract.DoesNotExist):
            default_context['title'] = 'ویرایش قرارداد ناموفق بود'
            default_context['message'] = 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.'
            default_context['button_url'] = ''  # disable the button
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        if status == 'UPDATED':
            old_contract = DirectDebitContract.objects.filter(
                contract_code=contract.contract_code, status=DirectDebitContract.STATUS.active
            ).first()
            if not old_contract:
                contract.cancel()
                contract.notify_edit_failed()
                default_context['title'] = 'ویرایش قرارداد ناموفق بود'
                default_context['message'] = 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.'
                return render(
                    request=self.request,
                    template_name=template_name,
                    context=default_context,
                )
            with transaction.atomic():
                old_contract.status = DirectDebitContract.STATUS.replaced
                old_contract.save(update_fields=['status'])
                contract.status = DirectDebitContract.STATUS.active
                contract.save(update_fields=['status'])
                contract.notify_edited_successfully(old_contract)

                default_context['page_title'] = 'ویرایش قرارداد موفق'
                default_context['status'] = 'success'
                default_context['title'] = 'قرارداد با موفقیت ویرایش شد'
                default_context['button_url'] = deposit_button_url
                default_context['button_text'] = deposit_button_text

                return render(
                    request=self.request,
                    template_name=template_name,
                    context=default_context,
                )

        if status == 'CANCELED':
            contract.cancel()
            contract.notify_edit_failed()
            default_context['title'] = 'ویرایش قرارداد لغو شد'
            default_context['button_url'] = deposit_button_url
            default_context['button_text'] = deposit_button_text
            return render(
                request=self.request,
                template_name=template_name,
                context=default_context,
            )

        contract.status = DirectDebitContract.STATUS.failed
        contract.save(update_fields=['status'])
        contract.notify_edit_failed()

        title = 'ویرایش قرارداد موفقیت آمیز نبود'
        if status == 'INTERNAL_ERROR':
            message = 'خطای فنی در هنگام ویرایش قرارداد رخ داده است. لطفا دقایقی بعد مجددا تلاش کنید.'
        else:  # timeout and unknown statuses
            message = 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.'

        default_context['title'] = title
        default_context['message'] = message
        return render(
            request=self.request,
            template_name=template_name,
            context=default_context,
        )
