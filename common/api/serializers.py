from rest_framework import serializers

from core.middleware import RequestMiddleware
from utils.util_date import date_by_timezone, replace_time_zone

class DefaultModelSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # user = RequestMiddleware(get_response=None).thread_local.current_request.user
        # for field, f_type in self.fields.items():
        #     if type(f_type) == serializers.DateTimeField and getattr(instance, field):
        #         if not user.is_anonymous and user.is_authenticated and hasattr(user, 'time_zone'):
        #             data[field] = date_by_timezone(getattr(instance, field), user.time_zone)
        #         else:
        #             data[field] = date_by_timezone(getattr(instance, field))
        return data

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        # user = RequestMiddleware(get_response=None).thread_local.current_request.user
        # for field, f_type in self.fields.items():
        #     if type(f_type) == serializers.DateTimeField and validated_data.get(field):
        #         if self.instance is None or (getattr(self.instance, field) != validated_data.get(field)):
        #             validated_data[field] = replace_time_zone(validated_data.get(field), user.time_zone)
        return validated_data

class DynamicSerializer(serializers.Serializer):

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        add_fields = kwargs.pop('add_fields', None)
        exclude = kwargs.pop('exclude', None)
        nest = kwargs.pop('nest', None)

        if nest is not None:
            self.Meta.depth = nest
        super(DynamicSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if add_fields is not None:
            for field_name, field_class in add_fields.items():
                ### first pop the old field class from the fields if it's there
                if field_name in self.fields:
                    self.fields.pop(field_name)
                ### now add the field to the fields
                self.fields[field_name] = field_class

        if exclude is not None:
            for field_name in exclude:
                self.fields.pop(field_name)

class DynamicModelSerializer(DefaultModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        add_fields = kwargs.pop('add_fields', None)
        exclude = kwargs.pop('exclude', None)
        nest = kwargs.pop('nest', None)

        if nest is not None:
            self.Meta.depth = nest

        super(DynamicModelSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if add_fields is not None:
            for field_name, field_class in add_fields.items():
                ### first pop the old field class from the fields if it's there
                if field_name in self.fields:
                    self.fields.pop(field_name)
                ### now add the field to the fields
                self.fields[field_name] = field_class

        if exclude is not None:
            for field_name in exclude:
                if field_name in self.fields:
                    self.fields.pop(field_name)


class QueryIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)

class QueryListIdsSerializer(serializers.Serializer):
    list_ids = serializers.ListField(required=True)