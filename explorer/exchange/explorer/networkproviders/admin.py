from django.contrib import admin
from .models import Provider, Network, NetworkDefaultProvider

admin.site.register(Provider)
admin.site.register(NetworkDefaultProvider)


class NetworkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "block_limit_per_req",
        "use_db"
    )

    search_fields = ['name']

admin.site.register(Network, NetworkAdmin)
