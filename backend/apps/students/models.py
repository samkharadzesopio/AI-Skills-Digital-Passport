import uuid

from django.db import models
from django.db.models.functions import Length, Lower, Now, Trim
from django.db.models.lookups import GreaterThan


class Student(models.Model):
    """Canonical student identity and current academic profile."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_student_id = models.CharField(max_length=120)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255)
    program = models.CharField(max_length=255)
    education_level = models.CharField(max_length=100)
    student_status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "students"
        constraints = [
            models.UniqueConstraint(
                fields=["external_student_id"], name="students_external_student_id_key",
            ),
            models.UniqueConstraint(Lower("email"), name="ux_students_email"),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("external_student_id")), 0),
                name="chk_student_external_id",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("first_name")), 0),
                name="chk_student_first_name",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("last_name")), 0),
                name="chk_student_last_name",
            ),
            models.CheckConstraint(
                condition=models.Q(email=Trim("email"))
                & models.Q(email__iregex=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"),
                name="chk_student_email",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("program")), 0),
                name="chk_student_program",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("education_level")), 0),
                name="chk_student_education_level",
            ),
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("student_status")), 0),
                name="chk_student_status",
            ),
        ]

    def __str__(self):
        return self.external_student_id
