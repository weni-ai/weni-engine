from rest_framework.pagination import CursorPagination


class ChangeHistoryCursorPagination(CursorPagination):
    page_size = 10
    max_page_size = 50
    ordering = "-occurred_at"
