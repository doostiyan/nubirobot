from ipware import get_client_ip
from rest_framework.permissions import BasePermission


class CheckIPAddress(BasePermission):
    def has_permission(self, request, view):
        application = request.auth.application
        if application.accepts_ip(get_client_ip(request)[0]):
            return True
        return False


class UserIsActive(BasePermission):
    message = 'کاربر غیرفعال است یا حذف شده.'
    def has_permission(self, request, view):
        user = request.user
        return user.is_active
