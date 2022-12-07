# Generated by Django 3.1.4 on 2022-12-07 07:55

import core.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_auto_20221207_0955'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='readytoexport',
            name='export',
        ),
        migrations.AddField(
            model_name='readytoexport',
            name='paths',
            field=models.FileField(default='paths.csv', storage=core.models.OverwriteStorage(), upload_to='exports/'),
        ),
        migrations.AddField(
            model_name='readytoexport',
            name='webuser',
            field=models.FileField(default='template.xml', storage=core.models.OverwriteStorage(), upload_to='exports/'),
        ),
    ]
