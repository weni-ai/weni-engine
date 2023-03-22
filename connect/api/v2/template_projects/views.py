from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from connect.template_projects.models import TemplateType, TemplateFeature, TemplateAI
from .serializers import TemplateTypeSerializer, RetrieveTemplateSerializer, TemplateFeatureSerializer, TemplateAISerializer
from rest_framework.response import Response


class TemplateTypeViewSet(ModelViewSet):

    queryset = TemplateType.objects.all()
    serializer_class = TemplateTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        queryset = self.queryset
        id = self.request.query_params.get('id', None)
        name = self.request.query_params.get('name', None)
        category = self.request.query_params.get('category', None)

        if name:
            queryset = self.queryset.filter(name__iexact=name)

        if category:
            queryset = self.queryset.filter(category__iexact=category)

        if id:
            queryset = self.queryset.filter(pk=id)

        return queryset

    def retrieve(self, request, *args, **kwargs):

        instance = self.get_object()
        serializer = RetrieveTemplateSerializer(instance)
        print("alo")

        return Response(serializer.data)


class TemplateAIViewSet(ModelViewSet):
    queryset = TemplateAI.objects.all()
    serializer_class = TemplateAISerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        name = self.request.query_params.get('name', None)
        template_type = self.request.query_params.get('template_type', None)
        if name:
            queryset = self.queryset.filter(name__iexact=name)
        if template_type:
            queryset = self.queryset.filter(pk=template_type)
        return queryset


class TemplateFeatureViewSet(ModelViewSet):
    queryset = TemplateFeature.objects.all()
    serializer_class = TemplateFeatureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        id = self.request.query_params.get('id', None)
        name = self.request.query_params.get('name', None)
        if name:
            queryset = self.queryset.filter(name__iexact=name)
        if id:
            queryset = self.queryset.filter(pk=id)
        return queryset
