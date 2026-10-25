import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command, CommandError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.passports.models import DigitalPassport, PassportUpdateEvent, PassportVersion
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from .models import (
    BTU_ISSUER_DISPLAY_NAME,
    BTU_ISSUER_REFERENCE,
    Credential,
    CredentialIssuer,
    CredentialIssuerProvisioningEvent,
    CredentialLifecycleEvent,
    CredentialPassportRefresh,
)
from .passport_refresh import (
    enqueue_expired_passport_refreshes,
    process_passport_refresh_event,
    process_pending_passport_refreshes,
    retry_failed_passport_refreshes,
    _retry_database,
)
from .services import issue_credential, provision_btu_issuer, revoke_credential
from .test_support import SyntheticCredentialAdmin
from .tests import CredentialDataMixin


class RefreshTestDataMixin(CredentialDataMixin):
    def issue(self, **kwargs):
        return issue_credential(
            issuer_reference=self.issuer.reference,
            idempotency_key="REFRESH-TEST-ISSUE",
            achievement_ids=[row.pk for row in self.achievements],
            **kwargs,
        )


class PassportRefreshOutboxTests(RefreshTestDataMixin, TestCase):
    def test_issuance_creates_transactional_durable_refresh(self):
        credential = self.issue()
        event = credential.lifecycle_events.get(event_type="ISSUED")
        refresh = CredentialPassportRefresh.objects.get(lifecycle_event=event)
        self.assertEqual(refresh.student_id, credential.student_id)
        self.assertEqual(refresh.event_key, f"credential-lifecycle:{event.pk}")
        self.assertEqual(refresh.status, CredentialPassportRefresh.Status.PENDING)
        self.assertEqual(refresh.source_occurred_at, event.occurred_at)

    def test_user_controlled_issuer_reference_is_rejected(self):
        with self.assertRaises(ValidationError):
            issue_credential(
                issuer_reference="ATTACKER-CONTROLLED",
                idempotency_key="SPOOF-TEST",
                achievement_ids=[row.pk for row in self.achievements],
            )
        self.assertEqual(Credential.objects.count(), 0)

    def test_issue_and_refresh_request_roll_back_together(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.issue()
                raise RuntimeError("synthetic transaction abort")
        self.assertEqual(Credential.objects.count(), 0)
        self.assertEqual(CredentialLifecycleEvent.objects.count(), 0)
        self.assertEqual(CredentialPassportRefresh.objects.count(), 0)

    def test_duplicate_processing_is_durable_and_idempotent(self):
        credential = self.issue()
        event = credential.lifecycle_events.get(event_type="ISSUED")
        refresh = CredentialPassportRefresh.objects.get(lifecycle_event=event)

        self.assertEqual(process_passport_refresh_event(refresh_id=refresh.pk), "completed")
        self.assertEqual(process_passport_refresh_event(refresh_id=refresh.pk), "completed")
        refresh.refresh_from_db()
        receipt = PassportUpdateEvent.objects.get(event_key=refresh.event_key)
        self.assertEqual(refresh.status, CredentialPassportRefresh.Status.COMPLETED)
        self.assertEqual(receipt.source_occurred_at, event.occurred_at)
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(receipt.version.credential_snapshots.count(), 1)

    def test_pending_request_recovers_after_worker_was_unavailable(self):
        credential = self.issue()
        refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential,
            lifecycle_event__event_type="ISSUED",
        )
        result = process_pending_passport_refreshes(batch_size=10)
        self.assertEqual(result["completed"], 1)
        refresh.refresh_from_db()
        self.assertEqual(
            refresh.status,
            CredentialPassportRefresh.Status.COMPLETED,
            f"callback state={refresh.status}; available_at={refresh.available_at}; now={timezone.now()}; in_atomic={connection.in_atomic_block}",
        )

    @override_settings(PASSPORT_REFRESH_RETRY_BASE_SECONDS=0.1)
    def test_worker_failure_is_recorded_and_recoverable(self):
        credential = self.issue()
        refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential,
            lifecycle_event__event_type="ISSUED",
        )
        with patch(
            "apps.passports.services.publish_passport_for_credential_event",
            side_effect=RuntimeError("synthetic passport failure"),
        ):
            self.assertEqual(process_passport_refresh_event(refresh_id=refresh.pk), "PENDING")
        refresh.refresh_from_db()
        self.assertEqual(refresh.status, CredentialPassportRefresh.Status.PENDING)
        self.assertEqual(refresh.attempt_count, 1)
        self.assertEqual(refresh.last_error_code, "RuntimeError")
        time.sleep(0.25)
        self.assertEqual(process_passport_refresh_event(refresh_id=refresh.pk), "completed")

    def test_terminal_failure_can_be_explicitly_requeued(self):
        refresh = CredentialPassportRefresh.objects.create(
            event_key=f"credential-expiration:{self.student.pk}:123",
            source_type=CredentialPassportRefresh.SourceType.EXPIRATION,
            student=self.student,
            source_occurred_at=timezone.now(),
            max_attempts=1,
        )
        with patch(
            "apps.passports.services.publish_passport_version",
            side_effect=RuntimeError("synthetic terminal failure"),
        ):
            self.assertEqual(process_passport_refresh_event(refresh_id=refresh.pk), "FAILED")
        refresh.refresh_from_db()
        self.assertEqual(refresh.attempt_count, 1)
        self.assertEqual(retry_failed_passport_refreshes(limit=1), 1)
        refresh.refresh_from_db()
        self.assertEqual(refresh.status, CredentialPassportRefresh.Status.PENDING)
        self.assertEqual(refresh.attempt_count, 0)

    @override_settings(
        CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:outbox-test"
    )
    def test_revocation_creates_a_distinct_durable_refresh(self):
        credential = self.issue()
        revoke_credential(
            public_reference=credential.public_reference,
            actor=object(),
            reason="Synthetic revocation",
        )
        refreshes = CredentialPassportRefresh.objects.filter(
            lifecycle_event__credential=credential
        ).order_by("source_occurred_at")
        self.assertEqual(refreshes.count(), 2)
        self.assertCountEqual(
            refreshes.values_list("lifecycle_event__event_type", flat=True),
            ["ISSUED", "REVOKED"],
        )

    @override_settings(
        CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:ordering-test"
    )
    def test_out_of_order_old_event_rebuilds_from_current_credential_state(self):
        credential = self.issue()
        revoke_credential(
            public_reference=credential.public_reference,
            actor=object(),
            reason="Synthetic out-of-order revocation",
        )
        revoked_refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__event_type="REVOKED",
            lifecycle_event__credential=credential,
        )
        issued_refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__event_type="ISSUED",
            lifecycle_event__credential=credential,
        )

        self.assertEqual(process_passport_refresh_event(refresh_id=revoked_refresh.pk), "completed")
        self.assertEqual(process_passport_refresh_event(refresh_id=issued_refresh.pk), "completed")
        passport = DigitalPassport.objects.get(student=self.student)
        self.assertEqual(passport.latest_version.credential_snapshots.count(), 0)
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(PassportUpdateEvent.objects.count(), 2)

    def test_database_protects_refresh_source_identity_and_delete(self):
        credential = self.issue()
        refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialPassportRefresh.objects.filter(pk=refresh.pk).update(
                event_key="credential-lifecycle:tampered"
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            refresh.delete()


class PassportRefreshConcurrencyTests(RefreshTestDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_issue_commits_before_robust_callback_publishes(self):
        callback_results = []

        def observe_callback(refresh_id):
            callback_results.append(
                process_passport_refresh_event(refresh_id=refresh_id)
            )

        with patch(
            "apps.credentials.passport_refresh.process_passport_refresh_event",
            side_effect=observe_callback,
        ) as callback_processor:
            credential = self.issue()
        refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential
        )
        refresh.refresh_from_db()
        self.assertEqual(callback_processor.call_count, 1)
        self.assertEqual(callback_results, ["completed"])
        self.assertEqual(
            refresh.status,
            CredentialPassportRefresh.Status.COMPLETED,
        )
        passport = DigitalPassport.objects.get(student=self.student)
        self.assertEqual(passport.latest_version.credential_snapshots.count(), 1)

    def test_two_workers_cannot_claim_the_same_refresh_at_once(self):
        with patch("apps.passports.services.transaction.on_commit"):
            credential = self.issue()
        refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential
        )
        entered = Event()
        release = Event()
        original_publish = __import__(
            "apps.credentials.passport_refresh", fromlist=["_publish_refresh"]
        )._publish_refresh

        def slow_publish(refresh_id):
            entered.set()
            if not release.wait(timeout=10):
                raise TimeoutError("synthetic worker wait timed out")
            original_publish(refresh_id)

        def worker():
            close_old_connections()
            try:
                return process_passport_refresh_event(refresh_id=refresh.pk)
            finally:
                close_old_connections()

        with patch("apps.credentials.passport_refresh._publish_refresh", side_effect=slow_publish):
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(worker)
                self.assertTrue(entered.wait(timeout=10))
                second = process_passport_refresh_event(refresh_id=refresh.pk)
                release.set()
                self.assertEqual(first.result(timeout=10), "completed")
        self.assertEqual(second, "processing")
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(
            CredentialPassportRefresh.objects.get(pk=refresh.pk).status,
            CredentialPassportRefresh.Status.COMPLETED,
        )

    def test_deadlock_retry_is_bounded_to_three_database_attempts(self):
        class SyntheticDeadlock(Exception):
            sqlstate = "40P01"

        error = DatabaseError("synthetic deadlock")
        error.__cause__ = SyntheticDeadlock()
        operation = Mock(side_effect=[error, error, "recovered"])
        with patch("apps.credentials.passport_refresh.time.sleep"):
            self.assertEqual(_retry_database(operation), "recovered")
        self.assertEqual(operation.call_count, 3)


class CredentialExpirationRefreshTests(RefreshTestDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_expiration_scan_queues_bounded_current_snapshot_refresh(self):
        expires_at = timezone.now() + timezone.timedelta(seconds=1)
        with patch("apps.passports.services.transaction.on_commit"):
            credential = self.issue(expires_at=expires_at)
        lifecycle_refresh = CredentialPassportRefresh.objects.get(
            lifecycle_event__credential=credential,
            lifecycle_event__event_type="ISSUED",
        )
        self.assertEqual(
            process_passport_refresh_event(refresh_id=lifecycle_refresh.pk), "completed"
        )
        time.sleep(1.1)
        scan_time = expires_at + timezone.timedelta(seconds=1)
        self.assertEqual(enqueue_expired_passport_refreshes(limit=1, now=scan_time), 1)
        self.assertEqual(enqueue_expired_passport_refreshes(limit=1, now=scan_time), 0)
        self.assertEqual(credential.verification_status_at(scan_time), "EXPIRED")

        result = process_pending_passport_refreshes(batch_size=10)
        self.assertGreaterEqual(result["completed"], 1)
        passport = DigitalPassport.objects.get(student=self.student)
        self.assertEqual(passport.latest_version.credential_snapshots.count(), 0)
        self.assertEqual(
            CredentialPassportRefresh.objects.filter(
                source_type=CredentialPassportRefresh.SourceType.EXPIRATION,
                status=CredentialPassportRefresh.Status.COMPLETED,
            ).count(),
            1,
        )

    def test_expiration_scan_predicate_can_use_partial_credential_index(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL enable_seqscan = off")
                cursor.execute(
                    "EXPLAIN (COSTS OFF) SELECT id FROM credentials "
                    "WHERE status = 'ISSUED' AND expires_at IS NOT NULL "
                    "AND expires_at <= %s",
                    [timezone.now()],
                )
                plan = " ".join(row[0] for row in cursor.fetchall())
        self.assertIn("cred_issued_expiry_idx", plan)


class TrustedIssuerProvisioningTests(TestCase):
    def test_untrusted_canonical_row_fails_closed_for_issuance(self):
        student = Student.objects.create(
            external_student_id="UNTRUSTED-ISSUER-001",
            first_name="Synthetic",
            last_name="Student",
            email="untrusted-issuer@example.org",
            program="Test",
            education_level="Test",
            student_status="Active",
        )
        skill = Skill.objects.create(
            skill_code="UNTRUSTED-SKILL",
            skill_name="Synthetic Skill",
            category="Test",
            description="Synthetic test skill.",
            stamp_type="FOCUSED",
            badge_asset_id="UNTRUSTED-BADGE",
        )
        source = AchievementSourceEvent.objects.create(
            source="TEST",
            source_event_id="UNTRUSTED-ISSUER-EVENT",
            payload_sha256="d" * 64,
        )
        achievement = VerifiedAchievement.objects.create(
            student=student,
            skill=skill,
            source_event=source,
            earned_on="2026-10-01",
            verification_status="VERIFIED",
        )
        CredentialIssuer.objects.create(
            reference=BTU_ISSUER_REFERENCE,
            display_name="Untrusted BTU",
            is_trusted=False,
        )
        with self.assertRaises(ImproperlyConfigured):
            issue_credential(
                issuer_reference=BTU_ISSUER_REFERENCE,
                idempotency_key="UNTRUSTED-ISSUE",
                achievement_ids=[achievement.pk],
            )

    def test_authorized_command_is_idempotent_and_audited(self):
        user = get_user_model().objects.create_admin_user(
            email="issuer-admin@btu.edu.ge",
            password="Synthetic-test-password-123!",
            permission_codenames={"manage_credentials"},
        )

        call_command("provision_btu_issuer", actor_email=user.email)
        call_command("provision_btu_issuer", actor_email=user.email)
        call_command(
            "provision_btu_issuer",
            actor_email=user.email,
            display_name="Synthetic BTU Issuer Update",
        )
        issuer = CredentialIssuer.objects.get(reference=BTU_ISSUER_REFERENCE)
        self.assertTrue(issuer.is_trusted)
        self.assertEqual(issuer.display_name, "Synthetic BTU Issuer Update")
        self.assertEqual(CredentialIssuerProvisioningEvent.objects.count(), 2)
        self.assertEqual(
            CredentialIssuerProvisioningEvent.objects.order_by("occurred_at").first().actor_user_id,
            str(user.pk),
        )
        renamed = CredentialIssuerProvisioningEvent.objects.get(
            event_type=CredentialIssuerProvisioningEvent.EventType.DISPLAY_NAME_CHANGED
        )
        self.assertEqual(renamed.previous_display_name, BTU_ISSUER_DISPLAY_NAME)

    def test_unprivileged_user_cannot_provision_trusted_issuer(self):
        user = get_user_model().objects.create_user(
            email="issuer-student@btu.edu.ge",
            password="Synthetic-test-password-123!",
            is_email_verified=True,
        )
        with self.assertRaises(CommandError):
            call_command("provision_btu_issuer", actor_email=user.email)
        self.assertFalse(
            CredentialIssuer.objects.filter(
                reference=BTU_ISSUER_REFERENCE, is_trusted=True
            ).exists()
        )

    def test_unauthorized_or_untrusted_issuer_cannot_issue(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialIssuer.objects.create(
                reference=BTU_ISSUER_REFERENCE,
                display_name="Unprovisioned BTU",
                is_trusted=True,
            )

    def test_trusted_issuer_identity_and_audit_are_database_protected(self):
        issuer, _ = provision_btu_issuer(
            actor=SyntheticCredentialAdmin(),
            display_name="Synthetic BTU issuer",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialIssuer.objects.filter(pk=issuer.pk).update(is_trusted=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialIssuerProvisioningEvent.objects.filter(issuer=issuer).delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialIssuerProvisioningEvent.objects.filter(issuer=issuer).update(
                display_name="Tampered audit"
            )
