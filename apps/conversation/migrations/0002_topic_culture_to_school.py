from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('conversation', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversationsession',
            name='topic',
            field=models.CharField(
                choices=[
                    ('free', 'Free Conversation'),
                    ('daily_life', 'Daily Life'),
                    ('travel', 'Travel'),
                    ('business', 'Business'),
                    ('school', 'School'),
                    ('hobby', 'Hobbies'),
                ],
                default='free',
                max_length=50,
            ),
        ),
    ]
