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
