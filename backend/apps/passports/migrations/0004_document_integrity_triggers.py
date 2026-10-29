from django.db import migrations


FORWARD = r"""
CREATE FUNCTION passport_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_status varchar; expected_generation integer; expected_key text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'passport document metadata cannot be deleted' USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'INSERT' THEN
    SELECT status INTO parent_status FROM passport_versions WHERE id = NEW.passport_version_id;
    SELECT COALESCE(MAX(generation_number), 0) + 1 INTO expected_generation
      FROM passport_documents WHERE passport_version_id = NEW.passport_version_id;
    IF parent_status <> 'ISSUED' OR NEW.status <> 'PENDING'
       OR NEW.generation_number <> expected_generation THEN
      RAISE EXCEPTION 'invalid initial passport document state' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  IF NEW.id <> OLD.id OR NEW.public_reference <> OLD.public_reference
     OR NEW.passport_version_id <> OLD.passport_version_id
     OR NEW.generation_number <> OLD.generation_number
     OR NEW.renderer_version <> OLD.renderer_version
     OR NEW.request_sha256 <> OLD.request_sha256 OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'passport document identity is immutable' USING ERRCODE = '23514';
  END IF;
  IF OLD.status = 'ISSUED' THEN
    RAISE EXCEPTION 'issued passport document metadata is immutable' USING ERRCODE = '23514';
  END IF;

  IF (OLD.status IN ('PENDING', 'FAILED') AND NEW.status = 'GENERATING')
     OR (OLD.status = 'GENERATING' AND NEW.status = 'GENERATING'
         AND OLD.lease_expires_at <= STATEMENT_TIMESTAMP()) THEN
    IF NEW.attempt_count <> OLD.attempt_count + 1 OR NEW.lease_token IS NULL THEN
      RAISE EXCEPTION 'invalid passport document generation claim' USING ERRCODE = '23514';
    END IF;
    SELECT 'passports/' || p.public_reference::text || '/' || pv.public_reference::text
           || '/' || NEW.public_reference::text || '/' || NEW.lease_token::text || '.pdf'
      INTO expected_key
      FROM passport_versions pv JOIN digital_passports p ON p.id = pv.passport_id
     WHERE pv.id = NEW.passport_version_id;
    IF NEW.attempt_storage_key <> expected_key THEN
      RAISE EXCEPTION 'invalid passport document storage key' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  IF OLD.status = 'GENERATING' AND NEW.status IN ('ISSUED', 'FAILED') THEN
    IF NEW.attempt_count <> OLD.attempt_count OR NEW.lease_token IS NOT NULL
       OR NEW.lease_expires_at IS NOT NULL THEN
      RAISE EXCEPTION 'invalid passport document generation completion' USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'ISSUED' AND NEW.storage_key <> OLD.attempt_storage_key THEN
      RAISE EXCEPTION 'issued document must use its claimed storage key' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  RAISE EXCEPTION 'invalid passport document status transition' USING ERRCODE = '23514';
END $$;

CREATE TRIGGER passport_document_guard_trg
BEFORE INSERT OR UPDATE OR DELETE ON passport_documents
FOR EACH ROW EXECUTE FUNCTION passport_document_guard();
"""


REVERSE = r"""
DROP TRIGGER IF EXISTS passport_document_guard_trg ON passport_documents;
DROP FUNCTION IF EXISTS passport_document_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("passports", "0003_passportdocument")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
