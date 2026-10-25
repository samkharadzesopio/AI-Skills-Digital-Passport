"""Private API contracts. Internal source payloads and account metadata stay private."""
from collections.abc import Mapping
from rest_framework import serializers
from apps.students.models import Student
from apps.students.serializers import StudentProfileSerializer
from apps.skills.models import Skill, VerifiedAchievement
from apps.credentials.models import Credential
from apps.passports.models import DigitalPassport, PassportVersion, PassportVersionSkill, PassportVersionCredential


class StrictInputMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        protected = {key for key in data if key in self.fields and self.fields[key].read_only}
        if unknown or protected:
            raise serializers.ValidationError({key: 'Field is not writable.' for key in unknown | protected})
        return super().to_internal_value(data)


class StudentSerializer(StrictInputMixin, StudentProfileSerializer):
    class Meta(StudentProfileSerializer.Meta):
        fields = ('id', 'external_student_id', *StudentProfileSerializer.Meta.fields[1:])
        read_only_fields = ('id',)

    def validate(self, attrs):
        if self.instance:
            protected = {'external_student_id', 'email', 'first_name', 'last_name'} & attrs.keys()
            if protected:
                raise serializers.ValidationError({key: 'University identity cannot be changed through this API.' for key in protected})
        # Model constraint validation includes case-insensitive university identifiers.
        candidate = Student(**{field.name: getattr(self.instance, field.name) for field in Student._meta.fields} if self.instance else {})
        for key, value in attrs.items():
            setattr(candidate, key, value)
        if self.instance:
            candidate._state.adding = False
        from django.core.exceptions import ValidationError
        try:
            candidate.full_clean()
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class SkillSerializer(serializers.ModelSerializer):
    competency_level = serializers.CharField(source='stamp_type')
    class Meta:
        model = Skill
        fields = ('id', 'skill_code', 'skill_name', 'category', 'subcategory', 'competency_level', 'description')


class AchievementSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    course_reference = serializers.CharField(source='source_event.course_id', read_only=True)
    class Meta:
        model = VerifiedAchievement
        fields = ('id', 'skill', 'course_reference', 'earned_on', 'verification_status')


class RecognizedSkillSerializer(SkillSerializer):
    achievements = AchievementSerializer(source='student_achievements', many=True, read_only=True)
    achievements_limit = serializers.IntegerField(default=100, read_only=True)
    class Meta(SkillSerializer.Meta):
        fields = (*SkillSerializer.Meta.fields, 'achievements', 'achievements_limit')


class CredentialSerializer(serializers.ModelSerializer):
    validity_status = serializers.SerializerMethodField()
    achievements = AchievementSerializer(many=True, read_only=True)
    class Meta:
        model = Credential
        fields = ('id', 'public_reference', 'student_id', 'issuer_reference', 'issuer_name', 'issued_at', 'expires_at', 'status', 'validity_status', 'revoked_at', 'achievements')

    def get_validity_status(self, obj):
        return obj.verification_status_at(self.context['now'])


class SnapshotSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassportVersionSkill
        fields = ('skill_id', 'skill_code', 'skill_name', 'category', 'subcategory', 'description', 'stamp_type')


class SnapshotCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassportVersionCredential
        fields = ('credential_public_reference', 'issuer_reference', 'issuer_name', 'credential_issued_at', 'credential_expires_at')


class VersionSerializer(serializers.ModelSerializer):
    skills = SnapshotSkillSerializer(source='skill_snapshots', many=True, read_only=True)
    credentials = SnapshotCredentialSerializer(source='credential_snapshots', many=True, read_only=True)
    class Meta:
        model = PassportVersion
        fields = ('id', 'public_reference', 'version_number', 'status', 'issued_at', 'created_at', 'skills', 'credentials')


class PassportSerializer(serializers.ModelSerializer):
    latest_version = VersionSerializer(read_only=True)
    status = serializers.SerializerMethodField()
    class Meta:
        model = DigitalPassport
        fields = ('id', 'public_reference', 'student_id', 'status', 'created_at', 'updated_at', 'latest_version')

    def get_status(self, obj):
        return obj.latest_version.status if obj.latest_version else 'NOT_ISSUED'


class IssueSerializer(StrictInputMixin, serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=255)
    achievement_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=256)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class RevokeSerializer(StrictInputMixin, serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
