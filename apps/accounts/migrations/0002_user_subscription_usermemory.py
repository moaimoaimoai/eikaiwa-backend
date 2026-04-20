from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # サブスクリプション・月次制限フィールドをUserに追加
        migrations.AddField(
            model_name='user',
            name='subscription_tier',
            field=models.CharField(
                choices=[('free', 'Free'), ('premium', 'Premium')],
                default='free',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='subscription_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='monthly_sessions_used',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='monthly_reset_date',
            field=models.DateField(blank=True, null=True),
        ),
        # UserMemoryモデルを追加
        migrations.CreateModel(
            name='UserMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interests', models.TextField(blank=True, help_text='ユーザーの趣味・関心（AI抽出）')),
                ('occupation', models.CharField(blank=True, help_text='職業・仕事', max_length=200)),
                ('personal_facts', models.TextField(blank=True, help_text='個人的な情報（家族、出身地など）')),
                ('common_mistakes', models.TextField(blank=True, help_text='よくするミスのパターン')),
                ('topics_discussed', models.JSONField(default=list, help_text='これまで話したトピック一覧')),
                ('session_count', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memory',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
