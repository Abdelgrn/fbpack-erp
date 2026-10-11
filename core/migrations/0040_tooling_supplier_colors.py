from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_alter_technicalproduct_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='tooling', name='supplier_name',
            field=models.CharField(blank=True, default='', max_length=150, verbose_name='Fournisseur / Graveur'),
        ),
        migrations.AddField(
            model_name='tooling', name='color_count',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(8)], verbose_name='Nombre de couleurs'),
        ),
        migrations.AddField(model_name='tooling', name='color_1', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 1')),
        migrations.AddField(model_name='tooling', name='color_2', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 2')),
        migrations.AddField(model_name='tooling', name='color_3', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 3')),
        migrations.AddField(model_name='tooling', name='color_4', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 4')),
        migrations.AddField(model_name='tooling', name='color_5', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 5')),
        migrations.AddField(model_name='tooling', name='color_6', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 6')),
        migrations.AddField(model_name='tooling', name='color_7', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 7')),
        migrations.AddField(model_name='tooling', name='color_8', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Couleur 8')),
    ]
