
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='CaptchaStore',
            fields=[
                (
                    'id',
                    models.AutoField(
                        verbose_name='ID',
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ('challenge', models.CharField(max_length=32)),
                ('response', models.CharField(max_length=32)),
                ('hashkey', models.CharField(unique=True, max_length=40)),
                ('expiration', models.DateTimeField()),
            ],
            options={},
            bases=(models.Model,),
        ),
    ]
