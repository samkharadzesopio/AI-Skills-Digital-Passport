"""Authoritative represented-award dates and immutable legacy PDF contracts."""
import hashlib
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pymupdf
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from apps.credentials.services import issue_credential, revoke_credential
from apps.skills.models import AchievementSourceEvent, VerifiedAchievement
from .document_services import _render_context, _version_queryset, generate_passport_document
from .models import PassportVersion, PassportVersionCredential, PassportVersionCredentialSkill, PassportVersionSkill
from .services import _snapshot_payload, publish_passport_version
from .test_documents import DocumentDataMixin


class SnapshotEarnedDateTests(DocumentDataMixin, TransactionTestCase):
    def award(self, key, earned_on, *, represented=True):
        source = AchievementSourceEvent.objects.create(source="PDF_DATE_TEST", source_event_id=key,
            payload_sha256=hashlib.sha256(key.encode()).hexdigest())
        award = VerifiedAchievement.objects.create(student=self.student, skill=self.skill,
            source_event=source, earned_on=earned_on, verification_status="VERIFIED")
        if represented:
            return issue_credential(issuer_reference=self.issuer.reference, idempotency_key=key,
                achievement_ids=[award.pk], issued_at=self.now - timedelta(hours=1))
        return award

    def test_single_actual_earned_date_is_frozen_hashed_and_rendered(self):
        skill = self.version.skill_snapshots.get()
        self.assertEqual(skill.earned_on, date(2026, 10, 20))
        self.assertEqual(self.version.snapshot_schema_version, 2)
        context = _render_context(_version_queryset().get(pk=self.version.pk))
        self.assertEqual(context["skills"][0]["date_earned"], "2026-10-20")
        document = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        with pymupdf.open(self.storage.path(document.storage_key)) as pdf:
            self.assertIn("2026-10-20", pdf[3].get_text())
            self.assertNotIn("2026-10-24", pdf[3].get_text())
        from .services import _current_credential_rows
        with transaction.atomic():
            rows = _current_credential_rows(self.student.pk, self.now)
        payload, digest = _snapshot_payload(self.version.student_snapshot, rows)
        self.assertEqual(payload["credentials"][0]["skills"][0]["earned_on"], "2026-10-20")
        self.assertEqual(digest, self.version.content_sha256)
        rows[0].achievement_links.all()[0].achievement.earned_on = date(2026, 10, 19)
        self.assertNotEqual(_snapshot_payload(self.version.student_snapshot, rows)[1], digest)

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:date-test")
    def test_earliest_only_among_awards_represented_in_each_version(self):
        original_hash = self.version.content_sha256
        self.award("UNREPRESENTED-EARLIER", date(2026, 1, 1), represented=False)
        earliest = self.award("REPRESENTED-EARLIER", date(2026, 10, 10))
        self.award("REPRESENTED-LATER", date(2026, 10, 22))
        second, _ = publish_passport_version(student_id=self.student.pk, event_key="DATES-V2", effective_at=self.now)
        self.assertEqual(second.skill_snapshots.get().earned_on, date(2026, 10, 10))
        from .services import _current_credential_rows
        with transaction.atomic():
            represented = _current_credential_rows(self.student.pk, self.now)
        payload, digest = _snapshot_payload(second.student_snapshot, represented)
        self.assertEqual(digest, second.content_sha256)
        self.assertEqual({skill['earned_on'] for credential in payload['credentials']
            for skill in credential['skills']}, {'2026-10-10'})
        self.assertEqual(_render_context(_version_queryset().get(pk=second.pk))['skills'][0]['date_earned'], '2026-10-10')
        revoke_credential(public_reference=earliest.public_reference, actor=object(), reason="Synthetic date regression")
        third, _ = publish_passport_version(student_id=self.student.pk, event_key="DATES-V3", effective_at=self.now)
        self.assertEqual(third.skill_snapshots.get().earned_on, date(2026, 10, 20))
        self.version.refresh_from_db()
        self.assertEqual(self.version.content_sha256, original_hash)
        self.assertEqual(self.version.skill_snapshots.get().earned_on, date(2026, 10, 20))
        self.assertEqual(second.skill_snapshots.get().earned_on, date(2026, 10, 10))
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.skill_snapshots.update(earned_on=date(2026, 1, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportVersion.objects.filter(pk=second.pk).update(snapshot_schema_version=1)

    def test_missing_authoritative_date_has_no_issuance_fallback(self):
        from .services import _current_credential_rows
        with transaction.atomic():
            rows = _current_credential_rows(self.student.pk, self.now)
        rows[0].achievement_links.all()[0].achievement.earned_on = None
        with self.assertRaisesMessage(ValidationError, "authoritative earned date"):
            _snapshot_payload(self.version.student_snapshot, rows)
        rows[0].achievement_links.all()[0].achievement.earned_on = date(2099, 1, 1)
        with self.assertRaisesMessage(ValidationError, "dates cannot follow issuance"):
            _snapshot_payload(self.version.student_snapshot, rows)
        version = _version_queryset().get(pk=self.version.pk)
        version.skill_snapshots.all()[0].earned_on = None
        with self.assertRaisesMessage(ValidationError, "authoritative earned date"):
            _render_context(version)
        version.snapshot_schema_version = 1
        context = _render_context(version)
        self.assertEqual(context["skills"][0]["date_earned"], "Not recorded in snapshot")
        version.student_snapshot["last_name"] = ""
        with self.assertRaisesMessage(ValidationError, "mandatory student data"):
            _render_context(version)

    def test_database_rejects_missing_or_substituted_earned_dates(self):
        source_credential = self.version.credential_snapshots.get()
        source_skill = self.version.skill_snapshots.get()
        for earned_on in (None, date(2026, 10, 24)):
            with self.assertRaisesMessage(IntegrityError, "earliest represented approved awards"), transaction.atomic():
                draft = PassportVersion.objects.create(passport=self.version.passport,
                    version_number=2, student_snapshot=self.version.student_snapshot)
                credential = PassportVersionCredential.objects.create(version=draft, credential=self.credential,
                    credential_public_reference=source_credential.credential_public_reference,
                    issuer_reference=source_credential.issuer_reference, issuer_name=source_credential.issuer_name,
                    credential_issued_at=source_credential.credential_issued_at)
                skill = PassportVersionSkill.objects.create(version=draft, skill=self.skill,
                    skill_code=source_skill.skill_code, skill_name=source_skill.skill_name,
                    category=source_skill.category, subcategory=source_skill.subcategory,
                    description=source_skill.description, stamp_type=source_skill.stamp_type,
                    badge_asset_id=source_skill.badge_asset_id, earned_on=earned_on)
                PassportVersionCredentialSkill.objects.create(credential_snapshot=credential, skill_snapshot=skill)
                PassportVersion.objects.filter(pk=draft.pk).update(status="ISSUED", issued_at=self.now,
                    content_sha256="a" * 64)

    def test_migration_preserves_legacy_hashes_and_artifacts_and_uses_truthful_label(self):
        document = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        original = Path(self.storage.path(document.storage_key)).read_bytes()
        content_hash, pdf_hash = self.version.content_sha256, document.pdf_sha256
        from apps.students.models import Student
        Student.objects.filter(pk=self.student.pk).update(program="Legacy without PDF")
        unpublished, _ = publish_passport_version(student_id=self.student.pk,
            event_key="LEGACY-NO-PDF", effective_at=self.now + timedelta(hours=1))
        executor = MigrationExecutor(connection)
        executor.migrate([("passports", "0008_lifecycle_integrity")])
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("passports", "0009_snapshot_earned_on")])
            legacy = _version_queryset().get(pk=self.version.pk)
            self.assertEqual(legacy.snapshot_schema_version, 1)
            self.assertIsNone(legacy.skill_snapshots.get().earned_on)
            self.assertEqual(legacy.content_sha256, content_hash)
            with patch("apps.passports.document_services.render_passport_pdf") as renderer:
                reused = generate_passport_document(passport_version_id=legacy.pk, storage=self.storage)
            renderer.assert_not_called()
            self.assertEqual(reused.pk, document.pk)
            self.assertEqual(reused.pdf_sha256, pdf_hash)
            self.assertEqual(Path(self.storage.path(reused.storage_key)).read_bytes(), original)
            # A legacy version without a registered PDF gets its own newly hashed
            # artifact; its missing date never falls back to a live achievement.
            created = generate_passport_document(passport_version_id=unpublished.pk, storage=self.storage)
            with pymupdf.open(self.storage.path(created.storage_key)) as pdf:
                self.assertIn("Not recorded in snapshot", " ".join(pdf[3].get_text().split()))
            self.assertNotEqual(created.pdf_sha256, pdf_hash)
        finally:
            MigrationExecutor(connection).migrate([("passports", "0009_snapshot_earned_on")])
