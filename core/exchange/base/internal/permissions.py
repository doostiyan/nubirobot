from typing import Iterable

from rest_framework.permissions import BasePermission

from exchange.base.internal.services import Services


class AllowedServices(BasePermission):
    """
    Permission class to check if the request's service is allowed to access a particular view.

    This class is used to restrict access to views based on the service making the request. It checks
    whether the service associated with the request is within a specified set of allowed services.

    Attributes:
        allowed_services (Iterable[Services]): A collection of `Services` instances that are permitted
            to access the view.
    """

    def __init__(self, allowed_services: Iterable[Services]) -> None:
        self.allowed_services = allowed_services
        super().__init__()

    def __call__(self):
        return self

    def has_permission(self, request, view):
        return bool(request.service and request.service in self.allowed_services)
