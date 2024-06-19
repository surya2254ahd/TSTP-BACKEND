from django_filters import rest_framework as filters

from .models import Test


class IntegerListFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class CharListFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class TestFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    course = IntegerListFilter(field_name='course__id')
    format_type = CharListFilter()

    class Meta:
        model = Test
        fields = ['name', 'course', 'format_type']
