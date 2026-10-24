
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
