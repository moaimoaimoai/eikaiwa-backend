from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mistakes', '0002_add_advice_and_useful_phrases'),
    ]

    operations = [
        # mistake_type の max_length を 20 → 30 に拡張（新しい長い種別名に対応）
        migrations.AlterField(
            model_name='mistake',
            name='mistake_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('grammar',     '文法'),
                    ('vocabulary',  '語彙'),
                    ('preposition', '前置詞'),
                    ('collocation', '語の組み合わせ'),
                    ('unnatural',   '不自然な表現'),
                    ('word_order',  '語順'),
                    ('article',     '冠詞'),
                    ('pronunciation', '発音'),
                    ('spelling',    'スペリング'),
                    ('other',       'その他'),
                ],
                default='grammar',
            ),
        ),
        # level_up フィールドを追加（より上級・ネイティブらしい表現の提案）
        migrations.AddField(
            model_name='mistake',
            name='level_up',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        # is_unnatural_only フィールドを追加（文法的には正しいが不自然な場合）
        migrations.AddField(
            model_name='mistake',
            name='is_unnatural_only',
            field=models.BooleanField(default=False),
        ),
    ]
