# Generated by Django 3.2.13 on 2023-08-19 07:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_alter_businesscode_remote_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='businesscode',
            name='foreign_address',
            field=models.CharField(default='/SMB', max_length=100),
        ),
    ]