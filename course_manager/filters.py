from django_filters import rest_framework as filters

from .models import Question, Material


class IntegerListFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class CharListFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class QuestionFilter(filters.FilterSet):
    description = filters.CharFilter(lookup_expr='icontains')
    topic = IntegerListFilter(field_name='topic__id')
    sub_topic = IntegerListFilter(field_name='sub_topic__id')
    test_type = CharListFilter()
    difficulty = CharListFilter()

    class Meta:
        model = Question
        fields = ['description', 'is_active', 'topic', 'sub_topic', 'test_type', 'difficulty']

    # def filter_is_active(self, queryset, name, value):
    #     if value is None:
    #         return queryset.filter(is_active=True)
    #     return queryset.filter(**{name: value})
    #
    # is_active = filters.BooleanFilter(method='filter_is_active')


class PracticeQuestionFilter(filters.FilterSet):
    topic = IntegerListFilter(field_name='topic__id')
    sub_topic = IntegerListFilter(field_name='sub_topic__id')
    difficulty = CharListFilter()

    class Meta:
        model = Question
        fields = ['is_active', 'topic', 'sub_topic', 'difficulty']

    def filter_is_active(self, queryset, name, value):
        if value is None:
            return queryset.filter(is_active=True)
        return queryset.filter(**{name: value})

    is_active = filters.BooleanFilter(method='filter_is_active')


class MaterialFilter(filters.FilterSet):
    topic = IntegerListFilter(field_name='topic__id')
    sub_topic = IntegerListFilter(field_name='sub_topic__id')

    # def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
    #     super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)
    #     self.request = request

    class Meta:
        model = Material
        fields = ['material_type', 'access_type', 'topic', 'sub_topic']

    # def filter_by_topic_subtopic(self, queryset, name, value):
    #     topic_ids = self.parse_ids(self.request.query_params.get('topic'))
    #     sub_topic_ids = self.parse_ids(self.request.query_params.get('sub_topic'))
    #
    #     if topic_ids:
    #         queryset = queryset.filter(topic__id__in=topic_ids)
    #
    #     if sub_topic_ids:
    #         # Filter by subtopics from the already filtered queryset by topics
    #         queryset = queryset.filter(sub_topic__id__in=sub_topic_ids)
    #
    #     return queryset
    #
    # def filter_queryset(self, queryset):
    #     return self.filter_by_topic_subtopic(queryset, None, None)

    # @staticmethod
    # def parse_ids(ids_string):
    #     """Parse a comma-separated string into a list of integers."""
    #     if ids_string:
    #         return [int(id.strip()) for id in ids_string.split(',')]
    #     return []

    # def filter_material_type(self, queryset, name, value):
    #     if value is None:
    #         return queryset.filter(material_type='VIDEO')
    #     return queryset.filter(**{name: value})
    #
    # material_type = filters.CharFilter(method='filter_material_type')
