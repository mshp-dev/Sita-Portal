# Generated by Django 3.1.4 on 2022-07-26 12:40

import mftusers.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_auto_20220720_1422'),
    ]

    operations = [
        migrations.AlterField(
            model_name='readytoexport',
            name='export',
            field=models.FileField(default='template.xml', storage=mftusers.utils.OverwriteStorage(), upload_to='exports/'),
        ),
    ]
