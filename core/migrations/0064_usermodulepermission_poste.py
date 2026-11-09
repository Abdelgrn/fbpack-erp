from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0063_stockmovement_article_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermodulepermission',
            name='poste',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Poste / Fonction',
            ),
        ),
    ]
