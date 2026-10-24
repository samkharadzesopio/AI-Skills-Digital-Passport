from rest_framework import serializers

from .models import Student


class StudentProfileSerializer(serializers.ModelSerializer):
    student_id = serializers.CharField(source="external_student_id", read_only=True)

    class Meta:
        model = Student
        fields = (
            "student_id", "first_name", "last_name", "email",
            "program", "education_level", "student_status",
        )
        read_only_fields = fields
