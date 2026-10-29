from django.db import migrations, connection


def add_physical_cash_account_if_missing(apps, schema_editor):
    table_name = "customers_customerdeposit"
    column_name = "physical_cash_account_id"

    with connection.cursor() as cursor:
        existing_columns = {
            col.name
            for col in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

        if column_name not in existing_columns:
            schema_editor.execute("""
                ALTER TABLE customers_customerdeposit
                ADD COLUMN physical_cash_account_id BIGINT NULL
                REFERENCES bank_management_bankaccount(id)
                DEFERRABLE INITIALLY DEFERRED;
                """)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0144_merge_20260205_0814"),
        ("bank_management", "0028_bankaccount_currency"),
    ]

    operations = [
        migrations.RunPython(add_physical_cash_account_if_missing),
    ]
