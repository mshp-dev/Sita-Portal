# Generated by Django 3.1.4 on 2022-10-11 11:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_readytoexport_number_of_exports'),
    ]

    operations = [
        migrations.AddField(
            model_name='mftusertemp',
            name='is_confirmed',
            field=models.BooleanField(default=False),
        ),
    ]
