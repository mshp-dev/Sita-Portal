# Generated by Django 3.1.4 on 2022-10-05 11:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_auto_20220928_1127'),
    ]

    operations = [
        migrations.AddField(
            model_name='readytoexport',
            name='is_downloaded',
            field=models.BooleanField(default=False),
        ),
    ]
