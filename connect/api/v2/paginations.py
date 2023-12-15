from rest_framework.pagination import CursorPagination


class CustomCursorPagination(CursorPagination):
    page_size_query_param = 'page_size'
    page_size = 20

    def paginate_queryset(self, queryset, request, view=None):
        self.ordering = view.get_ordering()
        return super().paginate_queryset(queryset, request, view)
