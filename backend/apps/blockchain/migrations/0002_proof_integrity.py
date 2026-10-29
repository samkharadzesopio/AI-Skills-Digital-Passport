from django.db import migrations

FORWARD=r"""
CREATE FUNCTION passport_anchor_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE doc_hash text; doc_snapshot text; doc_status text; owner_passport uuid;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'blockchain receipts cannot be deleted' USING ERRCODE='23514'; END IF;
 IF NEW.operation_type='ISSUE' THEN
   SELECT d.pdf_sha256,d.status,v.passport_id,v.content_sha256 INTO doc_hash,doc_status,owner_passport,doc_snapshot
     FROM passport_documents d JOIN passport_versions v ON v.id=d.passport_version_id WHERE d.id=NEW.document_id;
   IF doc_status IS DISTINCT FROM 'ISSUED' OR doc_hash IS DISTINCT FROM NEW.pdf_sha256 OR doc_snapshot IS DISTINCT FROM NEW.snapshot_sha256 OR owner_passport IS DISTINCT FROM NEW.passport_id
      OR NEW.commitment!~'^[0-9a-f]{64}$' OR NEW.commitment_salt!~'^[0-9a-f]{64}$'
      OR NEW.version_key!~'^[0-9a-f]{64}$' OR NEW.document_key!~'^[0-9a-f]{64}$' THEN
     RAISE EXCEPTION 'proof must bind an issued PDF and opaque commitment' USING ERRCODE='23514';
   END IF;
 ELSIF NEW.operation_type NOT IN ('REPLACE','REVOKE') OR NEW.document_id IS NOT NULL
       OR (NEW.operation_type='REPLACE' AND (NEW.replacement_id IS NULL OR NEW.replacement_key!~'^[0-9a-f]{64}$')) THEN
   RAISE EXCEPTION 'invalid lifecycle operation' USING ERRCODE='23514';
 END IF;
 IF NEW.passport_key!~'^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid opaque Passport key' USING ERRCODE='23514'; END IF;
 IF NEW.state IN ('SIGNED','SUBMITTED','CONFIRMED') AND NEW.signed_transaction IS NULL THEN
   RAISE EXCEPTION 'proof submission requires durable signing' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' THEN
   IF (to_jsonb(NEW)-ARRAY['state','signed_transaction','transaction_hash','nonce','block_number','block_hash','attempts','retryable','next_attempt_at','error_code','updated_at','last_checked_at'])
      <> (to_jsonb(OLD)-ARRAY['state','signed_transaction','transaction_hash','nonce','block_number','block_hash','attempts','retryable','next_attempt_at','error_code','updated_at','last_checked_at']) THEN
     RAISE EXCEPTION 'proof target is immutable' USING ERRCODE='23514';
   END IF;
   IF OLD.signed_transaction IS NOT NULL AND (NEW.signed_transaction IS DISTINCT FROM OLD.signed_transaction
      OR NEW.transaction_hash<>OLD.transaction_hash OR NEW.nonce IS DISTINCT FROM OLD.nonce) THEN
     RAISE EXCEPTION 'signed proof is immutable' USING ERRCODE='23514';
   END IF;
   IF OLD.state='CONFIRMED' AND (to_jsonb(NEW)-ARRAY['updated_at','last_checked_at'])<>(to_jsonb(OLD)-ARRAY['updated_at','last_checked_at']) THEN
     RAISE EXCEPTION 'confirmed proof receipt is immutable' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER passport_anchor_guard_trg BEFORE INSERT OR UPDATE OR DELETE ON passport_blockchain_anchors
FOR EACH ROW EXECUTE FUNCTION passport_anchor_guard();

CREATE FUNCTION blockchain_nonce_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'nonce reservations cannot be deleted' USING ERRCODE='23514'; END IF;
 IF NEW.key<>OLD.key OR NEW.next_nonce<OLD.next_nonce THEN RAISE EXCEPTION 'nonce cannot go backwards' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER blockchain_nonce_guard_trg BEFORE UPDATE OR DELETE ON blockchain_signer_nonces
FOR EACH ROW EXECUTE FUNCTION blockchain_nonce_guard();
"""

REVERSE=r"""
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM passport_blockchain_anchors)
    OR EXISTS (SELECT 1 FROM passport_lifecycle_events)
    OR EXISTS (SELECT 1 FROM digital_passports WHERE status<>'ACTIVE') THEN
   RAISE EXCEPTION 'Cannot remove retained blockchain receipts; review an archival/forward migration instead';
 END IF;
END $$;
DROP TRIGGER IF EXISTS blockchain_nonce_guard_trg ON blockchain_signer_nonces;
DROP FUNCTION IF EXISTS blockchain_nonce_guard();
DROP TRIGGER IF EXISTS passport_anchor_guard_trg ON passport_blockchain_anchors;
DROP FUNCTION IF EXISTS passport_anchor_guard();
"""

class Migration(migrations.Migration):
    dependencies=[('blockchain','0001_initial'),('passports','0008_lifecycle_integrity')]
    operations=[migrations.RunSQL(FORWARD,REVERSE)]
