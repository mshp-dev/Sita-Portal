# Generated by Django 3.2.13 on 2022-06-26 15:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_remove_customerbank_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='iscuser',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
