from django.db import migrations
from django.db.models.functions import Lower


def backfill_legacy_account_roles(apps, schema_editor):
    """Normalize existing identities before installing stricter constraints."""

    User = apps.get_model("accounts", "User")
    database = schema_editor.connection.alias
    User.objects.using(database).all().update(email=Lower("email"))
    User.objects.using(database).filter(is_superuser=True).update(
        role="ADMIN", is_staff=True, is_superuser=False, is_email_verified=True
    )
    User.objects.using(database).filter(is_staff=True).update(
        role="ADMIN", is_email_verified=True
    )
    User.objects.using(database).filter(student__isnull=False).update(
        is_email_verified=True
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_authratelimitbucket_otpchallenge_and_more")]
    operations = [
        migrations.RunPython(
            backfill_legacy_account_roles,
            migrations.RunPython.noop,
        )
    ]
