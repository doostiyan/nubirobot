from django.urls import path


from .views import LoginView, LogoutView, UserDashboardView, UserListView, UserAPIKeyView

app_name = 'accounts'

urlpatterns = [

    path(
        '',
        UserListView.as_view(),
        name='user_list'
    ),
    path(
        'login',
        LoginView.as_view(),
        name='login'
    ),
    path(
        'logout',
        LogoutView.as_view(),
        name='logout'
    ),
    path(
        'dashboard',
        UserDashboardView.as_view(),
        name='dashboard'
    ),
    path(
        'api-keys',
        UserAPIKeyView.as_view(),
        name='user_api_keys'
    ),
]
