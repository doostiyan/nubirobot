from exchange.asset_backed_credit.models import Service

SERVICE_PROVIDERS_HELP_LINK = {
    Service.PROVIDERS.tara: 'https://nobitex.ir/help/discover/credit/activating-credit-purchasing/',
    Service.PROVIDERS.digipay: 'https://nobitex.ir/help/discover/credit/activating-credit-digipay/',
}

SERVICE_TYPES_HELP_LINK = {
    Service.TYPES.credit: 'https://nobitex.ir/help/discover/credit/',
    Service.TYPES.loan: 'https://nobitex.ir/help/discover/loan/',
}

DEFAULT_HELP_LINK = 'https://nobitex.ir/help/'


def get_service_activation_help_link_data(service: Service) -> str:
    if service.provider in SERVICE_PROVIDERS_HELP_LINK:
        return SERVICE_PROVIDERS_HELP_LINK[service.provider]

    if service.tp in SERVICE_TYPES_HELP_LINK:
        return SERVICE_TYPES_HELP_LINK[service.tp]

    return DEFAULT_HELP_LINK
