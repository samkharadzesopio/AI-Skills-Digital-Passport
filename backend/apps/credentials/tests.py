import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from .models import Credential, CredentialAchievement, CredentialLifecycleEvent
from .services import IdempotencyConflict, issue_credential, revoke_credential
from .test_support import create_test_issuer


class CredentialDataMixin:
    def setUp(self):
        super().setUp()
        self.student = Student.objects.create(external_student_id="CRED-TEST-001", first_name="Test", last_name="Student", email="credential-test@example.org", program="Test", education_level="Test", student_status="Active")
        self.issuer = create_test_issuer("Synthetic Issuer")
        event = AchievementSourceEvent.objects.create(source="TEST", source_event_id="CRED-EVENT-001", payload_sha256="a" * 64)
        self.achievements = [VerifiedAchievement.objects.create(student=self.student, skill=Skill.objects.create(skill_code=f"CRED-{n}", skill_name=f"Synthetic {n}", category="Test", description="Synthetic test skill.", stamp_type="FOCUSED", badge_asset_id="TEST"), source_event=event, earned_on="2026-10-01", verification_status="VERIFIED") for n in range(1, 3)]


class CredentialServiceTests(CredentialDataMixin, TestCase):
    def issue(self, **kwargs):
        return issue_credential(issuer_reference=self.issuer.reference, idempotency_key="ISSUE-001", achievement_ids=[a.pk for a in self.achievements], **kwargs)

    def test_issue_links_multiple_verified_achievements_and_keeps_ids_separate(self):
        credential = self.issue()
        self.assertNotEqual(credential.pk, credential.public_reference)
        self.assertNotEqual(credential.pk, self.student.pk)
        self.assertEqual(credential.student_id, self.student.pk)
        self.assertCountEqual(credential.achievements.all(), self.achievements)
        self.assertEqual(list(credential.lifecycle_events.values_list("event_type", flat=True)), ["ISSUED"])

    def test_exact_idempotent_replay_returns_same_record_and_conflict_rejected(self):
        first = self.issue()
        replay = self.issue()
        self.assertEqual(first.pk, replay.pk)
        with self.assertRaises(IdempotencyConflict):
            issue_credential(issuer_reference=self.issuer.reference, idempotency_key="ISSUE-001", achievement_ids=[self.achievements[0].pk])

    def test_input_count_limit_and_duplicates_fail_before_writes(self):
        with self.assertRaises(ValidationError):
            issue_credential(issuer_reference=self.issuer.reference, idempotency_key="x", achievement_ids=[uuid.uuid4()] * 257)
        with self.assertRaises(ValidationError):
            issue_credential(issuer_reference=self.issuer.reference, idempotency_key="x", achievement_ids=[self.achievements[0].pk] * 2)
        self.assertEqual(Credential.objects.count(), 0)

    def test_unverified_achievement_rejected(self):
        self.achievements[0].verification_status = "PENDING"
        self.achievements[0].save(update_fields=["verification_status"])
        with self.assertRaises(ValidationError):
            self.issue()
        self.assertEqual(Credential.objects.count(), 0)

    def test_expiration_maps_to_verification_contract(self):
        issue_time = datetime.now(timezone.utc)
        credential = self.issue(issued_at=issue_time, expires_at=issue_time + timedelta(seconds=2))
        self.assertEqual(credential.verification_status_at(issue_time), "VALID")
        self.assertEqual(credential.verification_status_at(issue_time + timedelta(seconds=2)), "EXPIRED")


    def test_issue_rolls_back_credential_and_links_if_audit_write_fails(self):
        with patch("apps.credentials.services.CredentialLifecycleEvent.objects.create", side_effect=IntegrityError("synthetic failure")):
            with self.assertRaises(IntegrityError):
                self.issue()
        self.assertEqual(Credential.objects.count(), 0)
        self.assertEqual(CredentialAchievement.objects.count(), 0)

    def test_separate_idempotency_keys_allow_independent_credentials(self):
        first = self.issue()
        second = issue_credential(issuer_reference=self.issuer.reference, idempotency_key="ISSUE-002", achievement_ids=[a.pk for a in self.achievements])
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Credential.objects.count(), 2)

    def test_database_seals_links_after_issue(self):
        credential = self.issue()
        with self.assertRaises(IntegrityError), transaction.atomic():
            credential.achievement_links.all().delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialAchievement.objects.create(credential=credential, achievement=self.achievements[0])

    def test_database_blocks_mismatched_student_link(self):
        credential = self.issue()
        other = Student.objects.create(external_student_id="CRED-TEST-002", first_name="Other", last_name="Student", email="credential-test-2@example.org", program="Test", education_level="Test", student_status="Active")
        other_event = AchievementSourceEvent.objects.create(source="TEST", source_event_id="CRED-EVENT-OTHER", payload_sha256="b" * 64)
        other_achievement = VerifiedAchievement.objects.create(student=other, skill=self.achievements[0].skill, source_event=other_event, earned_on="2026-10-01", verification_status="VERIFIED")
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialAchievement.objects.create(credential=credential, achievement=other_achievement)

    def test_database_blocks_credential_fact_mutation_and_lifecycle_delete(self):
        credential = self.issue()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Credential.objects.filter(pk=credential.pk).update(issuer_name="tampered")
        with self.assertRaises(IntegrityError), transaction.atomic():
            credential.lifecycle_events.all().delete()

    def test_no_revocation_policy_fails_closed(self):
        credential = self.issue()
        with self.assertRaises(ImproperlyConfigured):
            revoke_credential(public_reference=credential.public_reference, actor=object(), reason="test reason")

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:test")
    def test_revocation_is_audited_and_exact_retry_is_idempotent(self):
        credential = self.issue()
        revoked = revoke_credential(public_reference=credential.public_reference, actor=object(), reason="Synthetic correction")
        again = revoke_credential(public_reference=credential.public_reference, actor=object(), reason="Synthetic correction")
        self.assertEqual(revoked.pk, again.pk)
        self.assertEqual(revoked.verification_status_at(datetime.now(timezone.utc)), "REVOKED")
        self.assertEqual(revoked.lifecycle_events.count(), 2)


class CredentialConcurrencyTests(CredentialDataMixin, TransactionTestCase):
    reset_sequences = True



    def test_conflicting_concurrent_request_for_same_key_is_rejected(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(2)
        ids = [[str(a.pk) for a in self.achievements], [str(self.achievements[0].pk)]]
        def issue_one(items):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return issue_credential(issuer_reference=self.issuer.reference, idempotency_key="CONFLICTING-RACE", achievement_ids=items).pk
            except IdempotencyConflict:
                return "conflict"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(issue_one, ids))
        self.assertEqual(sum(result == "conflict" for result in results), 1)
        self.assertEqual(Credential.objects.count(), 1)

    def test_concurrent_identical_issuance_returns_one_credential(self):
        barrier = Barrier(2)
        ids = [str(row.pk) for row in self.achievements]
        def issue_one():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return str(issue_credential(issuer_reference=self.issuer.reference, idempotency_key="CONCURRENT-1", achievement_ids=ids).pk)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: issue_one(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(CredentialLifecycleEvent.objects.count(), 1)
