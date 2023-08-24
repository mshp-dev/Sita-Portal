# Generated by Django 3.2.13 on 2023-08-24 08:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0076_businesscode_foreign_address'),
        ('invoice', '0019_alter_preinvoice_directories_list'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='mftuser_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.mftuser'),
        ),
        migrations.AlterField(
            model_name='preinvoice',
            name='directories_list',
            field=models.CharField(default='', max_length=500000),
        ),
    ]