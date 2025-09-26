from typing import Iterable, List, Tuple

from django.db.models import Manager, Model, Q, QuerySet


class BulkCobankManager(Manager):
    """
    A manager that handles a bulk_get_or_create with better performance than O(n) hits to DB.
    """

    def bulk_get_or_create(self, items: List[Model], unique_fields: Iterable[str]) -> Tuple[List[Model], QuerySet]:
        """
        Receives a list of Model objects with a list of fields that should be considered unique per object
        during the creation of these objects. Then creates all objects that don't already exist in DB
        and returns the rest.
        :param items: a List of Model objects to be created in DB if not already in there
        :param unique_fields: a List of names of the fields that should be considered unique per creation
        :return: a QuerySet of newly created items and a QuerySet of items that already existed in DB. The union of
         output created_items and existing_items might have more objects than the input items.
        """
        query_conditions = self._get_query_conditions(items, unique_fields)
        existing_items = super().filter(query_conditions)
        to_be_created_items = self._exclude_items(items, existing_items, unique_fields)
        created_items = super().bulk_create(to_be_created_items, ignore_conflicts=True)
        return created_items, existing_items

    def bulk_update_or_create(
        self,
        items: List[Model],
        unique_fields: Iterable[str],
        update_fields: Iterable[str],
    ) -> Tuple[List[Model], int]:
        query_conditions = self._get_query_conditions(items, unique_fields)
        existing_items = super().filter(query_conditions)

        to_be_updated_items = self._updated_items(items, existing_items, unique_fields, update_fields)
        updated_items_count = super().bulk_update(to_be_updated_items, update_fields, batch_size=100)

        to_be_created_items = self._exclude_items(items, existing_items, unique_fields)
        created_items = super().bulk_create(to_be_created_items, ignore_conflicts=True, batch_size=100)

        return created_items, updated_items_count

    def _get_query_conditions(self, items: List[Model], query_fields: Iterable[str]):
        """
        For each item, OR a set of condition on fields "default_fields",
        e.g. Q(field1=item1.field1, field2=item1.field2) OR Q(field1=item2.field1, field2=item2.field2)
        """
        query_condition = Q()
        for item in items:
            item_conditions = {field: getattr(item, field) for field in query_fields}
            query_condition |= Q(**item_conditions)
        return query_condition

    def _exclude_items(self, items: List[Model], exclusive_items: QuerySet, fields: Iterable[str]) -> List[Model]:
        """
        Return any item from the list of items that isn't similar to exclusive_items in certain fields
        """
        remaining_items = []
        for item in items:
            item_is_exclusive = False
            for exclusive_item in exclusive_items:
                if all(getattr(item, field) == getattr(exclusive_item, field) for field in fields):
                    item_is_exclusive = True
            if not item_is_exclusive:
                remaining_items.append(item)
        return remaining_items

    def _updated_items(
        self,
        items: List[Model],
        existing_items: QuerySet[Model],
        unique_fields: Iterable[str],
        update_fields: Iterable[str],
    ) -> List[Model]:
        existing_lookup = {
            tuple(getattr(existing_item, field) for field in unique_fields): (
                tuple(getattr(existing_item, field) for field in update_fields),
                existing_item,
            )
            for existing_item in existing_items
        }

        to_update_items = []
        for new_item in items:
            key = tuple(getattr(new_item, field) for field in unique_fields)

            if key in existing_lookup:
                new_update_values = tuple(getattr(new_item, field) for field in update_fields)
                if new_update_values != existing_lookup[key][0]:
                    existing_item = existing_lookup[key][1]
                    updated_item = False

                    for field, new_value in zip(update_fields, new_update_values):
                        if existing_item.is_updatable(field):
                            setattr(existing_item, field, new_value)
                            updated_item = True

                    if updated_item:
                        to_update_items.append(existing_item)

        return to_update_items
