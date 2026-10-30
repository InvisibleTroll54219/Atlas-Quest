from django.db import migrations, models


def mark_existing_progress_legacy(apps, schema_editor):
    PlayerProgress = apps.get_model("game", "PlayerProgress")
    PlayerProgress.objects.using(schema_editor.connection.alias).update(campaign_version=1)


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerprogress",
            name="campaign_version",
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.RunPython(mark_existing_progress_legacy, migrations.RunPython.noop),
    ]
