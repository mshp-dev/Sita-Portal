# Generated by Django 3.1.4 on 2022-07-20 09:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_readytoexport_export_path'),
    ]

    operations = [
        migrations.RenameField(
            model_name='readytoexport',
            old_name='export_path',
            new_name='export',
        ),
    ]
