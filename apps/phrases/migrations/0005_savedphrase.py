from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('phrases', '0004_aiwordsession'),
        ('conversation', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedPhrase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('english', models.CharField(max_length=500)),
                ('japanese', models.CharField(max_length=500)),
                ('context_ja', models.TextField(blank=True)),
                ('source', models.CharField(
                    choices=[('coaching', '会話中コーチング'), ('summary', '会話サマリー'), ('correction', '添削フレーズ')],
                    default='coaching',
                    max_length=20,
                )),
                ('session_topic', models.CharField(blank=True, max_length=50)),
                ('is_mastered', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_phrases',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('session', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='saved_phrases',
                    to='conversation.conversationsession',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
