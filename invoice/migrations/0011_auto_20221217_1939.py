# Generated by Django 3.1.4 on 2022-12-17 16:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0010_auto_20221217_1724'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='description',
            field=models.CharField(blank=True, max_length=1000),
        ),
        migrations.AlterField(
            model_name='preinvoice',
            name='description',
            field=models.CharField(blank=True, max_length=1000),
        ),
    ]
