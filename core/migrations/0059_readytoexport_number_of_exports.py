# Generated by Django 3.1.4 on 2022-10-05 11:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_readytoexport_is_downloaded'),
    ]

    operations = [
        migrations.AddField(
            model_name='readytoexport',
            name='number_of_exports',
            field=models.IntegerField(default=0),
        ),
    ]
