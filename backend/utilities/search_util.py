from django.db import models
from django.db.models import F, Q
from django_cte import CTE, with_cte


class SearchableQuerySet(models.QuerySet):
    @staticmethod
    def _normalize_search_value(value):
        if not isinstance(value, str):
            return value

        return " ".join(value.split())

    def _build_search_q(self, value):
        value = self._normalize_search_value(value)

        model = self.model
        base_fields = getattr(model, "base_search_fields", [])
        text_fields = getattr(model, "search_fields", [])

        if not value:
            return Q()

        query = Q()

        for field in base_fields:
            query |= Q(**{f"{field}__iexact": value})
            query |= Q(**{f"{field}__istartswith": value})
            query |= Q(**{f"{field}__icontains": value})

        for field in text_fields:
            query |= Q(**{f"{field}__icontains": value})

        return query

    def search(self, value):
        value = self._normalize_search_value(value)

        if not value:
            return self

        return self.filter(self._build_search_q(value))

    def hierarchical_search(self, value, parent_field="parent", use_cte=True):
        value = self._normalize_search_value(value)

        if not value:
            return self

        query = self._build_search_q(value)
        parent_field_object = self.model._meta.get_field(parent_field)
        parent_id_field = parent_field_object.attname

        if not use_cte:
            matching_ids = set(self.filter(query).values_list("pk", flat=True))

            if not matching_ids:
                return self.none()

            parent_by_id = dict(self.values_list("pk", parent_id_field))
            included_ids = set(matching_ids)
            pending_ids = set(matching_ids)

            while pending_ids:
                node_id = pending_ids.pop()
                parent_id = parent_by_id.get(node_id)

                if parent_id is None or parent_id in included_ids:
                    continue

                included_ids.add(parent_id)
                pending_ids.add(parent_id)

            return self.filter(pk__in=included_ids)

        def build_hierarchy(cte):
            matching_nodes = (
                self.filter(query)
                .order_by()
                .annotate(
                    node_id=F("pk"),
                    parent_node_id=F(parent_id_field),
                )
                .values("node_id", "parent_node_id")
            )

            parent_nodes = (
                cte.join(
                    self.order_by(),
                    pk=cte.col.parent_node_id,
                )
                .annotate(
                    node_id=F("pk"),
                    parent_node_id=F(parent_id_field),
                )
                .values("node_id", "parent_node_id")
            )

            return matching_nodes.union(parent_nodes)

        hierarchy = CTE.recursive(
            build_hierarchy,
            name="search_hierarchy",
        )

        return with_cte(
            hierarchy,
            select=hierarchy.join(
                self,
                pk=hierarchy.col.node_id,
            ),
        )


class BaseQuerySet(SearchableQuerySet):
    def active(self):
        return self.filter(is_active=True, deleted_at__isnull=True)

    def undeleted(self):
        return self.filter(deleted_at__isnull=True)


class BaseManager(models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        return super().get_queryset().all()
