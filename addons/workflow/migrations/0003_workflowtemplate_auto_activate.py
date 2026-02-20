from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('addons_workflow', '0002_workflowtemplate_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowtemplate',
            name='auto_activate',
            field=models.BooleanField(default=False),
        ),
    ]
