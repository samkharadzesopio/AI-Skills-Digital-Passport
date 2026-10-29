from django.db import migrations, models


FORWARD = r"""
CREATE FUNCTION passport_snapshot_date_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.snapshot_schema_version <> 2 THEN
      RAISE EXCEPTION 'new passport snapshots require schema 2' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.snapshot_schema_version IS DISTINCT FROM OLD.snapshot_schema_version THEN
    RAISE EXCEPTION 'passport snapshot schema is immutable' USING ERRCODE='23514';
  END IF;
  IF OLD.status = 'DRAFT' AND NEW.status = 'ISSUED' THEN
    IF NEW.snapshot_schema_version <> 2 OR EXISTS (
      SELECT 1 FROM passport_version_skills s
      WHERE s.version_id = NEW.id AND (
        s.earned_on IS NULL OR s.earned_on > NEW.issued_at::date OR s.earned_on IS DISTINCT FROM (
          SELECT min(a.earned_on)
          FROM passport_version_credential_skills l
          JOIN passport_version_credentials c ON c.id=l.credential_snapshot_id
          JOIN credential_achievements ca ON ca.credential_id=c.credential_id
          JOIN verified_achievements a ON a.id=ca.achievement_id AND a.skill_id=s.skill_id
          JOIN digital_passports p ON p.id=NEW.passport_id
          WHERE l.skill_snapshot_id=s.id AND c.version_id=NEW.id
            AND a.student_id=p.student_id AND a.verification_status='VERIFIED'
        ) OR EXISTS (
          SELECT 1 FROM passport_version_credential_skills l
          JOIN passport_version_credentials c ON c.id=l.credential_snapshot_id
          JOIN credential_achievements ca ON ca.credential_id=c.credential_id
          JOIN verified_achievements a ON a.id=ca.achievement_id AND a.skill_id=s.skill_id
          WHERE l.skill_snapshot_id=s.id AND (a.verification_status<>'VERIFIED'
              OR a.earned_on > c.credential_issued_at::date)
        )
      )
    ) THEN
      RAISE EXCEPTION 'passport skill dates must match earliest represented approved awards' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_snapshot_date_guard_trg BEFORE INSERT OR UPDATE ON passport_versions
FOR EACH ROW EXECUTE FUNCTION passport_snapshot_date_guard();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS passport_snapshot_date_guard_trg ON passport_versions;
DROP FUNCTION IF EXISTS passport_snapshot_date_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("passports", "0008_lifecycle_integrity")]
    operations = [
        # Existing versions keep schema 1 and NULL dates. No source-data lookup,
        # snapshot rewrite, content-hash rewrite, or artifact regeneration.
        migrations.AddField(
            model_name="passportversion", name="snapshot_schema_version",
            field=models.PositiveSmallIntegerField(default=1, db_default=1),
        ),
        migrations.AlterField(
            model_name="passportversion", name="snapshot_schema_version",
            field=models.PositiveSmallIntegerField(default=2, db_default=2),
        ),
        migrations.AddField(
            model_name="passportversionskill", name="earned_on",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.RunSQL(FORWARD, REVERSE),
    ]
