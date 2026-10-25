import uuid

from django.db import models
from django.db.models.functions import Length, Now, Trim
from django.db.models.lookups import GreaterThan


class Skill(models.Model):
    """Catalog definition; student achievements belong to separate records."""

    class StampType(models.TextChoices):
        FOCUSED = "FOCUSED", "Focused"
        APPLIED = "APPLIED", "Applied"
        ADVANCED = "ADVANCED", "Advanced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill_code = models.CharField(max_length=100)
    skill_name = models.CharField(max_length=250)
    category = models.CharField(max_length=150)
    subcategory = models.CharField(max_length=150, blank=True, default="", db_default="")
    description = models.TextField()
    stamp_type = models.CharField(max_length=30, choices=StampType.choices)
    badge_asset_id = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "skills_catalog"
        constraints = [
            models.UniqueConstraint(fields=["skill_code"], name="skills_catalog_skill_code_key"),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("skill_code")), 0), name="chk_skill_code",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("skill_name")), 0), name="chk_skill_name",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("category")), 0), name="chk_skill_category",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("description")), 0), name="chk_skill_description",
            ),
            models.CheckConstraint(
                condition=models.Q(stamp_type__in=["FOCUSED", "APPLIED", "ADVANCED"]),
                name="chk_stamp_type",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("badge_asset_id")), 0), name="chk_badge_asset",
            ),
        ]

    def __str__(self):
        return self.skill_code


# Explicit Unicode whitespace keeps source identities independent of DB locale.
_EDGE_WHITESPACE = (
    r"[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680"
    r"\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
)


class AchievementSourceEvent(models.Model):
    """Durable receipt for one atomic batch of skill awards from a source event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=100)
    source_event_id = models.CharField(max_length=255)
    course_id = models.CharField(max_length=255, blank=True, default="")
    evidence_reference = models.TextField(blank=True, default="")
    evidence = models.JSONField(default=dict, blank=True)
    payload_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "achievement_source_events"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_event_id"], name="uq_achievement_source_event",
            ),
            *[
                models.CheckConstraint(
                    condition=GreaterThan(Length(Trim(field)), 0)
                    & ~models.Q(**{f"{field}__regex": f"^{_EDGE_WHITESPACE}|{_EDGE_WHITESPACE}$"}),
                    name=name,
                )
                for field, name in (
                    ("source", "chk_achievement_source"),
                    ("source_event_id", "chk_achievement_event_id"),
                )
            ],
            models.CheckConstraint(
                condition=models.Q(payload_sha256__regex=r"^[0-9a-f]{64}$"),
                name="chk_achievement_payload_hash",
            ),
        ]


class VerifiedAchievement(models.Model):
    """One skill award, distinct from credentials and passport snapshots."""

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT,
        related_name="verified_achievements", db_index=False,
    )
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="verified_achievements")
    source_event = models.ForeignKey(
        AchievementSourceEvent, on_delete=models.PROTECT,
        related_name="achievements", db_index=False,
    )
    earned_on = models.DateField()
    verification_status = models.CharField(
        max_length=12, choices=VerificationStatus.choices, default=VerificationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "verified_achievements"
        constraints = [
            models.UniqueConstraint(
                fields=["source_event", "skill"], name="uq_achievement_event_skill",
            ),
            models.CheckConstraint(
                condition=models.Q(verification_status__in=["PENDING", "VERIFIED", "REJECTED"]),
                name="chk_achievement_status",
            ),
        ]
        indexes = [
            models.Index(
                fields=["student", "verification_status", "earned_on"],
                name="va_student_status_earned_idx",
            ),
        ]
