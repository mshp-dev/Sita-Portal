# Generated by Django 3.2.13 on 2024-05-28 11:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('setad', '0006_setaduserinvoice_group_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='azmoondirectorypermission',
            name='invoice',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='setad.setaduserinvoice'),
        ),
    ]
