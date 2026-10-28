from django.contrib import admin

from .models import (
    GoodsReceivedNoteLineItem,
    Vendor,
    VendorPurchaseOrder,
    VendorBill,
    VendorBillOtherExpenses,
    VendorPaymentOption,
    VendorPayment,
    GoodsReceivedNote,
    VendorPurchaseOrderLineItem,
)

admin.site.register(VendorPurchaseOrder)
admin.site.register(Vendor)
admin.site.register(VendorBill)
admin.site.register(VendorBillOtherExpenses)
admin.site.register(VendorPaymentOption)
admin.site.register(VendorPayment)
admin.site.register(GoodsReceivedNoteLineItem)
admin.site.register(GoodsReceivedNote)
admin.site.register(VendorPurchaseOrderLineItem)
