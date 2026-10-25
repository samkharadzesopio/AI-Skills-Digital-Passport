from django.db import migrations


FORWARD = (
    """CREATE FUNCTION accounts_user_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.student_id IS DISTINCT FROM OLD.student_id THEN
        RAISE EXCEPTION 'student account association is immutable' USING ERRCODE = '23514';
      END IF;
      IF NEW.email IS DISTINCT FROM OLD.email THEN
        RAISE EXCEPTION 'account login email is immutable' USING ERRCODE = '23514';
      END IF;
      IF NEW.role IS DISTINCT FROM OLD.role
         OR NEW.is_staff IS DISTINCT FROM OLD.is_staff
         OR NEW.is_superuser IS DISTINCT FROM OLD.is_superuser THEN
        RAISE EXCEPTION 'account role and privilege flags are immutable' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$""",
    """CREATE TRIGGER accounts_user_identity_guard_trg
    BEFORE UPDATE OF student_id, email, role, is_staff, is_superuser ON accounts_user
    FOR EACH ROW EXECUTE FUNCTION accounts_user_identity_guard()""",
    """CREATE FUNCTION student_invitation_redemption_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.redeemed_at IS NOT NULL AND NEW.redeemed_at IS DISTINCT FROM OLD.redeemed_at THEN
        RAISE EXCEPTION 'redeemed account invitation cannot be reset' USING ERRCODE = '23514';
      END IF;
      IF OLD.redeemed_at IS NOT NULL AND (
           NEW.student_id IS DISTINCT FROM OLD.student_id
           OR NEW.token_digest IS DISTINCT FROM OLD.token_digest
           OR NEW.recipient_email_digest IS DISTINCT FROM OLD.recipient_email_digest
           OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
         ) THEN
        RAISE EXCEPTION 'redeemed account invitation is immutable' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$""",
    """CREATE TRIGGER student_invitation_redemption_guard_trg
    BEFORE UPDATE ON student_account_invitations
    FOR EACH ROW EXECUTE FUNCTION student_invitation_redemption_guard()""",
)

REVERSE = (
    "DROP TRIGGER IF EXISTS student_invitation_redemption_guard_trg ON student_account_invitations",
    "DROP FUNCTION IF EXISTS student_invitation_redemption_guard()",
    "DROP TRIGGER IF EXISTS accounts_user_identity_guard_trg ON accounts_user",
    "DROP FUNCTION IF EXISTS accounts_user_identity_guard()",
)


def create_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for statement in FORWARD:
            schema_editor.execute(statement)


def drop_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for statement in REVERSE:
            schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_user_integrity_constraints")]
    operations = [migrations.RunPython(create_guards, drop_guards)]
