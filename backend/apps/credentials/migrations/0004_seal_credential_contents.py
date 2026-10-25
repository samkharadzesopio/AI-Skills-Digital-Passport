from django.db import migrations

FORWARD = r"""
CREATE FUNCTION credential_link_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'credential achievement links are immutable' USING ERRCODE = '23514'; END $$;
CREATE TRIGGER credential_link_no_update_trg BEFORE UPDATE OR DELETE ON credential_achievements FOR EACH ROW EXECUTE FUNCTION credential_link_no_mutation();
CREATE OR REPLACE FUNCTION credential_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c_student uuid; a_student uuid; a_status varchar;
BEGIN
  IF EXISTS (SELECT 1 FROM credential_lifecycle_events WHERE credential_id = NEW.credential_id AND event_type = 'ISSUED') THEN
    RAISE EXCEPTION 'credential contents are finalized after issuance' USING ERRCODE = '23514';
  END IF;
  SELECT student_id INTO c_student FROM credentials WHERE id = NEW.credential_id;
  SELECT student_id, verification_status INTO a_student, a_status FROM verified_achievements WHERE id = NEW.achievement_id;
  IF c_student IS NULL OR a_student IS NULL OR c_student <> a_student OR a_status <> 'VERIFIED' THEN
    RAISE EXCEPTION 'credential requires a verified achievement owned by its student' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION credential_event_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c credentials%ROWTYPE;
BEGIN
  SELECT * INTO c FROM credentials WHERE id = NEW.credential_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'credential event parent missing' USING ERRCODE = '23503'; END IF;
  IF NEW.event_type = 'ISSUED' AND (c.status <> 'ISSUED' OR NEW.occurred_at <> c.issued_at OR NEW.actor_reference <> c.issuer_reference) THEN
    RAISE EXCEPTION 'issue event does not match credential facts' USING ERRCODE = '23514';
  END IF;
  IF NEW.event_type = 'REVOKED' AND (c.status <> 'REVOKED' OR NEW.occurred_at <> c.revoked_at OR NEW.actor_reference <> c.revoked_by OR NEW.reason <> c.revocation_reason) THEN
    RAISE EXCEPTION 'revocation event does not match credential state' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER credential_event_insert_guard_trg BEFORE INSERT ON credential_lifecycle_events FOR EACH ROW EXECUTE FUNCTION credential_event_insert_guard();
"""
REVERSE = r"""
DROP TRIGGER IF EXISTS credential_event_insert_guard_trg ON credential_lifecycle_events;
DROP FUNCTION IF EXISTS credential_event_insert_guard();
DROP TRIGGER IF EXISTS credential_link_no_update_trg ON credential_achievements;
DROP FUNCTION IF EXISTS credential_link_no_mutation();
"""
class Migration(migrations.Migration):
    dependencies = [('credentials', '0003_alter_credential_student')]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
