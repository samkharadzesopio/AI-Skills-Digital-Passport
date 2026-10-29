import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import patch

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.credentials.models import Credential
from apps.credentials.services import issue_credential, revoke_credential
from apps.credentials.test_support import create_test_issuer
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student

from .models import (
    DigitalPassport,
    PassportUpdateEvent,
    PassportVersion,
    PassportVersionCredential,
)
from .services import (
    get_or_create_passport,
    publish_passport_for_credential_event,
    publish_passport_version,
    schedule_passport_update_for_credential_event,
)


class PassportDataMixin:
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)
        self.student = Student.objects.create(
            external_student_id="PASSPORT-TEST-001",
            first_name="Synthetic",
            last_name="Student",
            email="passport-001@example.org",
            program="Computer Science",
            education_level="Bachelor",
            student_status="Active",
        )
        self.issuer = create_test_issuer("Synthetic University")
        self.skills = [
            Skill.objects.create(
                skill_code=f"PASS-SKILL-{number}",
                skill_name=f"Passport skill {number}",
                category="AI",
                description=f"Synthetic skill {number}",
                stamp_type="FOCUSED",
                badge_asset_id=f"PASS-BADGE-{number}",
            )
            for number in (1, 2)
        ]
        source = AchievementSourceEvent.objects.create(
            source="PASSPORT_TEST",
            source_event_id="PASSPORT-EVENT-001",
            payload_sha256="a" * 64,
        )
        self.achievements = [
            VerifiedAchievement.objects.create(
                student=self.student,
                skill=skill,
                source_event=source,
                earned_on=date(2026, 10, 20),
                verification_status=VerifiedAchievement.VerificationStatus.VERIFIED,
            )
            for skill in self.skills
        ]

    def issue(self, number=1, **overrides):
        values = {
            "issuer_reference": self.issuer.reference,
            "idempotency_key": f"PASSPORT-CREDENTIAL-{number}",
            "achievement_ids": [self.achievements[number - 1].pk],
            "issued_at": self.now - timedelta(days=number),
        }
        values.update(overrides)
        return issue_credential(**values)


class PassportServiceTests(PassportDataMixin, TestCase):
    def test_one_permanent_passport_with_distinct_stable_identifiers(self):
        first, created = get_or_create_passport(student_id=self.student.pk)
        second, created_again = get_or_create_passport(student_id=self.student.pk)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertNotEqual(first.pk, first.public_reference)
        self.assertNotEqual(first.pk, self.student.pk)
        self.assertIsInstance(first.pk, uuid.UUID)

    def test_empty_passport_can_publish_its_first_version(self):
        version, created = publish_passport_version(
            student_id=self.student.pk,
            event_key="INITIAL-EMPTY",
            effective_at=self.now,
        )
        version.passport.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.status, PassportVersion.Status.ISSUED)
        self.assertEqual(version.credential_snapshots.count(), 0)
        self.assertEqual(version.skill_snapshots.count(), 0)
        self.assertEqual(version.passport.latest_version_id, version.pk)

    def test_multiple_credentials_and_skills_are_snapshotted_without_n_plus_one(self):
        self.issue(1)
        self.issue(2)
        with CaptureQueriesContext(connection) as queries:
            version, created = publish_passport_version(
                student_id=self.student.pk,
                event_key="TWO-CREDENTIALS",
                effective_at=self.now,
            )
        self.assertTrue(created)
        self.assertLessEqual(len(queries), 18)
        self.assertEqual(version.credential_snapshots.count(), 2)
        self.assertEqual(version.skill_snapshots.count(), 2)
        self.assertEqual(
            sum(row.skill_links.count() for row in version.credential_snapshots.all()), 2
        )

    def test_duplicate_event_and_unchanged_new_event_reuse_version(self):
        self.issue(1)
        first, first_created = publish_passport_version(
            student_id=self.student.pk, event_key="EVENT-1", effective_at=self.now
        )
        replay, replay_created = publish_passport_version(
            student_id=self.student.pk, event_key="EVENT-1", effective_at=self.now
        )
        unchanged, unchanged_created = publish_passport_version(
            student_id=self.student.pk, event_key="EVENT-2", effective_at=self.now
        )
        self.assertTrue(first_created)
        self.assertFalse(replay_created)
        self.assertFalse(unchanged_created)
        self.assertEqual({first.pk, replay.pk, unchanged.pk}, {first.pk})
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(PassportUpdateEvent.objects.count(), 2)

    def test_versions_are_sequential_and_historical_snapshots_survive_changes(self):
        credential = self.issue(1)
        first, _ = publish_passport_version(
            student_id=self.student.pk, event_key="ISSUED-1", effective_at=self.now
        )
        old_name = first.student_snapshot["first_name"]
        old_skill_name = first.skill_snapshots.get().skill_name

        self.student.first_name = "Changed"
        self.student.save(update_fields=["first_name"])
        self.skills[0].skill_name = "Changed skill"
        self.skills[0].save(update_fields=["skill_name"])
        second_credential = self.issue(2)
        second, _ = publish_passport_version(
            student_id=self.student.pk, event_key="ISSUED-2", effective_at=self.now
        )

        first.refresh_from_db()
        self.assertEqual(second.version_number, 2)
        self.assertEqual(first.student_snapshot["first_name"], old_name)
        self.assertEqual(first.skill_snapshots.get().skill_name, old_skill_name)
        self.assertCountEqual(
            second.credential_snapshots.values_list("credential_id", flat=True),
            [credential.pk, second_credential.pk],
        )

    @override_settings(
        CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:passport-test"
    )
    def test_revocation_creates_new_current_snapshot_and_preserves_history(self):
        credential = self.issue(1)
        issued_event = credential.lifecycle_events.get(event_type="ISSUED")
        first, _ = publish_passport_for_credential_event(
            lifecycle_event_id=issued_event.pk
        )
        revoke_credential(
            public_reference=credential.public_reference,
            actor=object(),
            reason="Synthetic revocation",
        )
        revoked_event = credential.lifecycle_events.get(event_type="REVOKED")
        second, _ = publish_passport_for_credential_event(
            lifecycle_event_id=revoked_event.pk
        )
        self.assertEqual(first.credential_snapshots.count(), 1)
        self.assertEqual(second.version_number, 2)
        self.assertEqual(second.credential_snapshots.count(), 0)
        self.assertEqual(second.skill_snapshots.count(), 0)

    def test_expired_credential_is_removed_from_new_snapshot(self):
        credential = self.issue(
            1,
            issued_at=self.now - timedelta(days=2),
            expires_at=self.now + timedelta(hours=1),
        )
        first, _ = publish_passport_version(
            student_id=self.student.pk,
            event_key="BEFORE-EXPIRY",
            effective_at=self.now,
        )
        second, _ = publish_passport_version(
            student_id=self.student.pk,
            event_key="AFTER-EXPIRY",
            effective_at=self.now + timedelta(hours=2),
        )
        self.assertEqual(first.credential_snapshots.get().credential_id, credential.pk)
        self.assertEqual(second.version_number, 2)
        self.assertEqual(second.credential_snapshots.count(), 0)

    def test_lifecycle_scheduler_waits_for_commit_then_publishes(self):
        credential = self.issue(1)
        event = credential.lifecycle_events.get(event_type="ISSUED")
        refresh = event.passport_refresh
        with patch(
            "apps.credentials.passport_refresh.process_passport_refresh_event"
        ) as process:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                schedule_passport_update_for_credential_event(lifecycle_event_id=event.pk)
        self.assertEqual(len(callbacks), 1)
        process.assert_called_once_with(refresh_id=refresh.pk)
        self.assertEqual(
            refresh.status,
            "PENDING",
        )

    def test_publication_rolls_back_completely_on_partial_failure(self):
        self.issue(1)
        with patch(
            "apps.passports.services.PassportUpdateEvent.objects.create",
            side_effect=IntegrityError("synthetic receipt failure"),
        ):
            with self.assertRaises(IntegrityError):
                publish_passport_version(
                    student_id=self.student.pk,
                    event_key="ROLLBACK",
                    effective_at=self.now,
                )
        self.assertEqual(DigitalPassport.objects.count(), 0)
        self.assertEqual(PassportVersion.objects.count(), 0)


class PassportDatabaseIntegrityTests(PassportDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_issued_versions_snapshots_and_receipts_are_immutable(self):
        self.issue(1)
        version, _ = publish_passport_version(
            student_id=self.student.pk, event_key="IMMUTABLE", effective_at=self.now
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportVersion.objects.filter(pk=version.pk).update(content_sha256="b" * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            version.credential_snapshots.all().delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportUpdateEvent.objects.filter(version=version).delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            version.delete()

    def test_database_rejects_a_credential_from_another_student(self):
        credential = self.issue(1)
        other = Student.objects.create(
            external_student_id="PASSPORT-TEST-OTHER",
            first_name="Other",
            last_name="Student",
            email="passport-other@example.org",
            program="Test",
            education_level="Test",
            student_status="Active",
        )
        passport = DigitalPassport.objects.create(student=other)
        draft = PassportVersion.objects.create(
            passport=passport, version_number=1, student_snapshot={"test": True}
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportVersionCredential.objects.create(
                version=draft,
                credential=credential,
                credential_public_reference=credential.public_reference,
                issuer_reference=credential.issuer_reference,
                issuer_name=credential.issuer_name,
                credential_issued_at=credential.issued_at,
                credential_expires_at=credential.expires_at,
            )

    def test_database_enforces_one_passport_per_student(self):
        DigitalPassport.objects.create(student=self.student)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DigitalPassport.objects.create(student=self.student)


class PassportConcurrencyTests(PassportDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_concurrent_passport_creation_returns_one_identity(self):
        barrier = Barrier(2)

        def create_one():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return str(get_or_create_passport(student_id=self.student.pk)[0].pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: create_one(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(DigitalPassport.objects.count(), 1)

    def test_concurrent_duplicate_publication_returns_one_version(self):
        self.issue(1)
        barrier = Barrier(2)

        def publish_one():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                version, _ = publish_passport_version(
                    student_id=self.student.pk,
                    event_key="CONCURRENT-EVENT",
                    effective_at=self.now,
                )
                return str(version.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: publish_one(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(PassportVersion.objects.count(), 1)
        # One lifecycle receipt plus one receipt for the concurrent logical event.
        self.assertEqual(PassportUpdateEvent.objects.filter(event_key="CONCURRENT-EVENT").count(), 1)
        self.assertEqual(PassportUpdateEvent.objects.count(), 2)


class PassportScaleTests(TestCase):
    def test_five_thousand_passport_identities_and_indexed_lookup(self):
        students = Student.objects.bulk_create(
            [
                Student(
                    external_student_id=f"SCALE-{number:05d}",
                    first_name="Synthetic",
                    last_name="Scale",
                    email=f"scale-{number:05d}@example.org",
                    program="Scale Test",
                    education_level="Test",
                    student_status="Active",
                )
                for number in range(5000)
            ],
            batch_size=1000,
        )
        DigitalPassport.objects.bulk_create(
            [DigitalPassport(student=student) for student in students], batch_size=1000
        )
        self.assertEqual(DigitalPassport.objects.count(), 5000)
        with self.assertNumQueries(1):
            passport = DigitalPassport.objects.select_related("student").get(
                student_id=students[2499].pk
            )
            self.assertEqual(passport.student.external_student_id, "SCALE-02499")
        with connection.cursor() as cursor:
            cursor.execute(
                "EXPLAIN SELECT * FROM digital_passports WHERE student_id = %s",
                [students[2499].pk],
            )
            plan = " ".join(row[0] for row in cursor.fetchall())
        self.assertIn("Index Scan", plan)
