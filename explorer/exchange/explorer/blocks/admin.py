from django.contrib import admin
from .models import GetBlockStats


class BlockStatsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "network",
        "latest_processed_block",
        "min_available_block"
    )


admin.site.register(GetBlockStats, BlockStatsAdmin)
