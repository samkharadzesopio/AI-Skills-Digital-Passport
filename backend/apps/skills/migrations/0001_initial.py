import django.db.models.functions.datetime
import django.db.models.functions.text
import django.db.models.lookups
import uuid
from django.db import migrations, models


def configure_postgresql_catalog(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('ALTER TABLE skills_catalog ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    schema_editor.execute('''
        CREATE FUNCTION skills_catalog_set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := statement_timestamp();
            RETURN NEW;
        END;
        $$;
    ''')
    schema_editor.execute('''
        CREATE TRIGGER trg_skills_updated_at BEFORE UPDATE ON skills_catalog
        FOR EACH ROW EXECUTE FUNCTION skills_catalog_set_updated_at();
    ''')


def unconfigure_postgresql_catalog(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP TRIGGER trg_skills_updated_at ON skills_catalog')
    schema_editor.execute('DROP FUNCTION skills_catalog_set_updated_at()')
    schema_editor.execute('ALTER TABLE skills_catalog ALTER COLUMN id DROP DEFAULT')


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Skill',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('skill_code', models.CharField(max_length=100)),
                ('skill_name', models.CharField(max_length=250)),
                ('category', models.CharField(max_length=150)),
                ('description', models.TextField()),
                ('stamp_type', models.CharField(choices=[('FOCUSED', 'Focused'), ('APPLIED', 'Applied'), ('ADVANCED', 'Advanced')], max_length=30)),
                ('badge_asset_id', models.CharField(max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.datetime.Now())),
                ('updated_at', models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now())),
            ],
            options={
                'db_table': 'skills_catalog',
                'constraints': [models.UniqueConstraint(fields=('skill_code',), name='skills_catalog_skill_code_key'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('skill_code')), 0), name='chk_skill_code'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('skill_name')), 0), name='chk_skill_name'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('category')), 0), name='chk_skill_category'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('description')), 0), name='chk_skill_description'), models.CheckConstraint(condition=models.Q(('stamp_type__in', ['FOCUSED', 'APPLIED', 'ADVANCED'])), name='chk_stamp_type'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('badge_asset_id')), 0), name='chk_badge_asset')],
            },
        ),
        migrations.RunPython(configure_postgresql_catalog, unconfigure_postgresql_catalog),
    ]
