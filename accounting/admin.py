from django.contrib import admin
from django.utils.html import format_html
from .models import Account, JournalEntry, JournalEntryLine, Customer, Supplier, Product, Invoice, InvoiceItem, PurchaseBill, PurchaseBillItem, Quotation, QuotationItem, CompanySettings

class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

class PurchaseBillItemInline(admin.TabularInline):
    model = PurchaseBillItem
    extra = 1

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name_en', 'vat_number', 'phone')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'vat_number')
    search_fields = ('name', 'vat_number')

@admin.register(PurchaseBill)
class PurchaseBillAdmin(admin.ModelAdmin):
    list_display = ('bill_no', 'supplier', 'date', 'subtotal', 'vat_amount', 'total_amount')
    inlines = [PurchaseBillItemInline]
    
    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals_and_post_accounting()
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        obj.update_totals_and_post_accounting()
        return super().response_change(request, obj)

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'customer', 'date', 'total_amount', 'status')
    inlines = [QuotationItemInline]
    
    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals()
        return super().response_add(request, obj, post_url_continue)

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
    list_display = ('invoice_no', 'customer', 'date', 'subtotal', 'vat_amount', 'total_amount', 'print_tax_invoice')
    inlines = [InvoiceItemInline]

    def print_tax_invoice(self, obj):
        return format_html(
            '<a class="button" style="background-color: #00F0FF; color: #000; font-weight: bold; padding: 4px 10px; border-radius: 6px; text-decoration: none;" href="/invoice/{}/" target="_blank">🖨️ Print Tax Invoice</a>',
            obj.pk
        )
    print_tax_invoice.short_description = "ZATCA Invoice"

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
