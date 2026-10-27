from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.conf import settings


class CustomPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100
    DEFAULT_PAGINATION_PAGE_SIZE = 20

    def _get_page_size(self, obj):
        if obj and hasattr(obj, "default_pagination_page_size"):
            val = obj.default_pagination_page_size
            if val is not None and val > 0:
                return int(val)
        return None

    def get_page_size(self, request):
        try:
            requested = super().get_page_size(request)
            if requested is not None:
                return requested
        except (ValueError, TypeError):
            pass

        if not request.user.is_authenticated:
            return getattr(
                settings,
                "DEFAULT_PAGINATION_PAGE_SIZE",
                self.DEFAULT_PAGINATION_PAGE_SIZE,
            )

        try:
            from utilities.helpers import get_institution

            institution = get_institution(request)

            if institution:
                page_size = self._get_page_size(institution)
                if page_size:
                    return min(page_size, self.max_page_size)

        except Exception as e:
            print(f"Error determining personalized page size: {e}")
            pass

        return getattr(settings, "DEFAULT_PAGINATION_PAGE_SIZE", 20)

    def get_paginated_response(self, data):
        view = self.request.parser_context.get("view")
        queryset = getattr(view, "queryset", None)
        model = getattr(queryset, "model", None)

        meta = {}

        if model:
            meta = {
                "ordering_fields": getattr(model, "ordering_fields", []),
                "filterset_fields": getattr(model, "filterset_fields", []),
            }

        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                "meta": meta,
            }
        )
