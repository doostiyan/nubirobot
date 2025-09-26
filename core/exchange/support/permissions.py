from rest_framework import permissions


class HasCallReasonApiPerm(permissions.BasePermission):
    """
    Check that user has permission to call call_reason api endpoints
    """

    def has_permission(self, request, view):
        has_perm = request.user.has_perm('accounts.access_to_call_reason_api')
        return has_perm
