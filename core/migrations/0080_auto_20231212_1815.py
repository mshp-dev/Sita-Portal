# Generated by Django 3.2.13 on 2023-12-12 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_auto_20231212_1200'),
    ]

    operations = [
        migrations.AddField(
            model_name='mftusertemp',
            name='owned_business',
            field=models.ManyToManyField(related_name='temp_owned_business', to='core.BusinessCode'),
        ),
        migrations.AddField(
            model_name='mftusertemp',
            name='used_business',
            field=models.ManyToManyField(related_name='temp_used_business', to='core.BusinessCode'),
        ),
    ]
