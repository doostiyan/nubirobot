from typing import Dict

from django.db import models
from model_utils import Choices

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ServiceLimitNotSet
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.asset_backed_credit.types import UserServiceLimit
from .service import Service

_LIMIT_TYPES = Choices(
    (10, 'user', 'User'),
    (20, 'user_service', 'User Service'),
    (30, 'user_service_provider', 'User ServiceProvider'),
    (40, 'user_service_type', 'User ServiceType'),
    (50, 'user_type', 'UserType'),
    (60, 'user_type_service', 'UserType Service'),
    (70, 'user_type_service_provider', 'UserType ServiceProvider'),
    (80, 'user_type_service_type', 'UserType ServiceType'),
    (90, 'service', 'Service'),
    (100, 'service_provider', 'ServiceProvider'),
    (110, 'service_type', 'ServiceType'),
)


class UserFinancialServiceLimit(models.Model):
    """Model representing financial service limits for users.

    This model defines three types of limits in order:

    1. Per User
    2. Per User and Service
    3. Per Service and User Type
    4. Per Service

    Fields:
        - user (ForeignKey): Reference to the user for whom the limit is defined.
        - service (ForeignKey): Reference to the service associated with the limit.
        - user_type (SmallIntegerField): Type of user (choices specified by User.USER_TYPES).
        - limit (DecimalField): The actual numerical limit.
    """

    TYPE = Choices(
        (1, 'user', 'User'),
        (2, 'user_service', 'UserService'),
        (3, 'service_user_type', 'ServiceUserType'),
        (4, 'service', 'Service'),
    )

    SEARCH_FIELDS_ORDERED = ('user', 'user_type', 'service', 'service_provider', 'service_type')
    TYPES = _LIMIT_TYPES

    tp = models.SmallIntegerField(choices=TYPES)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    internal_user = models.ForeignKey(InternalUser, null=True, blank=True, on_delete=models.CASCADE)
    user_type = models.SmallIntegerField(choices=User.USER_TYPES, null=True, blank=True)
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE)
    service_provider = models.SmallIntegerField(choices=Service.PROVIDERS, null=True, blank=True)
    service_type = models.SmallIntegerField(choices=Service.TYPES, null=True, blank=True)
    min_limit = models.PositiveBigIntegerField(null=True, blank=True)
    limit = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='abc_%(class)s_unique_user_limit',
                condition=models.Q(
                    user_type__isnull=True,
                    service__isnull=True,
                    service_provider__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user', 'service'],
                name='abc_%(class)s_unique_user_service_limit',
                condition=models.Q(
                    user_type__isnull=True,
                    service_provider__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user', 'service_provider'],
                name='abc_%(class)s_unique_user_service_provider_limit',
                condition=models.Q(
                    user_type__isnull=True,
                    service__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user', 'service_type'],
                name='abc_%(class)s_unique_user_service_type_limit',
                condition=models.Q(
                    user_type__isnull=True,
                    service__isnull=True,
                    service_provider__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user_type'],
                name='abc_%(class)s_unique_user_type_limit',
                condition=models.Q(
                    user__isnull=True,
                    service__isnull=True,
                    service_provider__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user_type', 'service'],
                name='abc_%(class)s_unique_user_type_service_limit',
                condition=models.Q(
                    user__isnull=True,
                    service_provider__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user_type', 'service_provider'],
                name='abc_%(class)s_unique_user_type_service_provider_limit',
                condition=models.Q(
                    user__isnull=True,
                    service__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['user_type', 'service_type'],
                name='abc_%(class)s_unique_user_type_service_type_limit',
                condition=models.Q(
                    user__isnull=True,
                    service__isnull=True,
                    service_provider__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['service'],
                name='abc_%(class)s_unique_service_limit',
                condition=models.Q(
                    user__isnull=True,
                    user_type__isnull=True,
                    service_provider__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['service_provider'],
                name='abc_%(class)s_unique_service_provider_limit',
                condition=models.Q(
                    user__isnull=True,
                    user_type__isnull=True,
                    service__isnull=True,
                    service_type__isnull=True,
                ),
            ),
            models.UniqueConstraint(
                fields=['service_type'],
                name='abc_%(class)s_unique_service_type_limit',
                condition=models.Q(
                    user__isnull=True,
                    user_type__isnull=True,
                    service__isnull=True,
                    service_provider__isnull=True,
                ),
            ),
            models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        tp=_LIMIT_TYPES.user,
                        user__isnull=False,
                        user_type__isnull=True,
                        service__isnull=True,
                        service_provider__isnull=True,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_service,
                        user__isnull=False,
                        user_type__isnull=True,
                        service__isnull=False,
                        service_provider__isnull=True,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_service_provider,
                        user__isnull=False,
                        user_type__isnull=True,
                        service__isnull=True,
                        service_provider__isnull=False,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_service_type,
                        user__isnull=False,
                        user_type__isnull=True,
                        service__isnull=True,
                        service_provider__isnull=True,
                        service_type__isnull=False,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_type,
                        user__isnull=True,
                        user_type__isnull=False,
                        service__isnull=True,
                        service_provider__isnull=True,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_type_service,
                        user__isnull=True,
                        user_type__isnull=False,
                        service__isnull=False,
                        service_provider__isnull=True,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_type_service_provider,
                        user__isnull=True,
                        user_type__isnull=False,
                        service__isnull=True,
                        service_provider__isnull=False,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.user_type_service_type,
                        user__isnull=True,
                        user_type__isnull=False,
                        service__isnull=True,
                        service_provider__isnull=True,
                        service_type__isnull=False,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.service,
                        user__isnull=True,
                        user_type__isnull=True,
                        service__isnull=False,
                        service_provider__isnull=True,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.service_provider,
                        user__isnull=True,
                        user_type__isnull=True,
                        service__isnull=True,
                        service_provider__isnull=False,
                        service_type__isnull=True,
                    ),
                    models.Q(
                        tp=_LIMIT_TYPES.service_type,
                        user__isnull=True,
                        user_type__isnull=True,
                        service__isnull=True,
                        service_provider__isnull=True,
                        service_type__isnull=False,
                    ),
                    _connector=models.Q.OR,
                ),
                name='abc_%(class)s_null_checks_per_limit_type',
            ),
            models.CheckConstraint(
                check=models.Q(min_limit__lte=models.F('limit')),
                name='abc_%(class)s_min_limit_lte_limit',
            ),
            models.CheckConstraint(
                check=models.Q(min_limit__isnull=False, limit__isnull=False, _connector=models.Q.OR),
                name='abc_%(class)s_null_checks_on_min_max_limit',
            )
        ]

    @classmethod
    def get_user_limits_per_service(cls, user: User) -> Dict[int, UserServiceLimit]:
        q_user = models.Q(user_id=user.pk)
        q_user_type = models.Q(user_type=user.user_type)
        q_services = models.Q(user__isnull=True, user_type__isnull=True)
        query = q_user | q_user_type | q_services
        limits = list(cls.objects.filter(query).order_by(*cls.SEARCH_FIELDS_ORDERED))
        return cls._get_limits_per_service(limits=limits)

    @classmethod
    def get_limits_per_service(cls):
        limits = list(
            cls.objects.filter(user__isnull=True, user_type__isnull=True).order_by(*cls.SEARCH_FIELDS_ORDERED)
        )
        return cls._get_limits_per_service(limits=limits)

    @classmethod
    def _get_limits_per_service(cls, limits) -> Dict[int, UserServiceLimit]:
        services = set(limit.service for limit in limits if limit.service)
        services = {service.pk: {'service': service, 'limits': []} for service in services}

        for limit in limits:
            if limit.service_id:
                services[limit.service_id]['limits'].append(limit)
            elif limit.service_provider:
                for service_id in services.keys():
                    if services[service_id]['service'].provider == limit.service_provider:
                        services[service_id]['limits'].append(limit)
            elif limit.service_type:
                for service_id in services.keys():
                    if services[service_id]['service'].tp == limit.service_type:
                        services[service_id]['limits'].append(limit)
            else:
                for service_id in services.keys():
                    services[service_id]['limits'].append(limit)

        result = {}
        for service_id, data in services.items():
            service_limits = data['limits']
            if not cls._is_service_limits_set(service_limits, data['service']):
                raise ServiceLimitNotSet('Service limit is not set.')

            min_limit, max_limit = cls._get_min_max_limits(service_limits)
            result[service_id] = UserServiceLimit(min_limit=min_limit, max_limit=max_limit)

        return result

    @classmethod
    def get_user_service_limit(cls, user, service) -> UserServiceLimit:
        user_type = user.user_type
        service_provider = service.provider
        service_type = service.tp
        search_filters = [
            {'user': user},
            {'user_type': user_type},
            {'user': user, 'service': service},
            {'user': user, 'service_provider': service_provider},
            {'user': user, 'service_type': service_type},
            {'user_type': user_type, 'service': service},
            {'user_type': user_type, 'service_provider': service_provider},
            {'user_type': user_type, 'service_type': service_type},
            {'service': service},
            {'service_provider': service_provider},
            {'service_type': service_type},
        ]

        limits = cls._get_limits_list_by_search_filters(search_filters)
        if not cls._is_service_limits_set(limits, service):
            raise ServiceLimitNotSet('Service limit is not set.')

        min_limit, max_limit = cls._get_min_max_limits(limits)
        return UserServiceLimit(min_limit=min_limit, max_limit=max_limit)

    @classmethod
    def _get_limits_list_by_search_filters(cls, search_filters):
        q_list = [
            models.Q(**{field: _search_filter.get(field) for field in cls.SEARCH_FIELDS_ORDERED})
            for _search_filter in search_filters
        ]
        return cls.objects.filter(models.Q(*q_list, _connector=models.Q.OR)).order_by(*cls.SEARCH_FIELDS_ORDERED)

    @staticmethod
    def _is_service_limits_set(limits, service):
        is_min_limit_set, is_max_limit_set = False, False
        for limit in limits:
            if not limit.user and not limit.user_type:
                if (
                    limit.service == service
                    or limit.service_provider == service.provider
                    or limit.service_type == service.tp
                ):
                    is_min_limit_set = is_min_limit_set or limit.min_limit is not None
                    is_max_limit_set = is_max_limit_set or limit.limit is not None
                    if is_min_limit_set and is_max_limit_set:
                        return True
        return is_min_limit_set and is_max_limit_set

    @staticmethod
    def _get_min_max_limits(limits):
        try:
            min_limit = next(limit.min_limit for limit in limits if limit.min_limit is not None)
        except StopIteration:
            raise ServiceLimitNotSet('Service min_limit does not found.')
        try:
            max_limit = next(limit.limit for limit in limits if limit.limit is not None)
        except StopIteration:
            raise ServiceLimitNotSet('Service max_limit does not found.')

        return min_limit, max_limit

    @classmethod
    def set_user_limit(cls, user, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.user,
            user=user,
            user_type=None,
            service=None,
            service_provider=None,
            service_type=None,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            },
        )
        return limit

    @classmethod
    def set_user_service_limit(cls, user, service, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.user_service,
            user=user,
            user_type=None,
            service=service,
            service_provider=None,
            service_type=None,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            },
        )
        return limit

    @classmethod
    def set_user_type_service_limit(cls, user_type, service, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.user_type_service,
            user=None,
            user_type=user_type,
            service=service,
            service_provider=None,
            service_type=None,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            },
        )
        return limit

    @classmethod
    def set_service_limit(cls, service, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.service,
            user=None,
            user_type=None,
            service=service,
            service_provider=None,
            service_type=None,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            },
        )
        return limit

    @classmethod
    def set_service_provider_limit(cls, service_provider, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.service_provider,
            user=None,
            user_type=None,
            service=None,
            service_provider=service_provider,
            service_type=None,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            },
        )
        return limit

    @classmethod
    def set_service_type_limit(cls, service_type, min_limit=None, max_limit=None):
        if min_limit is None and max_limit is None:
            raise ValueError('min_limit and max_limit cannot both be None.')

        limit, _ = cls.objects.update_or_create(
            tp=cls.TYPES.service_type,
            user=None,
            user_type=None,
            service=None,
            service_provider=None,
            service_type=service_type,
            defaults={
                'min_limit': min_limit,
                'limit': max_limit,
            }
        )
        return limit
