# Generated by Django 3.1.4 on 2022-05-23 04:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_auto_20220521_1059'),
    ]

    operations = [
        migrations.AddField(
            model_name='mftuser',
            name='home_dir',
            field=models.TextField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='mftusertemp',
            name='home_dir',
            field=models.TextField(blank=True, max_length=500),
        ),
    ]
