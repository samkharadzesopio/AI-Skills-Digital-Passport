-- ============================================================
-- BTU AI SKILLS DIGITAL PASSPORT
-- PostgreSQL 18
-- Database Schema v1.0
-- Reference documentation only; Django migrations are authoritative.
-- Do not execute this script alongside Django migrations.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 1. STUDENTS
-- Source: Google Sheets / Students
-- Reference only: apps.students Django migrations own this table's schema.
-- ============================================================

CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    external_student_id VARCHAR(120) NOT NULL UNIQUE,

    first_name VARCHAR(150) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,

    program VARCHAR(255) NOT NULL,
    education_level VARCHAR(100) NOT NULL,
    student_status VARCHAR(50) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT chk_student_external_id
        CHECK (length(btrim(external_student_id)) > 0),

    CONSTRAINT chk_student_external_id_trimmed
        CHECK (external_student_id !~ '^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]$'),

    CONSTRAINT chk_student_first_name
        CHECK (length(btrim(first_name)) > 0),

    CONSTRAINT chk_student_last_name
        CHECK (length(btrim(last_name)) > 0),

    CONSTRAINT chk_student_email
        CHECK (
            email = btrim(email)
            AND email ~* '^[^\s@]+@[^\s@]+\.[^\s@]+$'
        ),

    CONSTRAINT chk_student_program
        CHECK (length(btrim(program)) > 0),

    CONSTRAINT chk_student_education_level
        CHECK (length(btrim(education_level)) > 0),

    CONSTRAINT chk_student_status
        CHECK (length(btrim(student_status)) > 0)
);

CREATE UNIQUE INDEX ux_students_email
    ON students (lower(email));


-- ============================================================
-- 2. SKILLS CATALOG
-- Source: Google Sheets / Skills Catalog
-- Reference only: apps.skills Django migrations own this table's schema.
-- ============================================================

CREATE TABLE skills_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    skill_code VARCHAR(100) NOT NULL UNIQUE,
    skill_name VARCHAR(250) NOT NULL,
    category VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,

    stamp_type VARCHAR(30) NOT NULL,
    badge_asset_id VARCHAR(150) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT chk_skill_code
        CHECK (length(btrim(skill_code)) > 0),

    CONSTRAINT chk_skill_name
        CHECK (length(btrim(skill_name)) > 0),

    CONSTRAINT chk_skill_category
        CHECK (length(btrim(category)) > 0),

    CONSTRAINT chk_skill_description
        CHECK (length(btrim(description)) > 0),

    CONSTRAINT chk_stamp_type
        CHECK (
            stamp_type IN (
                'FOCUSED',
                'APPLIED',
                'ADVANCED'
            )
        ),

    CONSTRAINT chk_badge_asset
        CHECK (length(btrim(badge_asset_id)) > 0)
);


-- ============================================================
-- 3. GOOGLE SHEETS SYNCHRONIZATION RUNS
-- ============================================================

CREATE TABLE sync_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    spreadsheet_id TEXT NOT NULL,
    sheet_name VARCHAR(120) NOT NULL DEFAULT 'Verified Skills',

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,

    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',

    records_seen INTEGER NOT NULL DEFAULT 0,
    records_changed INTEGER NOT NULL DEFAULT 0,

    error_summary TEXT,

    CONSTRAINT chk_sync_status
        CHECK (
            status IN (
                'RUNNING',
                'SUCCEEDED',
                'PARTIAL',
                'FAILED'
            )
        ),

    CONSTRAINT chk_sync_counters
        CHECK (
            records_seen >= 0
            AND records_changed >= 0
            AND records_changed <= records_seen
        ),

    CONSTRAINT chk_sync_dates
        CHECK (
            finished_at IS NULL
            OR finished_at >= started_at
        ),

    CONSTRAINT chk_sync_spreadsheet
        CHECK (length(btrim(spreadsheet_id)) > 0),

    CONSTRAINT uq_sync_run_source
        UNIQUE (id, spreadsheet_id)
);


-- ============================================================
-- 4. SOURCE SKILL RECORDS
-- Validated Google Sheets / Verified Skills records
--
-- Only records with valid Student ID, Skill Code,
-- date and status are inserted here.
--
-- Invalid source rows are logged in sync_record_events.
-- ============================================================

CREATE TABLE source_skill_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    spreadsheet_id TEXT NOT NULL,
    external_record_id VARCHAR(120) NOT NULL,

    student_id UUID NOT NULL
        REFERENCES students(id)
        ON DELETE RESTRICT,

    skill_code VARCHAR(100) NOT NULL
        REFERENCES skills_catalog(skill_code)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    earned_on DATE NOT NULL,

    status VARCHAR(12) NOT NULL,

    source_fingerprint CHAR(64) NOT NULL,

    last_seen_run_id UUID NOT NULL,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_source_external_record
        UNIQUE (spreadsheet_id, external_record_id),

    CONSTRAINT uq_source_confirmed_reference
        UNIQUE (
            id,
            student_id,
            skill_code,
            earned_on,
            status
        ),

    CONSTRAINT fk_source_sync_run
        FOREIGN KEY (last_seen_run_id, spreadsheet_id)
        REFERENCES sync_runs(id, spreadsheet_id),

    CONSTRAINT chk_source_record_id
        CHECK (length(btrim(external_record_id)) > 0),

    CONSTRAINT chk_source_status
        CHECK (
            status IN (
                'PENDING',
                'CONFIRMED',
                'REJECTED'
            )
        ),

    CONSTRAINT chk_source_fingerprint
        CHECK (
            source_fingerprint ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_source_dates
        CHECK (last_seen_at >= first_seen_at)
);

CREATE INDEX ix_source_student
    ON source_skill_records(student_id);

CREATE INDEX ix_source_status
    ON source_skill_records(status);

CREATE INDEX ix_source_student_status
    ON source_skill_records(student_id, status);


-- ============================================================
-- 5. SYNC RECORD EVENTS
-- Audit log for imported, ignored and invalid rows
-- ============================================================

CREATE TABLE sync_record_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    sync_run_id UUID NOT NULL
        REFERENCES sync_runs(id)
        ON DELETE RESTRICT,

    source_record_id UUID
        REFERENCES source_skill_records(id)
        ON DELETE RESTRICT,

    external_record_id VARCHAR(120),
    sheet_row_number INTEGER,

    source_fingerprint CHAR(64),

    outcome VARCHAR(25) NOT NULL,

    raw_payload JSONB,
    message TEXT,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_sync_event_outcome
        CHECK (
            outcome IN (
                'UNCHANGED',
                'IMPORTED',
                'IGNORED',
                'INVALID',
                'REVIEW_REQUIRED'
            )
        ),

    CONSTRAINT chk_sync_event_row
        CHECK (
            sheet_row_number IS NULL
            OR sheet_row_number >= 1
        ),

    CONSTRAINT chk_sync_event_fingerprint
        CHECK (
            source_fingerprint IS NULL
            OR source_fingerprint ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_imported_event_reference
        CHECK (
            outcome <> 'IMPORTED'
            OR source_record_id IS NOT NULL
        ),

    CONSTRAINT chk_invalid_event_payload
        CHECK (
            outcome NOT IN ('INVALID', 'REVIEW_REQUIRED')
            OR raw_payload IS NOT NULL
        )
);

CREATE INDEX ix_sync_events_record
    ON sync_record_events(
        external_record_id,
        occurred_at DESC
    );

CREATE INDEX ix_sync_events_run
    ON sync_record_events(sync_run_id);


-- ============================================================
-- 6. STUDENT SKILLS
-- Materialized confirmed skills only
--
-- A composite foreign key guarantees that the source
-- record has status CONFIRMED and matches the student,
-- skill code and earned date.
-- ============================================================

CREATE TABLE student_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_record_id UUID NOT NULL UNIQUE,

    student_id UUID NOT NULL,

    skill_code VARCHAR(100) NOT NULL,

    earned_on DATE NOT NULL,

    confirmation_status VARCHAR(12)
        NOT NULL DEFAULT 'CONFIRMED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_student_skill_confirmed
        CHECK (confirmation_status = 'CONFIRMED'),

    CONSTRAINT fk_student_skill_confirmed_source
        FOREIGN KEY (
            source_record_id,
            student_id,
            skill_code,
            earned_on,
            confirmation_status
        )
        REFERENCES source_skill_records (
            id,
            student_id,
            skill_code,
            earned_on,
            status
        )
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_student_skill
        UNIQUE (student_id, skill_code),

    CONSTRAINT uq_student_skill_identity
        UNIQUE (
            id,
            student_id,
            skill_code,
            earned_on
        )
);

CREATE INDEX ix_student_skills_student
    ON student_skills(student_id, earned_on);


-- ============================================================
-- 7. ISSUER IDENTITIES
-- BTU official or explicitly approved test issuer
--
-- trusted_at is populated only after the issuer identity
-- has been established through a trusted administrative
-- process.
-- ============================================================

CREATE TABLE issuer_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    issuer_code VARCHAR(80) NOT NULL,

    issuer_name VARCHAR(250) NOT NULL,

    issuer_kind VARCHAR(20) NOT NULL,

    chain_id BIGINT NOT NULL,

    wallet_address VARCHAR(42) NOT NULL,

    trust_reference TEXT,
    trusted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_issuer_kind
        CHECK (
            issuer_kind IN (
                'TEST',
                'OFFICIAL'
            )
        ),

    CONSTRAINT chk_issuer_chain
        CHECK (chain_id > 0),

    CONSTRAINT chk_issuer_wallet
        CHECK (
            wallet_address ~ '^0x[0-9a-fA-F]{40}$'
        ),

    CONSTRAINT chk_issuer_name
        CHECK (length(btrim(issuer_name)) > 0),

    CONSTRAINT chk_issuer_trust_dates
        CHECK (
            revoked_at IS NULL
            OR (
                trusted_at IS NOT NULL
                AND revoked_at > trusted_at
            )
        ),

    CONSTRAINT uq_issuer_wallet
        UNIQUE (chain_id, wallet_address),

    CONSTRAINT uq_issuer_identity_chain_wallet
        UNIQUE (id, chain_id, wallet_address)
);


-- ============================================================
-- 8. PASSPORTS
-- Exactly one permanent passport per student
-- ============================================================

CREATE TABLE passports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    passport_code VARCHAR(80) NOT NULL UNIQUE
        DEFAULT ('BTU-AI-' || gen_random_uuid()::TEXT),

    student_id UUID NOT NULL UNIQUE
        REFERENCES students(id)
        ON DELETE RESTRICT,

    issued_first_name VARCHAR(150) NOT NULL,
    issued_last_name VARCHAR(150) NOT NULL,

    first_issued_at TIMESTAMPTZ,

    latest_version_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_passport_code
        CHECK (length(btrim(passport_code)) > 0),

    CONSTRAINT chk_passport_first_name
        CHECK (length(btrim(issued_first_name)) > 0),

    CONSTRAINT chk_passport_last_name
        CHECK (length(btrim(issued_last_name)) > 0),

    CONSTRAINT uq_passport_student_identity
        UNIQUE (id, student_id)
);


-- ============================================================
-- 9. PASSPORT VERSIONS
-- One passport can have multiple official versions
-- ============================================================

CREATE TABLE passport_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    passport_id UUID NOT NULL,
    student_id UUID NOT NULL,

    version_number INTEGER NOT NULL,

    verification_code UUID NOT NULL UNIQUE
        DEFAULT gen_random_uuid(),

    status VARCHAR(20) NOT NULL DEFAULT 'PREPARING',

    pdf_storage_key TEXT UNIQUE,
    pdf_sha256 CHAR(64),

    skill_snapshot_hash CHAR(64) NOT NULL,

    issuer_identity_id UUID NOT NULL
        REFERENCES issuer_identities(id)
        ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    issued_at TIMESTAMPTZ,

    CONSTRAINT fk_version_passport_student
        FOREIGN KEY (passport_id, student_id)
        REFERENCES passports(id, student_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_passport_version_number
        UNIQUE (passport_id, version_number),

    CONSTRAINT uq_version_passport
        UNIQUE (passport_id, id),

    CONSTRAINT uq_version_student
        UNIQUE (id, student_id),

    CONSTRAINT uq_version_issuer
        UNIQUE (id, issuer_identity_id),

    CONSTRAINT uq_version_pdf_hash
        UNIQUE (id, pdf_sha256),

    CONSTRAINT chk_version_number
        CHECK (version_number >= 1),

    CONSTRAINT chk_version_status
        CHECK (
            status IN (
                'PREPARING',
                'PENDING_CHAIN',
                'ISSUED',
                'FAILED'
            )
        ),

    CONSTRAINT chk_version_pdf_hash
        CHECK (
            pdf_sha256 IS NULL
            OR pdf_sha256 ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_version_snapshot_hash
        CHECK (
            skill_snapshot_hash ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_version_pdf_required
        CHECK (
            status NOT IN ('PENDING_CHAIN', 'ISSUED')
            OR (
                pdf_storage_key IS NOT NULL
                AND pdf_sha256 IS NOT NULL
            )
        ),

    CONSTRAINT chk_version_issue_date
        CHECK (
            (status = 'ISSUED' AND issued_at IS NOT NULL)
            OR
            (status <> 'ISSUED' AND issued_at IS NULL)
        ),

    CONSTRAINT chk_version_issue_order
        CHECK (
            issued_at IS NULL
            OR issued_at >= created_at
        )
);

CREATE INDEX ix_versions_passport
    ON passport_versions(
        passport_id,
        version_number DESC
    );

CREATE INDEX ix_versions_status
    ON passport_versions(status);


-- ============================================================
-- 10. LATEST VERSION RELATIONSHIP
-- Ensures latest version belongs to the same passport
-- ============================================================

ALTER TABLE passports
ADD CONSTRAINT fk_latest_version_same_passport
    FOREIGN KEY (id, latest_version_id)
    REFERENCES passport_versions(passport_id, id)
    DEFERRABLE INITIALLY DEFERRED;


-- ============================================================
-- 11. VERSION SKILLS
-- Immutable historical skill snapshots after issuance
--
-- Composite foreign keys guarantee that each skill
-- belongs to the same student as the passport version.
-- Skill code and earned date must match the approved
-- student skill.
-- ============================================================

CREATE TABLE version_skills (
    version_id UUID NOT NULL,

    student_id UUID NOT NULL,

    student_skill_id UUID NOT NULL,

    skill_code_snapshot VARCHAR(100) NOT NULL,
    skill_name_snapshot VARCHAR(250) NOT NULL,

    category_snapshot VARCHAR(150) NOT NULL,
    description_snapshot TEXT NOT NULL,

    stamp_type_snapshot VARCHAR(30) NOT NULL,
    badge_asset_id_snapshot VARCHAR(150) NOT NULL,

    earned_on_snapshot DATE NOT NULL,

    PRIMARY KEY (version_id, student_skill_id),

    CONSTRAINT fk_version_skill_student
        FOREIGN KEY (version_id, student_id)
        REFERENCES passport_versions(id, student_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_version_skill_confirmed_award
        FOREIGN KEY (
            student_skill_id,
            student_id,
            skill_code_snapshot,
            earned_on_snapshot
        )
        REFERENCES student_skills(
            id,
            student_id,
            skill_code,
            earned_on
        )
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_version_skill_code
        UNIQUE (version_id, skill_code_snapshot),

    CONSTRAINT chk_version_skill_name
        CHECK (length(btrim(skill_name_snapshot)) > 0),

    CONSTRAINT chk_version_skill_category
        CHECK (length(btrim(category_snapshot)) > 0),

    CONSTRAINT chk_version_skill_description
        CHECK (length(btrim(description_snapshot)) > 0),

    CONSTRAINT chk_version_skill_stamp
        CHECK (
            stamp_type_snapshot IN (
                'FOCUSED',
                'APPLIED',
                'ADVANCED'
            )
        ),

    CONSTRAINT chk_version_skill_badge
        CHECK (length(btrim(badge_asset_id_snapshot)) > 0)
);


-- ============================================================
-- 12. BLOCKCHAIN ANCHORS
-- Metadata for future on-chain verification
--
-- Each official version has one confirmed anchor.
-- Multiple versions may share a blockchain transaction
-- if they have distinct event log indexes.
--
-- A database row alone is not cryptographic proof:
-- actual chain verification is performed by the
-- verification service.
-- ============================================================

CREATE TABLE blockchain_anchors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    version_id UUID NOT NULL UNIQUE,

    issuer_identity_id UUID NOT NULL,

    chain_id BIGINT NOT NULL,

    contract_address VARCHAR(42) NOT NULL,

    issuer_wallet_address VARCHAR(42) NOT NULL,

    transaction_hash VARCHAR(66) NOT NULL,

    event_log_index INTEGER NOT NULL,

    block_number BIGINT NOT NULL,

    anchored_pdf_sha256 CHAR(64) NOT NULL,

    confirmed_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_anchor_version_issuer
        FOREIGN KEY (version_id, issuer_identity_id)
        REFERENCES passport_versions(id, issuer_identity_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_anchor_issuer_wallet
        FOREIGN KEY (
            issuer_identity_id,
            chain_id,
            issuer_wallet_address
        )
        REFERENCES issuer_identities(
            id,
            chain_id,
            wallet_address
        )
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_anchor_pdf_hash
        FOREIGN KEY (
            version_id,
            anchored_pdf_sha256
        )
        REFERENCES passport_versions(
            id,
            pdf_sha256
        )
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_anchor_chain_event
        UNIQUE (
            chain_id,
            transaction_hash,
            event_log_index
        ),

    CONSTRAINT chk_anchor_chain
        CHECK (chain_id > 0),

    CONSTRAINT chk_anchor_contract
        CHECK (
            contract_address ~ '^0x[0-9a-fA-F]{40}$'
        ),

    CONSTRAINT chk_anchor_wallet
        CHECK (
            issuer_wallet_address ~ '^0x[0-9a-fA-F]{40}$'
        ),

    CONSTRAINT chk_anchor_transaction
        CHECK (
            transaction_hash ~ '^0x[0-9a-fA-F]{64}$'
        ),

    CONSTRAINT chk_anchor_hash
        CHECK (
            anchored_pdf_sha256 ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_anchor_event_index
        CHECK (event_log_index >= 0),

    CONSTRAINT chk_anchor_block
        CHECK (block_number >= 0)
);


-- ============================================================
-- 13. ISSUANCE JOBS
-- Idempotent PDF generation and issuance queue
-- ============================================================

CREATE TABLE issuance_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    passport_id UUID NOT NULL
        REFERENCES passports(id)
        ON DELETE RESTRICT,

    target_snapshot_hash CHAR(64) NOT NULL,

    version_id UUID,

    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',

    attempts INTEGER NOT NULL DEFAULT 0,

    next_retry_at TIMESTAMPTZ,
    leased_until TIMESTAMPTZ,

    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,

    CONSTRAINT fk_job_version
        FOREIGN KEY (passport_id, version_id)
        REFERENCES passport_versions(passport_id, id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_passport_snapshot_job
        UNIQUE (passport_id, target_snapshot_hash),

    CONSTRAINT chk_job_snapshot_hash
        CHECK (
            target_snapshot_hash ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT chk_job_status
        CHECK (
            status IN (
                'QUEUED',
                'RUNNING',
                'COMPLETED',
                'FAILED'
            )
        ),

    CONSTRAINT chk_job_attempts
        CHECK (attempts >= 0),

    CONSTRAINT chk_job_completed
        CHECK (
            (
                status = 'COMPLETED'
                AND completed_at IS NOT NULL
                AND version_id IS NOT NULL
            )
            OR
            (
                status <> 'COMPLETED'
                AND completed_at IS NULL
            )
        ),

    CONSTRAINT chk_job_completion_time
        CHECK (
            completed_at IS NULL
            OR completed_at >= created_at
        )
);

CREATE INDEX ix_jobs_queue
    ON issuance_jobs(
        status,
        next_retry_at,
        created_at
    );


-- ============================================================
-- 14. SOURCE RECORD IDENTITY PROTECTION
--
-- Once an external Record ID has been mapped to a student,
-- its student, skill and earned date cannot silently change.
-- Status changes remain allowed when referential constraints
-- permit them.
--
-- Corrections to protected fields require a new source
-- record or an explicit future correction workflow.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_source_record_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.spreadsheet_id IS DISTINCT FROM NEW.spreadsheet_id
       OR OLD.external_record_id IS DISTINCT FROM NEW.external_record_id
       OR OLD.student_id IS DISTINCT FROM NEW.student_id
       OR OLD.skill_code IS DISTINCT FROM NEW.skill_code
       OR OLD.earned_on IS DISTINCT FROM NEW.earned_on
    THEN
        RAISE EXCEPTION
            'Source record identity cannot be reassigned';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_source_record_identity
BEFORE UPDATE ON source_skill_records
FOR EACH ROW
EXECUTE FUNCTION protect_source_record_identity();


-- ============================================================
-- 15. CONFIRMED STUDENT SKILL IMMUTABILITY
--
-- A materialized confirmed award cannot be silently
-- modified or deleted.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_confirmed_student_skill()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Confirmed student skills are immutable';
END;
$$;

CREATE TRIGGER trg_protect_confirmed_student_skill
BEFORE UPDATE OR DELETE ON student_skills
FOR EACH ROW
EXECUTE FUNCTION protect_confirmed_student_skill();


-- ============================================================
-- 16. PASSPORT CORE IDENTITY PROTECTION
--
-- Passport ID and student association are permanent.
-- Issued names and original issuance date are frozen
-- after first official issuance.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_passport_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.passport_code IS DISTINCT FROM NEW.passport_code
       OR OLD.student_id IS DISTINCT FROM NEW.student_id
    THEN
        RAISE EXCEPTION
            'Passport identity cannot be changed';
    END IF;

    IF OLD.first_issued_at IS NOT NULL THEN
        IF OLD.issued_first_name IS DISTINCT FROM NEW.issued_first_name
           OR OLD.issued_last_name IS DISTINCT FROM NEW.issued_last_name
           OR OLD.first_issued_at IS DISTINCT FROM NEW.first_issued_at
        THEN
            RAISE EXCEPTION
                'Original passport identity and issuance date are immutable';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_passport_identity
BEFORE UPDATE ON passports
FOR EACH ROW
EXECUTE FUNCTION protect_passport_identity();


-- ============================================================
-- 17. PASSPORT VERSION PROTECTION
--
-- Version identity is permanent.
-- Allowed issuance status transitions are controlled.
-- Issued versions cannot be modified or deleted.
-- Historical skills must be retained in every new version.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_passport_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'ISSUED' THEN
            RAISE EXCEPTION
                'Issued passport versions cannot be deleted';
        END IF;

        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PREPARING' THEN
            RAISE EXCEPTION
                'New passport versions must start as PREPARING';
        END IF;

        RETURN NEW;
    END IF;

    IF OLD.status = 'ISSUED' THEN
        RAISE EXCEPTION
            'Issued passport versions are immutable';
    END IF;

    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.passport_id IS DISTINCT FROM NEW.passport_id
       OR OLD.student_id IS DISTINCT FROM NEW.student_id
       OR OLD.version_number IS DISTINCT FROM NEW.version_number
       OR OLD.verification_code IS DISTINCT FROM NEW.verification_code
       OR OLD.skill_snapshot_hash IS DISTINCT FROM NEW.skill_snapshot_hash
       OR OLD.issuer_identity_id IS DISTINCT FROM NEW.issuer_identity_id
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
    THEN
        RAISE EXCEPTION
            'Passport version identity cannot be changed';
    END IF;

    IF OLD.status = 'PREPARING'
       AND NEW.status NOT IN (
           'PREPARING',
           'PENDING_CHAIN',
           'FAILED'
       )
    THEN
        RAISE EXCEPTION
            'Invalid PREPARING status transition';
    END IF;

    IF OLD.status = 'PENDING_CHAIN'
       AND NEW.status NOT IN (
           'PENDING_CHAIN',
           'ISSUED',
           'FAILED'
       )
    THEN
        RAISE EXCEPTION
            'Invalid PENDING_CHAIN status transition';
    END IF;

    IF OLD.status = 'FAILED'
       AND NEW.status NOT IN (
           'FAILED',
           'PREPARING',
           'PENDING_CHAIN'
       )
    THEN
        RAISE EXCEPTION
            'Invalid FAILED status transition';
    END IF;

    IF OLD.status = 'PENDING_CHAIN'
       AND (
           OLD.pdf_storage_key IS DISTINCT FROM NEW.pdf_storage_key
           OR OLD.pdf_sha256 IS DISTINCT FROM NEW.pdf_sha256
       )
    THEN
        RAISE EXCEPTION
            'PDF metadata cannot change while awaiting blockchain confirmation';
    END IF;

    IF NEW.status = 'ISSUED'
       AND OLD.status <> 'ISSUED'
    THEN
        -- Prevent out-of-order publication.

        IF EXISTS (
            SELECT 1
            FROM passport_versions pv
            WHERE pv.passport_id = NEW.passport_id
              AND pv.id <> NEW.id
              AND pv.status = 'ISSUED'
              AND pv.version_number >= NEW.version_number
        ) THEN
            RAISE EXCEPTION
                'A newer or equal official version already exists';
        END IF;

        -- Every previously issued skill must remain present
        -- with exactly the same historical snapshot values.

        IF EXISTS (
            SELECT 1
            FROM passport_versions previous_version
            JOIN version_skills previous_skill
              ON previous_skill.version_id = previous_version.id
            WHERE previous_version.passport_id = NEW.passport_id
              AND previous_version.status = 'ISSUED'
              AND previous_version.version_number < NEW.version_number
              AND NOT EXISTS (
                  SELECT 1
                  FROM version_skills current_skill
                  WHERE current_skill.version_id = NEW.id
                    AND current_skill.student_skill_id =
                        previous_skill.student_skill_id
                    AND ROW(
                        current_skill.skill_code_snapshot,
                        current_skill.skill_name_snapshot,
                        current_skill.category_snapshot,
                        current_skill.description_snapshot,
                        current_skill.stamp_type_snapshot,
                        current_skill.badge_asset_id_snapshot,
                        current_skill.earned_on_snapshot
                    ) IS NOT DISTINCT FROM ROW(
                        previous_skill.skill_code_snapshot,
                        previous_skill.skill_name_snapshot,
                        previous_skill.category_snapshot,
                        previous_skill.description_snapshot,
                        previous_skill.stamp_type_snapshot,
                        previous_skill.badge_asset_id_snapshot,
                        previous_skill.earned_on_snapshot
                    )
              )
        ) THEN
            RAISE EXCEPTION
                'A new official version must preserve all previously issued skills and snapshots';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_passport_version
BEFORE INSERT OR UPDATE OR DELETE ON passport_versions
FOR EACH ROW
EXECUTE FUNCTION protect_passport_version();


-- ============================================================
-- 18. VERSION SKILL SNAPSHOT PROTECTION
--
-- Skills can only be assembled while the version is
-- PREPARING and no PDF hash has been assigned.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_version_skill_snapshot()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_version_id UUID;
    parent_status VARCHAR(20);
    parent_pdf_hash CHAR(64);
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_version_id := OLD.version_id;
    ELSE
        target_version_id := NEW.version_id;
    END IF;

    IF TG_OP = 'UPDATE'
       AND OLD.version_id IS DISTINCT FROM NEW.version_id
    THEN
        RAISE EXCEPTION
            'Skill snapshots cannot be moved between versions';
    END IF;

    SELECT status, pdf_sha256
    INTO parent_status, parent_pdf_hash
    FROM passport_versions
    WHERE id = target_version_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Passport version does not exist';
    END IF;

    IF parent_status <> 'PREPARING'
       OR parent_pdf_hash IS NOT NULL
    THEN
        RAISE EXCEPTION
            'Skill snapshots cannot change after PDF preparation';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_version_skill_snapshot
BEFORE INSERT OR UPDATE OR DELETE ON version_skills
FOR EACH ROW
EXECUTE FUNCTION protect_version_skill_snapshot();


-- ============================================================
-- 19. ISSUER IDENTITY PROTECTION
--
-- Existing issued versions retain the identity information
-- that was trusted at the time of issuance.
-- ============================================================

CREATE OR REPLACE FUNCTION protect_issuer_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM passport_versions
        WHERE issuer_identity_id = OLD.id
          AND status = 'ISSUED'
    ) THEN

        IF OLD.issuer_code IS DISTINCT FROM NEW.issuer_code
           OR OLD.issuer_name IS DISTINCT FROM NEW.issuer_name
           OR OLD.issuer_kind IS DISTINCT FROM NEW.issuer_kind
           OR OLD.chain_id IS DISTINCT FROM NEW.chain_id
           OR OLD.wallet_address IS DISTINCT FROM NEW.wallet_address
           OR OLD.trust_reference IS DISTINCT FROM NEW.trust_reference
           OR OLD.trusted_at IS DISTINCT FROM NEW.trusted_at
        THEN
            RAISE EXCEPTION
                'Trusted issuer identity cannot be altered after issuance';
        END IF;

        IF NEW.revoked_at IS NOT NULL
           AND EXISTS (
               SELECT 1
               FROM passport_versions
               WHERE issuer_identity_id = OLD.id
                 AND status = 'ISSUED'
                 AND issued_at >= NEW.revoked_at
           )
        THEN
            RAISE EXCEPTION
                'Issuer revocation cannot invalidate historical issuance timestamps';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_protect_issuer_identity
BEFORE UPDATE ON issuer_identities
FOR EACH ROW
EXECUTE FUNCTION protect_issuer_identity();


-- ============================================================
-- 20. DEFERRED PASSPORT ISSUANCE INTEGRITY
--
-- At transaction commit:
--
-- 1. Every ISSUED version must have a blockchain anchor.
-- 2. The anchor must correspond to the stored PDF hash.
-- 3. The issuer must have been trusted at issuance.
-- 4. Blockchain confirmation must precede issuance.
-- 5. latest_version_id must identify the highest issued
--    version number.
-- 6. first_issued_at must equal the earliest issuance date.
--
-- Actual independent blockchain verification will be
-- implemented separately in the verification service.
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_passport_consistency()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_passport_id UUID;

    stored_latest_id UUID;
    expected_latest_id UUID;

    stored_first_issued TIMESTAMPTZ;
    expected_first_issued TIMESTAMPTZ;
BEGIN

    IF TG_TABLE_NAME = 'passports' THEN
        target_passport_id := NEW.id;

    ELSIF TG_TABLE_NAME = 'passport_versions' THEN
        IF TG_OP = 'DELETE' THEN
            target_passport_id := OLD.passport_id;
        ELSE
            target_passport_id := NEW.passport_id;
        END IF;

    ELSIF TG_TABLE_NAME = 'blockchain_anchors' THEN
        IF TG_OP = 'DELETE' THEN
            SELECT passport_id
            INTO target_passport_id
            FROM passport_versions
            WHERE id = OLD.version_id;
        ELSE
            SELECT passport_id
            INTO target_passport_id
            FROM passport_versions
            WHERE id = NEW.version_id;
        END IF;
    END IF;

    IF target_passport_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT latest_version_id, first_issued_at
    INTO stored_latest_id, stored_first_issued
    FROM passports
    WHERE id = target_passport_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Every issued version requires an anchor and a trusted
    -- issuer identity valid at the time of issuance.

    IF EXISTS (
        SELECT 1
        FROM passport_versions pv

        LEFT JOIN blockchain_anchors ba
          ON ba.version_id = pv.id

        LEFT JOIN issuer_identities ii
          ON ii.id = pv.issuer_identity_id

        WHERE pv.passport_id = target_passport_id
          AND pv.status = 'ISSUED'
          AND (
              ba.id IS NULL
              OR ba.confirmed_at > pv.issued_at
              OR ii.trusted_at IS NULL
              OR ii.trusted_at > pv.issued_at
              OR (
                  ii.revoked_at IS NOT NULL
                  AND ii.revoked_at <= pv.issued_at
              )
          )
    ) THEN
        RAISE EXCEPTION
            'Issued passport version lacks a valid confirmed anchor or trusted issuer';
    END IF;

    -- Calculate the highest issued version.

    SELECT id
    INTO expected_latest_id
    FROM passport_versions
    WHERE passport_id = target_passport_id
      AND status = 'ISSUED'
    ORDER BY version_number DESC
    LIMIT 1;

    IF stored_latest_id IS DISTINCT FROM expected_latest_id THEN
        RAISE EXCEPTION
            'Passport latest_version_id does not reference the highest issued version';
    END IF;

    -- Calculate the first official issuance timestamp.

    SELECT MIN(issued_at)
    INTO expected_first_issued
    FROM passport_versions
    WHERE passport_id = target_passport_id
      AND status = 'ISSUED';

    IF stored_first_issued
       IS DISTINCT FROM expected_first_issued
    THEN
        RAISE EXCEPTION
            'Passport first_issued_at does not match its earliest official issuance';
    END IF;

    RETURN NULL;
END;
$$;


CREATE CONSTRAINT TRIGGER ctr_passport_consistency
AFTER INSERT OR UPDATE ON passports
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_passport_consistency();


CREATE CONSTRAINT TRIGGER ctr_version_consistency
AFTER INSERT OR UPDATE OR DELETE ON passport_versions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_passport_consistency();


CREATE CONSTRAINT TRIGGER ctr_anchor_consistency
AFTER INSERT OR UPDATE OR DELETE ON blockchain_anchors
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_passport_consistency();


-- ============================================================
-- 21. ISSUANCE JOB CONSISTENCY
--
-- A completed job must reference the matching officially
-- issued passport version and snapshot.
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_issuance_job_consistency()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = 'COMPLETED' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM passport_versions pv
            WHERE pv.id = NEW.version_id
              AND pv.passport_id = NEW.passport_id
              AND pv.skill_snapshot_hash = NEW.target_snapshot_hash
              AND pv.status = 'ISSUED'
        ) THEN
            RAISE EXCEPTION
                'Completed issuance job must reference a matching issued version';
        END IF;
    END IF;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER ctr_issuance_job_consistency
AFTER INSERT OR UPDATE ON issuance_jobs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_issuance_job_consistency();


-- ============================================================
-- 22. AUTOMATIC UPDATED_AT TIMESTAMPS
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


-- Student timestamps match Django's Now() statement-time semantics.
-- Keep the shared function above unchanged.
CREATE FUNCTION students_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_students_updated_at
BEFORE UPDATE ON students
FOR EACH ROW
EXECUTE FUNCTION students_set_updated_at();


-- Catalog timestamps use the same statement-time semantics as Django's Now().
CREATE FUNCTION skills_catalog_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_skills_updated_at
BEFORE UPDATE ON skills_catalog
FOR EACH ROW
EXECUTE FUNCTION skills_catalog_set_updated_at();




COMMIT;
