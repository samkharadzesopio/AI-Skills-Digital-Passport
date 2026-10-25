from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("skills", "0002_verified_achievements")]
    operations = [
        migrations.AddField(
            model_name="skill",
            name="subcategory",
            field=models.CharField(max_length=150, blank=True, default="", db_default=""),
        ),
    ]
