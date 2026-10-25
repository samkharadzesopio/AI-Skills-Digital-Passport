from django.db import migrations

FORWARD = r"""
CREATE FUNCTION credential_guard_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.id <> OLD.id OR NEW.public_reference <> OLD.public_reference OR NEW.student_id <> OLD.student_id
     OR NEW.issuer_id <> OLD.issuer_id OR NEW.issuer_reference <> OLD.issuer_reference OR NEW.issuer_name <> OLD.issuer_name
     OR NEW.idempotency_key <> OLD.idempotency_key OR NEW.request_sha256 <> OLD.request_sha256
     OR NEW.issued_at <> OLD.issued_at OR NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'credential issuance facts are immutable' USING ERRCODE = '23514';
  END IF;
  IF OLD.status <> 'ISSUED' OR NEW.status <> 'REVOKED' THEN
    RAISE EXCEPTION 'only an issued credential can transition to revoked' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER credential_guard_update_trg BEFORE UPDATE ON credentials FOR EACH ROW EXECUTE FUNCTION credential_guard_update();
CREATE FUNCTION credential_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'credentials cannot be deleted' USING ERRCODE = '23514'; END $$;
CREATE TRIGGER credential_no_delete_trg BEFORE DELETE ON credentials FOR EACH ROW EXECUTE FUNCTION credential_no_delete();
CREATE FUNCTION credential_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c_student uuid; a_student uuid; a_status varchar;
BEGIN
  SELECT student_id INTO c_student FROM credentials WHERE id = NEW.credential_id;
  SELECT student_id, verification_status INTO a_student, a_status FROM verified_achievements WHERE id = NEW.achievement_id;
  IF c_student IS NULL OR a_student IS NULL OR c_student <> a_student OR a_status <> 'VERIFIED' THEN
    RAISE EXCEPTION 'credential requires a verified achievement owned by its student' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER credential_link_guard_trg BEFORE INSERT OR UPDATE ON credential_achievements FOR EACH ROW EXECUTE FUNCTION credential_link_guard();
CREATE FUNCTION credential_event_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'credential lifecycle events are immutable' USING ERRCODE = '23514'; END $$;
CREATE TRIGGER credential_event_no_update_trg BEFORE UPDATE OR DELETE ON credential_lifecycle_events FOR EACH ROW EXECUTE FUNCTION credential_event_no_mutation();
CREATE FUNCTION credential_event_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c credentials%ROWTYPE; e credential_lifecycle_events%ROWTYPE;
BEGIN
  SELECT * INTO c FROM credentials WHERE id = NEW.id;
  IF NOT FOUND THEN RETURN NULL; END IF;
  SELECT * INTO e FROM credential_lifecycle_events WHERE credential_id = c.id AND event_type = 'ISSUED';
  IF NOT FOUND OR e.occurred_at <> c.issued_at OR e.actor_reference <> c.issuer_reference THEN
    RAISE EXCEPTION 'credential must have a matching issue audit event' USING ERRCODE = '23514';
  END IF;
  IF c.status = 'REVOKED' THEN
    SELECT * INTO e FROM credential_lifecycle_events WHERE credential_id = c.id AND event_type = 'REVOKED';
    IF NOT FOUND OR e.occurred_at <> c.revoked_at OR e.actor_reference <> c.revoked_by OR e.reason <> c.revocation_reason THEN
      RAISE EXCEPTION 'revocation must have a matching lifecycle event' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER credential_event_consistency_trg AFTER INSERT OR UPDATE ON credentials DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION credential_event_consistency();
CREATE FUNCTION credential_issuer_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE issuer_ref varchar; issuer_display varchar;
BEGIN
 SELECT reference, display_name INTO issuer_ref, issuer_display FROM credential_issuers WHERE id = NEW.issuer_id;
 IF issuer_ref IS NULL OR NEW.issuer_reference <> issuer_ref OR NEW.issuer_name <> issuer_display THEN
   RAISE EXCEPTION 'credential issuer snapshot mismatch' USING ERRCODE = '23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER credential_issuer_snapshot_trg BEFORE INSERT ON credentials FOR EACH ROW EXECUTE FUNCTION credential_issuer_snapshot_guard();
"""
REVERSE = r"""
DROP TRIGGER IF EXISTS credential_issuer_snapshot_trg ON credentials;
DROP FUNCTION IF EXISTS credential_issuer_snapshot_guard();
DROP TRIGGER IF EXISTS credential_event_consistency_trg ON credentials;
DROP FUNCTION IF EXISTS credential_event_consistency();
DROP TRIGGER IF EXISTS credential_event_no_update_trg ON credential_lifecycle_events;
DROP FUNCTION IF EXISTS credential_event_no_mutation();
DROP TRIGGER IF EXISTS credential_link_guard_trg ON credential_achievements;
DROP FUNCTION IF EXISTS credential_link_guard();
DROP TRIGGER IF EXISTS credential_no_delete_trg ON credentials;
DROP FUNCTION IF EXISTS credential_no_delete();
DROP TRIGGER IF EXISTS credential_guard_update_trg ON credentials;
DROP FUNCTION IF EXISTS credential_guard_update();
"""
class Migration(migrations.Migration):
    dependencies = [('credentials', '0001_initial')]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
