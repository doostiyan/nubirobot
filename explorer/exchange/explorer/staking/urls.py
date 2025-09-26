from django.urls import path

from exchange.explorer.staking.views import StakingRewardsView, ValidatorListView

urlpatterns = [
    path('staking-rewards/<str:wallet_address>/', StakingRewardsView.as_view(), name='staking-rewards'),
    path('validators', ValidatorListView.as_view(), name='validators-list'),
]
