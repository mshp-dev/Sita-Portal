# Generated by Django 3.1.4 on 2022-10-09 14:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invoice',
            name='directories',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='permissions',
        ),
        migrations.AlterField(
            model_name='invoice',
            name='mftuser',
            field=models.IntegerField(),
        ),
    ]
