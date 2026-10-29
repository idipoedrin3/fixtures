from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0078_alter_itemreturn_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditdebitnote",
            name="are_initial_journal_entries_made",
            field=models.BooleanField(default=False),
        ),
    ]
