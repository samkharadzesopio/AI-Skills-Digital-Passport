
from rest_framework import serializers


class ClassroomCompletionSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    student_id = serializers.CharField()
    course_id = serializers.CharField()
    course_name = serializers.CharField()
    enrollment_status = serializers.CharField()
    completion_status = serializers.CharField()
    grade = serializers.FloatField(allow_null=True)
    passed = serializers.BooleanField()
    completion_date = serializers.DateField(allow_null=True)


class ClassroomSyncControlSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=True)

    def to_internal_value(self, data):
        from collections.abc import Mapping
        if not isinstance(data, Mapping) or set(data) - {'dry_run'}:
            raise serializers.ValidationError({'non_field_errors': ['Only the dry_run control is accepted; events are server-sourced.']})
        return super().to_internal_value(data)
