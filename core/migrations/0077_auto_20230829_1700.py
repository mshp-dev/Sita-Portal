# Generated by Django 3.2.13 on 2023-08-29 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0076_businesscode_foreign_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='mftuser',
            name='max_sessions',
            field=models.IntegerField(blank=True, default=2),
        ),
        migrations.AddField(
            model_name='mftusertemp',
            name='max_sessions',
            field=models.IntegerField(blank=True, default=2),
        ),
    ]
