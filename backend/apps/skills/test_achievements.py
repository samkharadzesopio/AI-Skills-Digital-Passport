import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase

from apps.students.models import Student

from .achievement_services import SourceEventConflict, record_verified_achievements
from .models import AchievementSourceEvent, Skill, VerifiedAchievement


class AchievementDataMixin:
    def setUp(self):
        super().setUp()
        self.student = Student.objects.create(
            external_student_id="ACH-TEST-001", first_name="Synthetic", last_name="Student",
            email="ach-test-001@example.org", program="Test", education_level="Test",
            student_status="Active",
        )
        self.other_student = Student.objects.create(
            external_student_id="ACH-TEST-002", first_name="Synthetic", last_name="Other",
            email="ach-test-002@example.org", program="Test", education_level="Test",
            student_status="Active",
        )
        self.skills = [Skill.objects.create(
            skill_code=f"ACH-SKL-{n}", skill_name=f"Synthetic skill {n}", category="Test",
            description="Synthetic achievement test.", stamp_type="FOCUSED", badge_asset_id="TEST",
        ) for n in (1, 2)]

    def event(self, **overrides):
        return AchievementSourceEvent.objects.create(**({
            "source": "TEST_CLASSROOM", "source_event_id": "TEST-EVT-001",
            "course_id": "TEST-COURSE-001", "payload_sha256": "a" * 64,
        } | overrides))

    def award_data(self, event, **overrides):
        return {
            "student": self.student, "skill": self.skills[0], "source_event": event,
            "earned_on": date(2026, 10, 1),
        } | overrides

    def request_data(self, **overrides):
        return {
            "source": "TEST_CLASSROOM", "source_event_id": "TEST-EVT-001",
            "external_student_id": self.student.external_student_id,
            "approved_skill_codes": [s.skill_code for s in self.skills],
            "earned_on": date(2026, 10, 1), "course_id": "TEST-COURSE-001",
            "evidence_reference": "test-evidence:completion-001",
            "evidence": {"approval_reference": "TEST-APPROVAL-001", "grade": 80},
            "verification_status": "VERIFIED",
        } | overrides


class AchievementModelTests(AchievementDataMixin, TestCase):
    def test_uuid_relationships_default_status_and_timestamps(self):
        event = self.event()
        award = VerifiedAchievement.objects.create(**self.award_data(event))
        award.refresh_from_db()
        self.assertIsInstance(award.pk, uuid.UUID)
        self.assertIsInstance(event.pk, uuid.UUID)
        self.assertNotEqual(award.pk, event.pk)
        self.assertEqual(award.student_id, self.student.pk)
        self.assertEqual(award.skill_id, self.skills[0].pk)
        self.assertEqual(award.verification_status, "PENDING")
        self.assertIsNotNone(award.created_at)
        self.assertEqual(list(self.student.verified_achievements.all()), [award])

    def test_event_skill_unique_even_if_student_changes(self):
        event = self.event()
        VerifiedAchievement.objects.create(**self.award_data(event))
        with self.assertRaises(IntegrityError), transaction.atomic():
            VerifiedAchievement.objects.create(**self.award_data(event, student=self.other_student))

    def test_same_event_can_award_multiple_skills(self):
        event = self.event()
        for skill in self.skills:
            VerifiedAchievement.objects.create(**self.award_data(event, skill=skill))
        self.assertEqual(event.achievements.count(), 2)

    def test_independent_events_can_award_same_student_and_skill(self):
        for event_id in ("TEST-EVT-001", "TEST-EVT-002"):
            VerifiedAchievement.objects.create(**self.award_data(self.event(source_event_id=event_id)))
        self.assertEqual(self.student.verified_achievements.filter(skill=self.skills[0]).count(), 2)

    def test_source_namespaces_event_identity(self):
        self.event()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.event()
        self.event(source="TEST_OTHER_SOURCE")
        self.assertEqual(AchievementSourceEvent.objects.count(), 2)

    def test_source_identity_and_hash_constraints_cannot_be_bypassed(self):
        for field in ("source", "source_event_id"):
            for value in ("", " ", " value", "value\n", "\u00a0value", None):
                with self.subTest(field=field, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                    self.event(**{field: value})
        for value in ("", "z" * 64, "A" * 64, "a" * 63, None):
            with self.subTest(hash=value), self.assertRaises(IntegrityError), transaction.atomic():
                self.event(payload_sha256=value)

    def test_verification_status_and_date_are_required_at_database(self):
        event = self.event()
        for field, values in (("verification_status", ("", "UNKNOWN", "verified", None)), ("earned_on", (None,))):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                    VerifiedAchievement.objects.create(**self.award_data(event, **{field: value}))

    def test_all_supported_statuses_pass_model_validation(self):
        for status in VerifiedAchievement.VerificationStatus.values:
            award = VerifiedAchievement(**self.award_data(self.event(source_event_id=status), verification_status=status))
            award.full_clean()
            award.save()

    def test_protect_retains_students_catalog_and_evidence(self):
        event = self.event()
        VerifiedAchievement.objects.create(**self.award_data(event))
        for parent in (self.student, self.skills[0], event):
            with self.subTest(parent=type(parent).__name__), self.assertRaises(ProtectedError):
                parent.delete()

    def test_missing_uuid_foreign_keys_are_rejected(self):
        event = self.event()
        for field, relation in (("student_id", "student"), ("skill_id", "skill"), ("source_event_id", "source_event")):
            with self.subTest(field=field), self.assertRaises(IntegrityError), transaction.atomic():
                data = self.award_data(event)
                data.pop(relation)
                VerifiedAchievement.objects.create(**data, **{field: uuid.uuid4()})
                connection.check_constraints()

    def test_raw_delete_cannot_bypass_student_foreign_key(self):
        VerifiedAchievement.objects.create(**self.award_data(self.event()))
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM students WHERE id = %s", [self.student.pk])
            connection.check_constraints()


class AchievementServiceTests(AchievementDataMixin, TestCase):
    def test_records_entire_batch_and_resolves_external_id_to_uuid(self):
        awards, created = record_verified_achievements(**self.request_data())
        self.assertTrue(created)
        self.assertEqual(len(awards), 2)
        self.assertTrue(all(a.student_id == self.student.pk for a in awards))
        self.assertTrue(all(a.verification_status == "VERIFIED" for a in awards))
        event = AchievementSourceEvent.objects.get()
        self.assertEqual(event.course_id, "TEST-COURSE-001")
        self.assertEqual(event.evidence["approval_reference"], "TEST-APPROVAL-001")
        self.assertEqual(event.achievements.count(), 2)

    def test_replay_returns_original_ids_without_duplicates_or_skill_order_sensitivity(self):
        original, _ = record_verified_achievements(**self.request_data())
        replay, created = record_verified_achievements(**self.request_data(
            approved_skill_codes=[s.skill_code for s in reversed(self.skills)],
            evidence={"grade": 80, "approval_reference": "TEST-APPROVAL-001"},
        ))
        self.assertFalse(created)
        self.assertEqual([a.pk for a in original], [a.pk for a in replay])
        self.assertEqual(AchievementSourceEvent.objects.count(), 1)
        self.assertEqual(VerifiedAchievement.objects.count(), 2)

    def test_distinct_events_and_sources_do_not_collapse_repeat_awards(self):
        for overrides in ({}, {"source_event_id": "TEST-EVT-002"}, {"source": "OTHER_SOURCE"}):
            _, created = record_verified_achievements(**self.request_data(**overrides))
            self.assertTrue(created)
        self.assertEqual(VerifiedAchievement.objects.count(), 6)

    def test_conflicting_replays_never_overwrite_existing_batch(self):
        original, _ = record_verified_achievements(**self.request_data())
        changes = (
            {"external_student_id": self.other_student.external_student_id},
            {"earned_on": date(2026, 10, 2)}, {"approved_skill_codes": [self.skills[0].skill_code]},
            {"verification_status": "REJECTED"}, {"course_id": "OTHER-COURSE"},
            {"evidence": {"grade": 99}}, {"evidence_reference": "other-reference"},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(SourceEventConflict):
                record_verified_achievements(**self.request_data(**change))
        self.assertCountEqual(VerifiedAchievement.objects.values_list("pk", flat=True), [a.pk for a in original])

    def test_failed_partial_insert_rolls_back_receipt_and_all_awards(self):
        def fail_after_first(awards, **kwargs):
            awards[0].save(force_insert=True)
            raise RuntimeError("Synthetic failure")

        with patch.object(VerifiedAchievement.objects, "bulk_create", side_effect=fail_after_first):
            with self.assertRaises(RuntimeError):
                record_verified_achievements(**self.request_data())
        self.assertEqual(AchievementSourceEvent.objects.count(), 0)
        self.assertEqual(VerifiedAchievement.objects.count(), 0)
        self.assertTrue(record_verified_achievements(**self.request_data())[1])

    def test_missing_catalog_mapping_or_student_leaves_no_receipt(self):
        with self.assertRaises(ValidationError):
            record_verified_achievements(**self.request_data(approved_skill_codes=["MISSING-SKILL"]))
        for value in ("MISSING-STUDENT", str(self.student.pk)):
            with self.subTest(value=value), self.assertRaises(Student.DoesNotExist):
                record_verified_achievements(**self.request_data(external_student_id=value))
        self.assertFalse(AchievementSourceEvent.objects.exists())

    def test_rejects_invalid_input_before_creating_receipt(self):
        changes = (
            {"source": " "}, {"source_event_id": " padded "},
            {"external_student_id": " " + self.student.external_student_id},
            {"earned_on": "2026-10-01"}, {"earned_on": datetime(2026, 10, 1)},
            {"verification_status": "APPROVED"}, {"course_id": None},
            {"approved_skill_codes": []}, {"approved_skill_codes": self.skills[0].skill_code},
            {"approved_skill_codes": [self.skills[0].skill_code] * 2},
            {"evidence": []}, {"evidence": {"grade": float("nan")}},
            {"evidence": {"date": date(2026, 10, 1)}}, {"evidence_reference": None},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                record_verified_achievements(**self.request_data(**change))
        self.assertFalse(AchievementSourceEvent.objects.exists())

    def test_status_defaults_to_pending_without_implicit_approval(self):
        request = self.request_data()
        request.pop("verification_status")
        awards, _ = record_verified_achievements(**request)
        self.assertTrue(all(a.verification_status == "PENDING" for a in awards))

    def test_inconsistent_existing_awards_are_not_silently_repaired(self):
        awards, _ = record_verified_achievements(**self.request_data())
        VerifiedAchievement.objects.filter(pk=awards[0].pk).update(verification_status="REJECTED")
        with self.assertRaises(SourceEventConflict):
            record_verified_achievements(**self.request_data())


@skipUnless(connection.vendor == "postgresql", "Requires isolated PostgreSQL")
class AchievementConcurrencyTests(AchievementDataMixin, TransactionTestCase):
    def concurrent(self, operation):
        barrier = Barrier(2)

        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation(index)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, range(2)))

    def test_concurrent_identical_batches_create_one_receipt_and_one_award_per_skill(self):
        def record(index):
            awards, created = record_verified_achievements(**self.request_data())
            return created, [a.pk for a in awards]

        results = self.concurrent(record)
        self.assertCountEqual([r[0] for r in results], [True, False])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(AchievementSourceEvent.objects.count(), 1)
        self.assertEqual(VerifiedAchievement.objects.count(), 2)

    def test_concurrent_conflicting_student_batches_have_one_winner(self):
        def record(index):
            try:
                record_verified_achievements(**self.request_data(external_student_id=(
                    self.student if index == 0 else self.other_student
                ).external_student_id))
                return "created"
            except SourceEventConflict:
                return "conflict"

        self.assertCountEqual(self.concurrent(record), ["created", "conflict"])
        self.assertEqual(AchievementSourceEvent.objects.count(), 1)
        self.assertEqual(VerifiedAchievement.objects.count(), 2)
        self.assertEqual(VerifiedAchievement.objects.values("student_id").distinct().count(), 1)

    def test_concurrent_conflicting_mapping_batches_are_not_merged(self):
        def record(index):
            try:
                record_verified_achievements(**self.request_data(approved_skill_codes=[self.skills[index].skill_code]))
                return "created"
            except SourceEventConflict:
                return "conflict"

        self.assertCountEqual(self.concurrent(record), ["created", "conflict"])
        self.assertEqual(AchievementSourceEvent.objects.count(), 1)
        self.assertEqual(VerifiedAchievement.objects.count(), 1)

    def test_concurrent_direct_inserts_cannot_bypass_event_skill_uniqueness(self):
        event = self.event()

        def record(index):
            try:
                with transaction.atomic():
                    VerifiedAchievement.objects.create(**self.award_data(event))
                return "created"
            except IntegrityError:
                return "duplicate"

        self.assertCountEqual(self.concurrent(record), ["created", "duplicate"])
        self.assertEqual(VerifiedAchievement.objects.count(), 1)
