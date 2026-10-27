from django.db.models import BooleanField, Q
from rest_framework.exceptions import ValidationError
from institution.models import Branch, Institution
from typing import Optional, Sequence


class BranchFilterMixin:
    def get_branch_ids_from_header(self, request):
        raw = request.META.get("HTTP_SELECTEDBRANCHES")
        if not raw:
            return None
        try:
            ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
            return ids if ids else []
        except ValueError:
            raise ValidationError(
                {"error": "`SelectedBranches` must be comma-separated IDs"}
            )

    def filter_queryset_by_branches(
        self,
        queryset,
        request,
        institution: Institution,
        *,
        branch_lookups: Optional[Sequence[str]] = None,
        strict: bool = True,
    ):
        header_ids = self.get_branch_ids_from_header(request)

        filter_ids = (
            [bid for bid in header_ids]
            if header_ids
            else [b.id for b in Branch.objects.filter(institution=institution)]
        )

        if not filter_ids:
            return queryset.none()

        if branch_lookups is not None:
            lookups = (
                [branch_lookups]
                if isinstance(branch_lookups, str)
                else list(branch_lookups)
            )
            lookups = [lk.strip() for lk in lookups if lk.strip()]
        else:
            lookups = []

        if lookups:
            q_objects = Q()
            for lookup in lookups:
                if lookup.endswith("__in"):
                    q_objects |= Q(**{lookup: filter_ids})
                else:
                    q_objects |= Q(**{f"{lookup}_id__in": filter_ids})

            filtered = queryset.filter(q_objects).distinct()
            if strict or filtered.exists():
                return filtered

        direct_qs = self._try_filter_direct_branch(queryset, filter_ids)
        if direct_qs is not None and direct_qs.exists():
            return direct_qs

        user_qs = self._try_filter_via_userbranch(queryset, filter_ids)
        if user_qs is not None and user_qs.exists():
            return user_qs

        return queryset

    def _try_filter_direct_branch(self, qs, branch_ids):
        model = qs.model
        branch_filters = []

        for f in model._meta.get_fields():
            if (
                f.is_relation
                and f.related_model
                and issubclass(f.related_model, Branch)
                and not f.auto_created
            ):
                branch_filters.append(f.name)

        if not branch_filters:
            return None

        q_obj = Q()
        for field in branch_filters:
            field_obj = model._meta.get_field(field)
            if field_obj.many_to_many:
                q_obj |= Q(**{f"{field}__in": branch_ids})
            else:
                q_obj |= Q(**{f"{field}_id__in": branch_ids})
        return qs.filter(q_obj).distinct()

    def _try_filter_via_userbranch(self, qs, branch_ids):
        model = qs.model
        user_fields = [
            f.name
            for f in model._meta.get_fields()
            if (
                f.is_relation
                and f.related_model
                and f.related_model.__name__ == "CustomUser"
                and not f.auto_created
            )
        ]
        if not user_fields:
            return None

        q_obj = Q()
        for field in user_fields:
            q_obj |= Q(**{f"{field}__attached_branches__branch_id__in": branch_ids})
        return qs.filter(q_obj).distinct()


class SearchOrderMixin:
    search_param = "search"
    ordering_param = "ordering"

    @staticmethod
    def _coerce_filter_value(model, field_name, value):
        field = model._meta.get_field(field_name.split("__", 1)[0])
        if isinstance(field, BooleanField) and isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        return value

    def apply_filters(self, queryset):
        allowed_fields = getattr(queryset.model, "filterset_fields", [])
        filters = {}

        for field in allowed_fields:
            values = [
                value
                for value in self.request.query_params.getlist(field)
                if value not in (None, "")
            ]

            if len(values) == 1:
                filters[field] = self._coerce_filter_value(
                    queryset.model, field, values[0]
                )
            elif len(values) > 1:
                filters[f"{field}__in"] = [
                    self._coerce_filter_value(queryset.model, field, value)
                    for value in values
                ]

        return queryset.filter(**filters) if filters else queryset

    def apply_search(self, queryset):
        search_value = self.request.query_params.get(self.search_param)

        if not search_value:
            return queryset

        model = queryset.model

        if getattr(model, "supports_hierarchy", False):
            return queryset.hierarchical_search(search_value)

        return queryset.search(search_value)

    def apply_ordering(self, queryset):
        ordering = self.request.query_params.get(self.ordering_param)
        if not ordering:
            return queryset

        model = queryset.model
        allowed_fields = getattr(model, "ordering_fields", None)

        fields = []

        for field in ordering.split(","):
            field = field.strip()

            if not field:
                continue

            field_name = field.lstrip("-")

            if allowed_fields and field_name not in allowed_fields:
                continue

            fields.append(field)

        return queryset.order_by(*fields) if fields else queryset
