from django.db import migrations


FORWARD = r"""
CREATE FUNCTION passport_guard_update() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE next_passport_id uuid; next_version integer; next_status varchar;
BEGIN
  IF NEW.id <> OLD.id OR NEW.public_reference <> OLD.public_reference
     OR NEW.student_id <> OLD.student_id OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'passport identity is immutable' USING ERRCODE = '23514';
  END IF;
  IF NEW.latest_version_id IS DISTINCT FROM OLD.latest_version_id THEN
    IF NEW.latest_version_id IS NULL THEN
      RAISE EXCEPTION 'a published latest version cannot be cleared' USING ERRCODE = '23514';
    END IF;
    SELECT passport_id, version_number, status
      INTO next_passport_id, next_version, next_status
      FROM passport_versions WHERE id = NEW.latest_version_id;
    IF next_passport_id IS NULL OR next_passport_id <> NEW.id OR next_status <> 'ISSUED' THEN
      RAISE EXCEPTION 'latest version must be an issued version of this passport' USING ERRCODE = '23514';
    END IF;
    IF OLD.latest_version_id IS NULL AND next_version <> 1 THEN
      RAISE EXCEPTION 'the first published passport version must be version 1' USING ERRCODE = '23514';
    END IF;
    IF OLD.latest_version_id IS NOT NULL AND next_version <>
       (SELECT version_number + 1 FROM passport_versions WHERE id = OLD.latest_version_id) THEN
      RAISE EXCEPTION 'passport versions must advance sequentially' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_guard_update_trg
BEFORE UPDATE ON digital_passports
FOR EACH ROW EXECUTE FUNCTION passport_guard_update();

CREATE FUNCTION passport_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'published passport identities cannot be deleted' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER passport_no_delete_trg
BEFORE DELETE ON digital_passports
FOR EACH ROW EXECUTE FUNCTION passport_no_delete();

CREATE FUNCTION passport_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.status <> 'DRAFT' THEN
      RAISE EXCEPTION 'passport versions must begin as drafts' USING ERRCODE = '23514';
    END IF;
    IF jsonb_typeof(NEW.student_snapshot) <> 'object' THEN
      RAISE EXCEPTION 'student snapshot must be a JSON object' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE' THEN
    IF OLD.status = 'ISSUED' THEN
      RAISE EXCEPTION 'issued passport versions cannot be deleted' USING ERRCODE = '23514';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status <> 'DRAFT' OR NEW.status <> 'ISSUED'
     OR NEW.id <> OLD.id OR NEW.public_reference <> OLD.public_reference
     OR NEW.passport_id <> OLD.passport_id OR NEW.version_number <> OLD.version_number
     OR NEW.student_snapshot <> OLD.student_snapshot OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'issued passport versions are immutable' USING ERRCODE = '23514';
  END IF;
  IF EXISTS (
    SELECT 1
      FROM passport_version_credentials pvc
      JOIN credentials c ON c.id = pvc.credential_id
      JOIN digital_passports p ON p.id = NEW.passport_id
     WHERE pvc.version_id = NEW.id
       AND (c.student_id <> p.student_id OR c.status <> 'ISSUED'
            OR c.issued_at > NEW.issued_at
            OR (c.expires_at IS NOT NULL AND c.expires_at <= NEW.issued_at))
  ) THEN
    RAISE EXCEPTION 'issued passport contains an invalid credential' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_version_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_versions
FOR EACH ROW EXECUTE FUNCTION passport_version_guard();

CREATE FUNCTION passport_latest_consistency() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_number integer;
BEGIN
  IF NEW.status <> 'ISSUED' THEN RETURN NULL; END IF;
  SELECT pv.version_number INTO latest_number
    FROM digital_passports p
    JOIN passport_versions pv ON pv.id = p.latest_version_id
   WHERE p.id = NEW.passport_id;
  IF latest_number IS NULL OR latest_number < NEW.version_number THEN
    RAISE EXCEPTION 'issued passport version must be reachable from latest version' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER passport_latest_consistency_trg
AFTER UPDATE ON passport_versions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION passport_latest_consistency();

CREATE FUNCTION passport_credential_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_status varchar; passport_student uuid; source credentials%ROWTYPE;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'passport credential snapshots are immutable' USING ERRCODE = '23514';
  END IF;
  SELECT pv.status, p.student_id INTO version_status, passport_student
    FROM passport_versions pv JOIN digital_passports p ON p.id = pv.passport_id
   WHERE pv.id = NEW.version_id;
  SELECT * INTO source FROM credentials WHERE id = NEW.credential_id;
  IF version_status <> 'DRAFT' OR source.id IS NULL OR source.student_id <> passport_student
     OR source.status <> 'ISSUED'
     OR NEW.credential_public_reference <> source.public_reference
     OR NEW.issuer_reference <> source.issuer_reference OR NEW.issuer_name <> source.issuer_name
     OR NEW.credential_issued_at <> source.issued_at
     OR NEW.credential_expires_at IS DISTINCT FROM source.expires_at THEN
    RAISE EXCEPTION 'invalid passport credential snapshot' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_credential_snapshot_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_version_credentials
FOR EACH ROW EXECUTE FUNCTION passport_credential_snapshot_guard();

CREATE FUNCTION passport_skill_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_status varchar; source skills_catalog%ROWTYPE;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'passport skill snapshots are immutable' USING ERRCODE = '23514';
  END IF;
  SELECT status INTO version_status FROM passport_versions WHERE id = NEW.version_id;
  SELECT * INTO source FROM skills_catalog WHERE id = NEW.skill_id;
  IF version_status <> 'DRAFT' OR source.id IS NULL
     OR NEW.skill_code <> source.skill_code OR NEW.skill_name <> source.skill_name
     OR NEW.category <> source.category OR NEW.description <> source.description
     OR NEW.stamp_type <> source.stamp_type OR NEW.badge_asset_id <> source.badge_asset_id THEN
    RAISE EXCEPTION 'invalid passport skill snapshot' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_skill_snapshot_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_version_skills
FOR EACH ROW EXECUTE FUNCTION passport_skill_snapshot_guard();

CREATE FUNCTION passport_credential_skill_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE credential_version uuid; skill_version uuid; source_credential uuid; source_skill uuid; version_status varchar;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'passport credential-skill links are immutable' USING ERRCODE = '23514';
  END IF;
  SELECT version_id, credential_id INTO credential_version, source_credential
    FROM passport_version_credentials WHERE id = NEW.credential_snapshot_id;
  SELECT version_id, skill_id INTO skill_version, source_skill
    FROM passport_version_skills WHERE id = NEW.skill_snapshot_id;
  SELECT status INTO version_status FROM passport_versions WHERE id = credential_version;
  IF credential_version IS NULL OR credential_version <> skill_version OR version_status <> 'DRAFT'
     OR NOT EXISTS (
       SELECT 1 FROM credential_achievements ca
       JOIN verified_achievements va ON va.id = ca.achievement_id
       WHERE ca.credential_id = source_credential AND va.skill_id = source_skill
     ) THEN
    RAISE EXCEPTION 'invalid passport credential-skill link' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_credential_skill_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_version_credential_skills
FOR EACH ROW EXECUTE FUNCTION passport_credential_skill_guard();

CREATE FUNCTION passport_update_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_passport uuid; version_status varchar; version_hash varchar;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'passport update receipts are immutable' USING ERRCODE = '23514';
  END IF;
  SELECT passport_id, status, content_sha256
    INTO version_passport, version_status, version_hash
    FROM passport_versions WHERE id = NEW.version_id;
  IF version_passport IS NULL OR version_passport <> NEW.passport_id
     OR version_status <> 'ISSUED' OR version_hash <> NEW.content_sha256 THEN
    RAISE EXCEPTION 'passport update receipt does not match its version' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_update_event_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_update_events
FOR EACH ROW EXECUTE FUNCTION passport_update_event_guard();
"""


REVERSE = r"""
DROP TRIGGER IF EXISTS passport_update_event_guard_trg ON passport_update_events;
DROP FUNCTION IF EXISTS passport_update_event_guard();
DROP TRIGGER IF EXISTS passport_credential_skill_guard_trg ON passport_version_credential_skills;
DROP FUNCTION IF EXISTS passport_credential_skill_guard();
DROP TRIGGER IF EXISTS passport_skill_snapshot_guard_trg ON passport_version_skills;
DROP FUNCTION IF EXISTS passport_skill_snapshot_guard();
DROP TRIGGER IF EXISTS passport_credential_snapshot_guard_trg ON passport_version_credentials;
DROP FUNCTION IF EXISTS passport_credential_snapshot_guard();
DROP TRIGGER IF EXISTS passport_latest_consistency_trg ON passport_versions;
DROP FUNCTION IF EXISTS passport_latest_consistency();
DROP TRIGGER IF EXISTS passport_version_guard_trg ON passport_versions;
DROP FUNCTION IF EXISTS passport_version_guard();
DROP TRIGGER IF EXISTS passport_no_delete_trg ON digital_passports;
DROP FUNCTION IF EXISTS passport_no_delete();
DROP TRIGGER IF EXISTS passport_guard_update_trg ON digital_passports;
DROP FUNCTION IF EXISTS passport_guard_update();
"""


class Migration(migrations.Migration):
    dependencies = [("passports", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
