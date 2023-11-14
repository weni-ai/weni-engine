from rest_framework.pagination import CursorPagination


class CustomCursorPagination(CursorPagination):
    page_size = 1
    ordering = "-created_on"
