# Generated by Django 3.2 on 2022-02-16 08:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_mftuser_phone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mftuser',
            name='bic',
            field=models.ForeignKey(default='_ISC', on_delete=django.db.models.deletion.CASCADE, to='core.bankidentifiercode', to_field='code'),
        ),
        migrations.AlterField(
            model_name='mftuser',
            name='business',
            field=models.CharField(default='mft', max_length=255),
        ),
    ]
