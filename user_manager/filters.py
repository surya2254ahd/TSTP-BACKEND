from django_filters import rest_framework as filters

from user_manager.models import User


class UserFilter(filters.FilterSet):
    email = filters.CharFilter(lookup_expr='icontains')
    phone_number = filters.CharFilter(lookup_expr='icontains')
    name = filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = User
        fields = ['email', 'phone_number', 'name', 'is_active']

    def filter_is_active(self, queryset, name, value):
        if value is None:
            return queryset.filter(is_active=True)
        return queryset.filter(**{name: value})

    is_active = filters.BooleanFilter(method='filter_is_active')
