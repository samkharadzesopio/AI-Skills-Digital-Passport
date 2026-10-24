import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.students.models import Student

from . import achievement_services as service
from .achievement_limits import get_achievement_limits
from .models import AchievementSourceEvent, Skill, VerifiedAchievement
from .test_achievements import AchievementDataMixin


class AchievementLimitTests(AchievementDataMixin, TestCase):
    def assert_invalid_without_database(self, **change):
        with self.assertNumQueries(0), self.assertRaises(ValidationError), patch.object(service, "_record_once") as write:
            service.record_verified_achievements(**self.request_data(**change))
        write.assert_not_called()

    def test_default_skill_limit_rejects_oversized_batches_before_database_access(self):
        self.assertEqual(get_achievement_limits().max_skills_per_event, 256)
        self.assert_invalid_without_database(approved_skill_codes=[f"TEST-{i}" for i in range(257)])

    @override_settings(ACHIEVEMENT_LIMITS={"max_skills_per_event": 2})
    def test_configured_skill_boundary(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data())[1])
        self.assert_invalid_without_database(approved_skill_codes=["ONE", "TWO", "THREE"])

    def test_event_identifier_database_boundary(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(source_event_id="E" * 255))[1])
        self.assert_invalid_without_database(source_event_id="E" * 256)

    @override_settings(ACHIEVEMENT_LIMITS={"max_event_id_length": 8, "max_evidence_reference_length": 12})
    def test_configured_identifier_and_reference_boundaries(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(
            source_event_id="E" * 8, evidence_reference="R" * 12,
        ))[1])
        self.assert_invalid_without_database(source_event_id="E" * 9)
        self.assert_invalid_without_database(source_event_id="E", evidence_reference="R" * 13)

    def test_default_evidence_reference_boundary(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(evidence_reference="R" * 4096))[1])
        self.assert_invalid_without_database(evidence_reference="R" * 4097)

    @override_settings(ACHIEVEMENT_LIMITS={"max_evidence_bytes": 16})
    def test_canonical_json_byte_boundary(self):
        evidence = {"x": "a" * 8}
        self.assertEqual(len(json.dumps(evidence, separators=(",", ":")).encode()), 16)
        self.assertTrue(service.record_verified_achievements(**self.request_data(evidence=evidence))[1])
        self.assert_invalid_without_database(evidence={"x": "a" * 9})

    @override_settings(ACHIEVEMENT_LIMITS={"max_evidence_bytes": 14})
    def test_json_byte_budget_counts_unicode_escapes(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(evidence={"x": "é"}))[1])
        self.assert_invalid_without_database(evidence={"x": "éé"})

    @override_settings(ACHIEVEMENT_LIMITS={"max_evidence_depth": 3})
    def test_evidence_nesting_is_bounded(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(evidence={"x": {"y": 1}}))[1])
        self.assert_invalid_without_database(evidence={"x": {"y": {"z": 1}}})

    @override_settings(ACHIEVEMENT_LIMITS={"max_evidence_nodes": 4})
    def test_evidence_node_count_is_bounded(self):
        self.assertTrue(service.record_verified_achievements(**self.request_data(evidence={"x": [1, 2]}))[1])
        self.assert_invalid_without_database(evidence={"x": [1, 2, 3]})

    def test_invalid_postgresql_text_and_non_json_values_fail_before_database_access(self):
        cyclic = {}
        cyclic["self"] = cyclic
        for change in (
            {"source_event_id": "bad\x00id"}, {"evidence_reference": "bad\ud800"},
            {"evidence": {"x": "bad\x00text"}}, {"evidence": {"\ud800": 1}},
            {"evidence": {1: "non-string key"}}, {"evidence": {"x": float("inf")}},
            {"evidence": cyclic}, {"evidence": {"x": "a" * 262145}},
        ):
            with self.subTest(fields=list(change)):
                self.assert_invalid_without_database(**change)

    def test_invalid_configuration_is_explicit_and_does_not_touch_database(self):
        for configured in (
            [], {"unknown": 1}, {"max_skills_per_event": 0}, {"bulk_batch_size": True},
            {"max_event_id_length": 256}, {"max_evidence_bytes": 1}, {"retry_attempts": 6},
            {"retry_base_delay": float("nan")}, {"retry_max_delay": 3},
            {"retry_base_delay": 1, "retry_max_delay": 0.1},
        ):
            with self.subTest(config=configured), override_settings(ACHIEVEMENT_LIMITS=configured):
                with self.assertNumQueries(0), self.assertRaises(ImproperlyConfigured):
                    service.record_verified_achievements(**self.request_data())

    def test_json_snapshot_is_not_affected_by_later_caller_mutation(self):
        evidence = {"items": ["original"]}
        service.record_verified_achievements(**self.request_data(evidence=evidence))
        evidence["items"].append("later")
        self.assertEqual(AchievementSourceEvent.objects.get().evidence, {"items": ["original"]})


@skipUnless(connection.vendor == "postgresql", "Requires isolated PostgreSQL")
class AchievementTransactionTests(AchievementDataMixin, TransactionTestCase):
    def test_preparation_and_fingerprint_are_outside_write_transaction(self):
        original_prepare = service._prepare_request
        original_fingerprint = service._fingerprint
        original_resolve = service._resolve_identities
        resolution_scopes = []

        def prepare(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            return original_prepare(**kwargs)

        def fingerprint(*args):
            self.assertFalse(connection.in_atomic_block)
            return original_fingerprint(*args)

        def resolve(request):
            resolution_scopes.append(connection.in_atomic_block)
            return original_resolve(request)

        with patch.object(service, "_prepare_request", side_effect=prepare), patch.object(
            service, "_fingerprint", side_effect=fingerprint,
        ), patch.object(service, "_resolve_identities", side_effect=resolve):
            service.record_verified_achievements(**self.request_data())
        self.assertEqual(resolution_scopes, [False, True])

    def test_stale_identity_snapshot_cannot_create_mismatched_awards(self):
        original = service._resolve_identities
        calls = 0

        def resolve(request):
            nonlocal calls
            calls += 1
            identity = original(request)
            return identity if calls == 1 else (uuid.uuid4(), identity[1])

        with patch.object(service, "_resolve_identities", side_effect=resolve), self.assertRaises(ValidationError):
            service.record_verified_achievements(**self.request_data())
        self.assertFalse(AchievementSourceEvent.objects.exists())

    def test_format_one_receipts_created_before_optimization_still_replay(self):
        request = self.request_data()
        skill_uuids = sorted(s.pk for s in self.skills)
        legacy_payload = {
            "format": 1, "student_uuid": str(self.student.pk),
            "skill_uuids": [str(pk) for pk in skill_uuids],
            "earned_on": request["earned_on"].isoformat(), "verification_status": "VERIFIED",
            "course_id": request["course_id"], "evidence_reference": request["evidence_reference"],
            "evidence": request["evidence"],
        }
        legacy_hash = hashlib.sha256(json.dumps(
            legacy_payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        event = self.event(payload_sha256=legacy_hash, evidence=request["evidence"], evidence_reference=request["evidence_reference"])
        original = [VerifiedAchievement.objects.create(**self.award_data(
            event, skill=skill, verification_status="VERIFIED",
        )) for skill in self.skills]
        replay, created = service.record_verified_achievements(**request)
        self.assertFalse(created)
        self.assertCountEqual([a.pk for a in replay], [a.pk for a in original])

    @override_settings(ACHIEVEMENT_LIMITS={"bulk_batch_size": 1})
    def test_failure_in_later_insert_chunk_rolls_back_entire_event(self):
        inserts = 0

        def fail_second(execute, sql, params, many, context):
            nonlocal inserts
            if sql.startswith('INSERT INTO "verified_achievements"'):
                inserts += 1
                if inserts == 2:
                    raise RuntimeError("Synthetic second-chunk failure")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(fail_second), self.assertRaises(RuntimeError):
            service.record_verified_achievements(**self.request_data())
        self.assertEqual(inserts, 2)
        self.assertFalse(AchievementSourceEvent.objects.exists())
        self.assertFalse(VerifiedAchievement.objects.exists())

    def test_retryable_postgresql_errors_roll_back_before_retry(self):
        original_bulk = VerifiedAchievement.objects.bulk_create
        for state in ("40P01", "40001"):
            calls = 0

            def insert(awards, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    awards[0].save(force_insert=True)
                    with connection.cursor() as cursor:
                        cursor.execute("DO $$ BEGIN RAISE EXCEPTION 'synthetic retry' USING ERRCODE = '" + state + "'; END $$")
                return original_bulk(awards, **kwargs)

            def sleep(delay):
                self.assertFalse(connection.in_atomic_block)
                self.assertFalse(AchievementSourceEvent.objects.filter(source_event_id=state).exists())
                self.assertLessEqual(delay, 0.25)

            with self.subTest(state=state), patch.object(VerifiedAchievement.objects, "bulk_create", side_effect=insert), patch.object(service.time, "sleep", side_effect=sleep) as sleeping:
                awards, created = service.record_verified_achievements(**self.request_data(source_event_id=state))
            self.assertTrue(created)
            self.assertEqual(len(awards), 2)
            self.assertEqual(calls, 2)
            self.assertEqual(sleeping.call_count, 1)

    def test_retry_exhaustion_is_bounded(self):
        def fail(*args):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("DO $$ BEGIN RAISE EXCEPTION 'synthetic retry' USING ERRCODE = '40001'; END $$")

        with patch.object(service, "_record_once", side_effect=fail) as write, patch.object(service.time, "sleep") as sleep:
            with self.assertRaises(DatabaseError):
                service.record_verified_achievements(**self.request_data())
        self.assertEqual(write.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertFalse(AchievementSourceEvent.objects.exists())

    def test_non_retryable_database_errors_and_conflicts_are_not_retried(self):
        for state in ("23514", "55P03", "08006"):
            def fail(*args):
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute("DO $$ BEGIN RAISE EXCEPTION 'synthetic failure' USING ERRCODE = '" + state + "'; END $$")

            with self.subTest(state=state), patch.object(service, "_record_once", side_effect=fail) as write, patch.object(service.time, "sleep") as sleep:
                with self.assertRaises(DatabaseError):
                    service.record_verified_achievements(**self.request_data())
                self.assertEqual(write.call_count, 1)
                sleep.assert_not_called()
        service.record_verified_achievements(**self.request_data())
        with patch.object(service.time, "sleep") as sleep, self.assertRaises(service.SourceEventConflict):
            service.record_verified_achievements(**self.request_data(course_id="CONFLICT"))
        sleep.assert_not_called()

    def test_outer_transaction_caller_owns_retry(self):
        def fail(*args):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("DO $$ BEGIN RAISE EXCEPTION 'synthetic retry' USING ERRCODE = '40001'; END $$")

        with patch.object(service, "_record_once", side_effect=fail) as write, patch.object(service.time, "sleep") as sleep:
            with self.assertRaises(DatabaseError), transaction.atomic():
                service.record_verified_achievements(**self.request_data())
        self.assertEqual(write.call_count, 1)
        sleep.assert_not_called()

    def test_real_two_session_deadlock_is_retried_after_rollback(self):
        original_write = service._record_once
        barrier = Barrier(2)
        attempts = {}
        delays = []

        def contend(request, identities, fingerprint, limits):
            key = request.source_event_id
            attempts[key] = attempts.get(key, 0) + 1
            ids = [self.student.pk, self.other_student.pk]
            if key == "DEADLOCK-B":
                ids.reverse()
            # Test-only conflicting writer locks, deliberately opposite in order.
            with transaction.atomic():
                Student.objects.select_for_update().only("id").get(pk=ids[0])
                if attempts[key] == 1:
                    barrier.wait(timeout=10)
                Student.objects.select_for_update().only("id").get(pk=ids[1])
                return original_write(request, identities, fingerprint, limits)

        def sleep(delay):
            self.assertFalse(connection.in_atomic_block)
            delays.append(delay)

        def worker(event_id):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")
                return service.record_verified_achievements(**self.request_data(source_event_id=event_id))[1]
            finally:
                connection.close()

        with patch.object(service, "_record_once", side_effect=contend), patch.object(service.time, "sleep", side_effect=sleep):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(worker, ("DEADLOCK-A", "DEADLOCK-B")))
        self.assertEqual(results, [True, True])
        self.assertCountEqual(attempts.values(), [1, 2])
        self.assertEqual(len(delays), 1)
        self.assertEqual(AchievementSourceEvent.objects.count(), 2)
        self.assertEqual(VerifiedAchievement.objects.count(), 4)


@skipUnless(connection.vendor == "postgresql", "Requires isolated PostgreSQL")
class AchievementQueryTests(AchievementDataMixin, TransactionTestCase):
    def test_creation_and_replay_query_budgets_and_narrow_identity_reads(self):
        for expected, created in ((9, True), (6, False)):
            with CaptureQueriesContext(connection) as queries:
                awards, actual = service.record_verified_achievements(**self.request_data())
                self.assertEqual(len(awards), 2)
                self.assertEqual(actual, created)
                # Ordinary award fields must not trigger deferred per-row reads.
                [(a.pk, a.student_id, a.skill_id, a.earned_on, a.verification_status, a.created_at) for a in awards]
            self.assertEqual(len(queries), expected)
            sql = [q["sql"] for q in queries]
            self.assertNotIn('"email"', sql[0])
            self.assertNotIn('"description"', sql[0])
            self.assertEqual(sum("FOR UPDATE" in q for q in sql), 1)

    def test_more_skills_do_not_create_n_plus_one_queries(self):
        extra = [Skill.objects.create(
            skill_code=f"EXTRA-{n}", skill_name="Synthetic", category="Test", description="Test",
            stamp_type="FOCUSED", badge_asset_id="TEST",
        ) for n in range(8)]
        codes = [s.skill_code for s in self.skills + extra]
        for expected in (9, 6):
            with self.assertNumQueries(expected):
                awards, _ = service.record_verified_achievements(**self.request_data(approved_skill_codes=codes))
                self.assertEqual(len(awards), 10)

    @override_settings(ACHIEVEMENT_LIMITS={"bulk_batch_size": 1})
    def test_bulk_batch_size_bounds_each_insert_without_splitting_transaction(self):
        with CaptureQueriesContext(connection) as queries:
            awards, created = service.record_verified_achievements(**self.request_data())
        self.assertTrue(created)
        self.assertEqual(len(awards), 2)
        self.assertEqual(sum(q["sql"].startswith('INSERT INTO "verified_achievements"') for q in queries), 2)
        self.assertEqual(sum(q["sql"] == "BEGIN" for q in queries), 1)
        self.assertEqual(sum(q["sql"] == "COMMIT" for q in queries), 1)

    def test_representative_selects_use_existing_indexes(self):
        students = Student.objects.bulk_create([Student(
            external_student_id=f"PLAN-{n}", first_name="Synthetic", last_name="Student",
            email=f"plan-{n}@example.org", program="Test", education_level="Test", student_status="Active",
        ) for n in range(2000)])
        Skill.objects.bulk_create([Skill(
            skill_code=f"PLAN-SKILL-{n}", skill_name="Synthetic", category="Test", description="Test",
            stamp_type="FOCUSED", badge_asset_id="TEST",
        ) for n in range(512)])
        events = AchievementSourceEvent.objects.bulk_create([AchievementSourceEvent(
            source="PLAN", source_event_id=f"PLAN-{n}", payload_sha256="a" * 64,
        ) for n in range(4000)])
        VerifiedAchievement.objects.bulk_create([VerifiedAchievement(
            student=students[n % len(students)], skill=self.skills[n % 2], source_event=event,
            earned_on=self.request_data()["earned_on"], verification_status="VERIFIED",
        ) for n, event in enumerate(events)])
        with connection.cursor() as cursor:
            for table in ("students", "skills_catalog", "achievement_source_events", "verified_achievements"):
                cursor.execute('ANALYZE "' + table + '"')

        def nodes(plan):
            yield plan
            for child in plan.get("Plans", []):
                yield from nodes(child)

        cases = (
            (Student.objects.filter(external_student_id="PLAN-100"), "students_external_student_id_key"),
            (Skill.objects.filter(skill_code=self.skills[0].skill_code), "skills_catalog_skill_code_key"),
            (AchievementSourceEvent.objects.filter(source="PLAN", source_event_id="PLAN-2000"), "uq_achievement_source_event"),
            (VerifiedAchievement.objects.filter(student=students[100], verification_status="VERIFIED").order_by("earned_on"), "va_student_status_earned_idx"),
        )
        for queryset, index in cases:
            with self.subTest(index=index):
                plan = json.loads(queryset.explain(analyze=True, buffers=True, format="json"))[0]["Plan"]
                self.assertIn(index, {node.get("Index Name") for node in nodes(plan)})
        limits = get_achievement_limits()
        request = service._prepare_request(limits=limits, **self.request_data())
        with CaptureQueriesContext(connection) as queries:
            service._resolve_identities(request)
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + queries[0]["sql"])
            plan = cursor.fetchone()[0][0]["Plan"]
        initplans = [n for n in nodes(plan) if n.get("Parent Relationship") == "InitPlan"]
        self.assertEqual(len(initplans), 1)
        self.assertEqual(initplans[0]["Actual Loops"], 1)
