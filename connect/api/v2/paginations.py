from rest_framework.pagination import CursorPagination


class CustomCursorPagination(CursorPagination):
    page_size_query_param = 'page_size'
    page_size = 20
    ordering = "created_at"

    def paginate_queryset(self, queryset, request, view=None):
        ordering = view.get_ordering()
        if ordering:
            queryset = queryset.order_by(ordering)
        return super().paginate_queryset(queryset, request, view)
