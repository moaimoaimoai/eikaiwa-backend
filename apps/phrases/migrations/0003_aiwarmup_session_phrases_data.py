from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phrases', '0002_aiwarmup_session'),
    ]

    operations = [
        migrations.AddField(
            model_name='AIWarmupSession',
            name='phrases_data',
            field=models.JSONField(default=list, help_text='生成したフレーズの全データ（上限到達時の再表示用）'),
        ),
    ]
