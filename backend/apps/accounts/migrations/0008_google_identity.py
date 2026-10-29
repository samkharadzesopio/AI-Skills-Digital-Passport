import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_alter_user_options')]
    operations = [
        migrations.CreateModel(name='GoogleIdentity', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('subject', models.CharField(max_length=255, unique=True)),
            ('linked_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name='google_identity', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.CheckConstraint(condition=~models.Q(subject=''), name='google_subject_nonempty')]}),
        migrations.CreateModel(name='GoogleLoginChallenge', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('nonce_digest', models.CharField(max_length=64)),
            ('session_digest', models.CharField(max_length=64)),
            ('intent', models.CharField(max_length=5, choices=[('login', 'Login'), ('link', 'Link')])),
            ('audience', models.CharField(max_length=255)),
            ('expires_at', models.DateTimeField(db_index=True)),
            ('consumed_at', models.DateTimeField(null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.CheckConstraint(condition=(models.Q(intent='login', user__isnull=True) |
            models.Q(intent='link', user__isnull=False)), name='google_challenge_intent')]}),
        migrations.RunSQL("""
            CREATE FUNCTION accounts_google_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'UPDATE' AND (NEW.subject IS DISTINCT FROM OLD.subject OR NEW.user_id IS DISTINCT FROM OLD.user_id) THEN
                    RAISE EXCEPTION 'Google identity bindings cannot be reassigned';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM accounts_user u WHERE u.id = NEW.user_id
                    AND u.role = 'STUDENT' AND u.student_id IS NOT NULL
                    AND u.is_active AND u.is_email_verified AND NOT u.is_staff AND NOT u.is_superuser) THEN
                    RAISE EXCEPTION 'Google identity requires an eligible student login account';
                END IF;
                RETURN NEW;
            END $$;
            CREATE TRIGGER accounts_google_identity_guard BEFORE INSERT OR UPDATE ON accounts_googleidentity
            FOR EACH ROW EXECUTE FUNCTION accounts_google_identity_guard();
        """, """
            DROP TRIGGER accounts_google_identity_guard ON accounts_googleidentity;
            DROP FUNCTION accounts_google_identity_guard();
        """),
    ]
