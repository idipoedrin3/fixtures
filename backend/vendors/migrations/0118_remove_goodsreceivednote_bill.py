from django.db import migrations


def populate_purchase_order_from_bill(apps, schema_editor):
    GoodsReceivedNote = apps.get_model("vendors", "GoodsReceivedNote")
    VendorBill = apps.get_model("vendors", "VendorBill")

    for bill in VendorBill.objects.exclude(purchase_order_id=None):
        GoodsReceivedNote.objects.filter(
            bill_id=bill.id,
            purchase_order_id=None,
        ).update(purchase_order_id=bill.purchase_order_id)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        (
            "vendors",
            "0117_remove_inventoryvendorpurchaseorderlineitem_created_by_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            populate_purchase_order_from_bill,
        ),
        migrations.RemoveField(
            model_name="goodsreceivednote",
            name="bill",
        ),
    ]
