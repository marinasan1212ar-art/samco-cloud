from django.contrib import admin
from .models import Account, JournalEntry, JournalEntryLine, Customer, Product, Invoice, InvoiceItem

class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'balance')
    list_filter = ('account_type',)
    search_fields = ('code', 'name')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'vat_number')
    search_fields = ('name', 'vat_number')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('cat_no', 'name', 'sale_price', 'current_stock')
    search_fields = ('cat_no', 'name')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'customer', 'date', 'subtotal', 'vat_amount', 'total_amount')
    inlines = [InvoiceItemInline]

    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals_and_post_accounting()
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        obj.update_totals_and_post_accounting()
        return super().response_change(request, obj)

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'date', 'description')
    inlines = [JournalEntryLineInline]
