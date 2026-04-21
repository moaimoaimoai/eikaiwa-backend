from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mistakes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mistake',
            name='advice_ja',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='mistake',
            name='useful_phrases',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
