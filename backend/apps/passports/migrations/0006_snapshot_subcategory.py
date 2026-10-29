from django.db import migrations, models

FORWARD = r"""
CREATE OR REPLACE FUNCTION passport_skill_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_status varchar; source skills_catalog%ROWTYPE;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'passport skill snapshots are immutable' USING ERRCODE = '23514';
  END IF;
  SELECT status INTO version_status FROM passport_versions WHERE id = NEW.version_id;
  SELECT * INTO source FROM skills_catalog WHERE id = NEW.skill_id;
  IF version_status <> 'DRAFT' OR source.id IS NULL
     OR NEW.skill_code <> source.skill_code OR NEW.skill_name <> source.skill_name
     OR NEW.subcategory IS DISTINCT FROM source.subcategory
     OR NEW.category <> source.category OR NEW.description <> source.description
     OR NEW.stamp_type <> source.stamp_type OR NEW.badge_asset_id <> source.badge_asset_id THEN
    RAISE EXCEPTION 'invalid passport skill snapshot' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
"""

REVERSE = r"""
CREATE OR REPLACE FUNCTION passport_skill_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("passports", "0005_passportupdateevent_source_occurred_at"),
        ("skills", "0003_skill_subcategory"),
    ]
    operations = [
        migrations.AddField(
            model_name="passportversionskill",
            name="subcategory",
            field=models.CharField(max_length=150, blank=True, default="", db_default=""),
        ),
        migrations.RunSQL(FORWARD, REVERSE),
    ]
