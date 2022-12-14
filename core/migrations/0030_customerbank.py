# Generated by Django 3.1.4 on 2022-06-19 05:30

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_remove_mftusertemp_is_confirmed'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerBank',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('access_on', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.bankidentifiercode', to_field='code')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.iscuser')),
            ],
        ),
    ]
