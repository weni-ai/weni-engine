# Generated by Django 3.2.11 on 2022-04-05 13:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0009_alter_user_language'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='language',
            field=models.CharField(choices=[('en-us', 'English'), ('pt-br', 'Portuguese'), ('es', 'Spanish')], default='en-us', help_text='The primary language used by this user', max_length=64, verbose_name='Language'),
        ),
    ]
