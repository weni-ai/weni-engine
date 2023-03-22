from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from connect.template_projects.models import TemplateType
from .serializers import TemplateTypeSerializer


class TemplateTypeViewSet(ModelViewSet):

    queryset = TemplateType.objects
    serializer_class = TemplateTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        keyword = self.request.query_params.get('category')
        queryset = self.queryset.filter(category__iexact=keyword)
        print(keyword)
        return queryset


class TemplateAIViewSet(ModelViewSet):

    queryset = TemplateType.objects.all()
    serializer_class = TemplateTypeSerializer
    filterset_fields = []
    permission_classes = [IsAuthenticated]


class TemplateFeaturesViewSet(ModelViewSet):

    queryset = TemplateType.objects.all()
    serializer_class = TemplateTypeSerializer
    filterset_fields = []
    permission_classes = [IsAuthenticated]
