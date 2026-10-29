"""Protect reviewed inputs and committed receipts; existing domain tables are untouched."""
from django.db import migrations


FORWARD = r"""
CREATE FUNCTION integrations_spreadsheet_profile_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Spreadsheet policy versions are retained';
  END IF;
  IF (to_jsonb(NEW) - 'enabled') IS DISTINCT FROM (to_jsonb(OLD) - 'enabled') THEN
    RAISE EXCEPTION 'Spreadsheet policy versions are immutable';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER spreadsheet_profile_guard BEFORE UPDATE OR DELETE ON integrations_spreadsheetprofile
FOR EACH ROW EXECUTE FUNCTION integrations_spreadsheet_profile_guard();

CREATE FUNCTION integrations_spreadsheet_preview_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Reviewed spreadsheet sessions are retained';
  END IF;
  IF ROW(NEW.id, NEW.actor_id, NEW.profile_id, NEW.source_sha256, NEW.snapshot_sha256, NEW.records,
         NEW.report, NEW.expires_at, NEW.created_at) IS DISTINCT FROM
     ROW(OLD.id, OLD.actor_id, OLD.profile_id, OLD.source_sha256, OLD.snapshot_sha256, OLD.records,
         OLD.report, OLD.expires_at, OLD.created_at) THEN
    RAISE EXCEPTION 'Reviewed spreadsheet inputs are immutable';
  END IF;
  IF OLD.run_id IS NOT NULL AND NEW.run_id IS DISTINCT FROM OLD.run_id THEN
    RAISE EXCEPTION 'Import history cannot be detached';
  END IF;
  IF OLD.confirmed_at IS NOT NULL AND NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at THEN
    RAISE EXCEPTION 'Import confirmation is retained';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER spreadsheet_preview_guard BEFORE UPDATE OR DELETE ON integrations_spreadsheetpreview
FOR EACH ROW EXECUTE FUNCTION integrations_spreadsheet_preview_guard();

CREATE FUNCTION integrations_spreadsheet_award_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Spreadsheet award receipts are immutable';
END; $$;
CREATE TRIGGER spreadsheet_award_guard BEFORE UPDATE OR DELETE ON integrations_spreadsheetaward
FOR EACH ROW EXECUTE FUNCTION integrations_spreadsheet_award_guard();
"""


def refuse_history(apps, schema_editor):
    if apps.get_model('integrations', 'SpreadsheetPreview').objects.exists() or apps.get_model('integrations', 'SpreadsheetAward').objects.exists():
        raise RuntimeError('Reviewed imports exist. Use a reviewed forward recovery; do not discard audit history.')


REVERSE = """
DROP TRIGGER spreadsheet_award_guard ON integrations_spreadsheetaward;
DROP FUNCTION integrations_spreadsheet_award_guard();
DROP TRIGGER spreadsheet_preview_guard ON integrations_spreadsheetpreview;
DROP FUNCTION integrations_spreadsheet_preview_guard();
DROP TRIGGER spreadsheet_profile_guard ON integrations_spreadsheetprofile;
DROP FUNCTION integrations_spreadsheet_profile_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('integrations', '0003_spreadsheetprofile_spreadsheetpreview_and_more')]
    operations = [migrations.RunSQL(FORWARD, REVERSE), migrations.RunPython(migrations.RunPython.noop, refuse_history)]
