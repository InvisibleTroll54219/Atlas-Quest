from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0002_playerprogress_campaign_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerprogress",
            name="level_best_scores",
            field=models.JSONField(default=dict),
        ),
    ]
