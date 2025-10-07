import traceback

from django.db.models.functions import Lower
from django.http import QueryDict
from rest_framework.filters import OrderingFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import DestroyModelMixin
from rest_framework.response import Response
from django.db.models import Q

from core.exceptions import SmartException
from core.middleware import RequestMiddleware


class CaseInsensitiveOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        no_case_sensitive_orders = ['-id','id','order','-order']
        if ordering:
            new_ordering = []
            for field in ordering:
                if field in no_case_sensitive_orders or 'count' in field or 'date' in field or '_at' in field:
                    new_ordering.append(field)
                else:
                    if field.startswith('-'):
                        new_ordering.append(Lower(field[1:]).desc())
                    else:
                        new_ordering.append(Lower(field).asc())
            return queryset.order_by(*new_ordering)
        return queryset

class PaginationMixin(object):
    def _paginate_response(self,queryset,serializer_model,context=None, serializer_kwargs=None):
        serializer_kwargs = serializer_kwargs or {}
        if context is None:
            try:
                context = self.get_serializer_context()
            except:
                context = {}
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_model(page, many=True, context=context, **serializer_kwargs)
            return self.get_paginated_response(serializer.data)

        serializer = serializer_model(queryset, many=True, context=context, **serializer_kwargs)
        return Response(serializer.data)

class FieldsMixin(object):
    def _get_fields(self, request=None):
        if request is None:
            request = RequestMiddleware(get_response=None).thread_local.current_request
        params = request.query_params.get('fields', None)
        return params.split(',') if params else None

class EntityMixin(DestroyModelMixin, GenericAPIView):

    def get_serializer_context(self, **kwargs):
        context = super().get_serializer_context()
        context['entity'] = self.request.entity
        return context

    def get_queryset(self):
        return super().get_queryset().filter(entity=self.request.entity)
    # def perform_create(self, serializer):
    #     if 'entity' in serializer.validated_data  and serializer.validated_data.get('entity') != self.request.user.entity:
    #         raise SmartException('Erro ao realizar ação')
    #     return super().perform_create(serializer)
    # def perform_update(self, serializer):
    #     if 'entity' in serializer.validated_data:
    #         print('VALIDAR A COMPANY AQUI')
    #     return super().perform_update(serializer)
    def perform_destroy(self, instance):
        if hasattr(instance, 'entity') and instance.entity != self.request.entity:
            raise SmartException('Entidade diferente do esperado')
        try:
            instance.delete()
        except Exception:
            traceback.print_exc()
            raise SmartException('Você não pode realizar essa ação')


class ListFieldsMixin(object):
    search_fields = ['name']
    ordering_fields = '__all__'
    def list(self, request, version=None):
        params = request.query_params

        queryset = self.filter_queryset(self.get_queryset())

        distinct = params.get('distinct', None)
        ordering = params.get('ordering', None)
        if distinct and ordering is None:
            queryset = queryset.distinct(distinct)

        page = self.paginate_queryset(queryset)

        fields = params.get('fields').split(
            ',') if params.get('fields', None) else None

        if page is not None:
            serializer = self.get_serializer(page, many=True, fields=fields)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True, fields=fields)
        return Response(serializer.data)


class ParamsMixin(object):

    def _get_query_params(self):
        if hasattr(self.request, 'query_params') and self.request.query_params:
            params = self.request.query_params
        else:
            params = {}
        return params

    def _get_body_params(self):
        if hasattr(self.request, 'data') and self.request.data:
            params = self.request.data
        else:
            params = {}
        return params



class FilterMixin(ParamsMixin):
    filters_kwargs = {}
    request = None

    def _update_params(self, params: QueryDict, data):
        for key, value in data.items():
            if isinstance(value, list):
                params.setlist(key, value)
            else:
                params[key] = value

    def _build_filter_kwargs(self, data=None, blacklist=None):
        self.filters_kwargs = {}
        blacklist = blacklist or []
        params = QueryDict('', mutable=True)
        if data:
            self._update_params(params, data)

        # if self.request.method == 'GET':
        #     params = self._get_query_params()
        if self.request and self.request.method == 'POST':
            self._update_params(params, self._get_body_params())

        if params:
            for kwarg in params:
                if kwarg in blacklist:
                    continue
                else:
                    if kwarg in ['orderning','historic','page','page_size','search']:
                        pass
                    elif params[kwarg] == 'true':
                        self.filters_kwargs[kwarg] = True
                    elif params[kwarg] == 'false':
                        self.filters_kwargs[kwarg] = False
                    elif params[kwarg] == 'null':
                        self.filters_kwargs[kwarg] = None
                    elif any([item in kwarg for item in ['__in', '__range']]):
                        aux = []
                        for value in params.getlist(kwarg):
                            if str(value).isdigit():
                                aux.append(int(value))
                            else:
                                aux.append(value)
                        self.filters_kwargs[kwarg] = aux
                    else:
                        self.filters_kwargs[kwarg] = params[kwarg]

    # @action(methods=['post'], detail=False)
    # def list_post(self, request, *args, **kwargs):
    #     queryset = self.filter_queryset(self.get_queryset())
    #     self._build_filter_kwargs()
    #     if self.filters_kwargs:
    #         queryset = queryset.filter(**self.filters_kwargs)
    #     if self.request.query_params.get('page'):
    #         page = self.paginate_queryset(queryset)
    #         serializer = self.get_serializer(page, many=True)
    #         return self.get_paginated_response(serializer.data)
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(data=serializer.data)

class SearchMixin(ParamsMixin):
    search_fields = []
    def _build_search_kwargs(self, method='GET'):
        q_objects = None
        if method == 'GET':
            params = self._get_query_params()
        elif method == 'POST':
            params = self._get_body_params()
        else:
            params = {}

        if params and self.search_fields:
            value = params.get('search')
            if value:
                q_objects = Q()
                for field in self.search_fields:
                    q_objects |= Q(**{f"{field}__icontains":value})
        return q_objects
