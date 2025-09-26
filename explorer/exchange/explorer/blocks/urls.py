from django.urls import path

from .views import BlockHeadView, BlockInfoView

app_name = 'blocks'

urlpatterns = [
    path(
        'info',
        BlockInfoView.as_view(),
        name='block_info'
    ),
    path(
        'head',
        BlockHeadView.as_view(),
        name='block_head'
    )
]
