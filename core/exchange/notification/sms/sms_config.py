from enum import Enum

from exchange.accounts.sms_templates import OLD_SMSIR_TEMPLATES


class SmsProvider(Enum):
    OLD_SMSIR = 'OldSmsir'
    NEW_SMSIR = 'NewSmsir'
    FINNOTEXT = 'Finnotext'
    KAVENEGAR = 'Kavenegar'
    DEFAULT = 'OldSmsir'


GENERAL_AGGREGATED_LOAD_BALANCER_PER_TEMPLATE = {
    SmsProvider.KAVENEGAR.value: 0,
    SmsProvider.NEW_SMSIR.value: 0.6,
    SmsProvider.FINNOTEXT.value: 0.9,
    SmsProvider.OLD_SMSIR.value: 1,
}


NO_TEMPLATE_AGGREGATED_LOAD_BALANCER = {
    SmsProvider.KAVENEGAR.value: 0,
    SmsProvider.NEW_SMSIR.value: 0,
    SmsProvider.FINNOTEXT.value: 0,
    SmsProvider.OLD_SMSIR.value: 1,
}


AGGREGATED_LOAD_BALANCER = {
    template_name: GENERAL_AGGREGATED_LOAD_BALANCER_PER_TEMPLATE
    for template_name in OLD_SMSIR_TEMPLATES._identifier_map
}
AGGREGATED_LOAD_BALANCER['default'] = NO_TEMPLATE_AGGREGATED_LOAD_BALANCER


SMS_PROVIDER_LOAD_BALANCER_CONFIG_key = 'sms_provider_load_balancer_config'
