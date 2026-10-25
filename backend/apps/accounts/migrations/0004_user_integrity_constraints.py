from django.db import migrations, models
from django.db.models.functions.text import Lower


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_backfill_legacy_account_roles")]
    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=["STUDENT", "ADMIN"]),
                name="chk_accounts_user_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(email=Lower("email")),
                name="chk_accounts_user_email_lower",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(email__regex=r"^[a-z0-9._%+\-]+@btu\.edu\.ge$"),
                name="chk_accounts_user_email_btu",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(role="STUDENT", is_staff=False, is_superuser=False)
                    | models.Q(role="ADMIN", is_staff=True, is_superuser=False)
                ),
                name="chk_accounts_user_role_privileges",
            ),
        ),
    ]
