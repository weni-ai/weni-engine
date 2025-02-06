from rest_framework.pagination import CursorPagination


class CustomCursorPagination(CursorPagination):
    page_size = 1
    ordering = "-created_on"
    page_size_query_param = "page_size"
    max_page_size = 50
