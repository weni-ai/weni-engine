from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateSuggestion
from .serializers import TemplateTypeSerializer, RetrieveTemplateSerializer, TemplateFeatureSerializer, TemplateSuggestionSerializer
from .permission import IsAdminOrReadOnly


class TemplateTypeViewSet(ModelViewSet):

    queryset = TemplateType.objects.all()
    serializer_class = TemplateTypeSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = self.queryset
        id = self.request.query_params.get('id', None)
        name = self.request.query_params.get('name', None)
        category = self.request.query_params.get('category', None)
        uuid = self.request.query_params.get('uuid', None)

        if name:
            queryset = self.queryset.filter(name__iexact=name)

        if category:
            queryset = self.queryset.filter(category__contains=[category])

        if id:
            queryset = self.queryset.filter(pk=id)

        if uuid:
            queryset = self.queryset.filter(uuid__iexact=uuid)

        return queryset

    def retrieve(self, request, *args, **kwargs):

        instance = self.get_object()
        serializer = RetrieveTemplateSerializer(instance)

        return Response(serializer.data)


class TemplateFeatureViewSet(ModelViewSet):
    queryset = TemplateFeature.objects.all()
    serializer_class = TemplateFeatureSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = self.queryset
        id = self.request.query_params.get('id', None)
        name = self.request.query_params.get('name', None)
        if name:
            queryset = self.queryset.filter(name__iexact=name)
        if id:
            queryset = self.queryset.filter(pk=id)
        return queryset


class TemplateSuggestionViewSet(ModelViewSet):
    queryset = TemplateSuggestion.objects.all()
    serializer_class = TemplateSuggestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        id = self.request.query_params.get('id', None)
        if id:
            queryset = self.queryset.filter(pk=id)
        return queryset
