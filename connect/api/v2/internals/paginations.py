from rest_framework.pagination import PageNumberPagination
from django.conf import settings


class ProjectsPageNumberPagination(PageNumberPagination):
    """
    Pagination class for internal projects API.
    Returns paginated results in the format: {count, next, previous, results}
    """
    page_size = getattr(settings, 'PROJECTS_PAGE_SIZE', 100)
    page_size_query_param = 'page_size'
    max_page_size = 1000
    page_query_param = 'page'
