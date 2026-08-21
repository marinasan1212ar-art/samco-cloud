from django.contrib import admin
from .models import (
    CompanySettings, Customer, Supplier, Product, PriceList,
    Invoice, Quotation, RecurringInvoice, PurchaseBill, DirectExpense,
    Worker, AttendanceLog, SalarySheet, DeliveryNote, TransferSlip,
    VehicleBill, RejectLog, Account, JournalEntry
)

admin.site.register(CompanySettings)
admin.site.register(Customer)
admin.site.register(Supplier)
admin.site.register(Product)
admin.site.register(PriceList)
admin.site.register(Invoice)
admin.site.register(Quotation)
admin.site.register(RecurringInvoice)
admin.site.register(PurchaseBill)
admin.site.register(DirectExpense)
admin.site.register(Worker)
admin.site.register(AttendanceLog)
admin.site.register(SalarySheet)
admin.site.register(DeliveryNote)
admin.site.register(TransferSlip)
admin.site.register(VehicleBill)
admin.site.register(RejectLog)
admin.site.register(Account)
admin.site.register(JournalEntry)
