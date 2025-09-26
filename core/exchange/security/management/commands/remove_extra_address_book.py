from django.core.management.base import BaseCommand
from django.db.models import Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from exchange.security.models import AddressBook, WhiteListModeLog


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        """
        AddressBook objects that don't have active whiteListMode and don't have any registered address
        will be deleted!

        related address_book_items (addresses) will be deleted (cascade relation)
        related whitelist_mode_logs will also be deleted (cascade relation)
        """
        q_white_list_mode_logs = WhiteListModeLog.objects.filter(
            address_book_id=OuterRef("pk")
        ).order_by('-created_at')

        AddressBook.objects.annotate(
            whitelistmode=Coalesce(Subquery(q_white_list_mode_logs.values("is_active")[:1]), False),
            address_count=Count('addresses__pk')
        ).filter(whitelistmode=False, address_count=0).delete()


