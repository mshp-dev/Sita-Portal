# Generated by Django 3.1.4 on 2022-10-17 09:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_auto_20221017_1037'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mftuser',
            name='home_dir',
        ),
        migrations.RemoveField(
            model_name='mftusertemp',
            name='home_dir',
        ),
    ]
