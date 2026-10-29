import django.db.models.functions.datetime
import django.db.models.functions.text
import django.db.models.lookups
import uuid
from django.db import migrations, models


def configure_postgresql_students(apps, schema_editor):
    """Preserve server defaults and raw/bulk UPDATE behavior from the SQL schema."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('ALTER TABLE students ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    schema_editor.execute('''
        CREATE FUNCTION students_set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := statement_timestamp();
            RETURN NEW;
        END;
        $$;
    ''')
    schema_editor.execute('''
        CREATE TRIGGER trg_students_updated_at BEFORE UPDATE ON students
        FOR EACH ROW EXECUTE FUNCTION students_set_updated_at();
    ''')


def unconfigure_postgresql_students(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP TRIGGER trg_students_updated_at ON students')
    schema_editor.execute('DROP FUNCTION students_set_updated_at()')
    schema_editor.execute('ALTER TABLE students ALTER COLUMN id DROP DEFAULT')


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('external_student_id', models.CharField(max_length=120)),
                ('first_name', models.CharField(max_length=150)),
                ('last_name', models.CharField(max_length=150)),
                ('email', models.EmailField(max_length=255)),
                ('program', models.CharField(max_length=255)),
                ('education_level', models.CharField(max_length=100)),
                ('student_status', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_default=django.db.models.functions.datetime.Now())),
                ('updated_at', models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now())),
            ],
            options={
                'db_table': 'students',
                'constraints': [models.UniqueConstraint(django.db.models.functions.text.Lower('email'), name='ux_students_email'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('external_student_id')), 0), name='chk_student_external_id'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('first_name')), 0), name='chk_student_first_name'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('last_name')), 0), name='chk_student_last_name'), models.CheckConstraint(condition=models.Q(('email', django.db.models.functions.text.Trim('email')), ('email__iregex', '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$')), name='chk_student_email'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('program')), 0), name='chk_student_program'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('education_level')), 0), name='chk_student_education_level'), models.CheckConstraint(condition=django.db.models.lookups.GreaterThan(django.db.models.functions.text.Length(django.db.models.functions.text.Trim('student_status')), 0), name='chk_student_status')],
            },
        ),
        migrations.AddConstraint(
            model_name='student',
            constraint=models.UniqueConstraint(
                fields=('external_student_id',), name='students_external_student_id_key',
            ),
        ),
        migrations.RunPython(configure_postgresql_students, unconfigure_postgresql_students),
    ]
