# Generated by Django 5.1 on 2024-09-25 04:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_bentoreservation_transfer_user_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bentoreservation',
            name='transfer_user',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
