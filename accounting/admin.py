from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import (
    Company, CompanySettings, Account, BankAccount, JournalEntry, JournalEntryLine, 
    Customer, Supplier, Product, Invoice, InvoiceItem, PurchaseBill, PurchaseBillItem, 
    Quotation, QuotationItem, ReceiptVoucher, PaymentVoucher, Warehouse, WarehouseStock, 
    StockTransfer, StockTransferItem, UserProfile, BillOfMaterials, BOMItem, WorkOrder,
    CostCenter, FixedAsset, Employee, MonthlyPayroll, PayrollItem, StockAdjustment,
    SalesOrder, CreditNote, CreditNoteItem, PurchaseOrder
)

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_company', 'get_role', 'is_staff')
    def get_role(self, obj): return obj.profile.get_role_display() if hasattr(obj, 'profile') else 'N/A'
    def get_company(self, obj): return obj.profile.company.name if hasattr(obj, 'profile') and obj.profile.company else 'Global'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class CreditNoteItemInline(admin.TabularInline):
    model = CreditNoteItem
    extra = 1

@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ('credit_note_no', 'invoice', 'date', 'total_amount', 'reason')
    inlines = [CreditNoteItemInline]
    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals_and_post_accounting(); return super().response_add(request, obj, post_url_continue)

@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_en', 'name_ar', 'company')

@admin.register(FixedAsset)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display = ('asset_code', 'name', 'purchase_cost', 'accumulated_depreciation', 'cost_center')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_no', 'name_en', 'iqama_no', 'basic_salary', 'joining_date', 'is_active')
    search_fields = ('name_en', 'iqama_no', 'employee_no')

class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0

@admin.register(MonthlyPayroll)
class MonthlyPayrollAdmin(admin.ModelAdmin):
    list_display = ('month_year', 'processed_date', 'total_amount', 'is_paid', 'download_wps_sif')
    inlines = [PayrollItemInline]
    def download_wps_sif(self, obj):
        return format_html('<a class="button" style="background-color: #10B981; color: #000; font-weight: bold; padding: 4px 8px; border-radius: 6px;" href="/wps-export/{}/">📥 SIF Bank File</a>', obj.pk)

@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('adjustment_no', 'warehouse', 'product', 'system_qty', 'physical_qty', 'variance_qty')
    def response_add(self, request, obj, post_url_continue=None):
        obj.apply_adjustment(); return super().response_add(request, obj, post_url_continue)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'vat_number', 'print_statement')
    search_fields = ('name', 'vat_number')
    def print_statement(self, obj):
        return format_html('<a class="button" style="background-color: #38BDF8; color: #000; font-weight: bold; padding: 4px 8px; border-radius: 6px;" href="/statement/customer/{}/" target="_blank">📋 كشف حساب</a>', obj.pk)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'vat_number', 'print_statement')
    search_fields = ('name', 'vat_number')
    def print_statement(self, obj):
        return format_html('<a class="button" style="background-color: #F59E0B; color: #000; font-weight: bold; padding: 4px 8px; border-radius: 6px;" href="/statement/supplier/{}/" target="_blank">📋 كشف حساب</a>', obj.pk)

class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 2

@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ('bom_code', 'finished_product', 'output_qty', 'company')
    inlines = [BOMItemInline]

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'bom', 'warehouse', 'planned_qty', 'actual_qty_produced', 'status', 'unit_cost')
    def response_change(self, request, obj):
        obj.execute_production_completion(); return super().response_change(request, obj)

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

class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 1

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_en', 'name_ar', 'company')

@admin.register(WarehouseStock)
class WarehouseStockAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'product', 'stock_qty')

@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ('transfer_no', 'date', 'source_warehouse', 'destination_warehouse', 'status', 'print_transfer_slip')
    inlines = [StockTransferItemInline]
    def print_transfer_slip(self, obj):
        return format_html('<a class="button" style="background-color: #38BDF8; color: #000; font-weight: bold; padding: 4px 10px; border-radius: 6px; text-decoration: none;" href="/transfer/{}/" target="_blank">📄 سند تحويل Print</a>', obj.pk)
    def response_add(self, request, obj, post_url_continue=None):
        obj.execute_transfer(); return super().response_add(request, obj, post_url_continue)

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_number', 'balance', 'company')

@admin.register(ReceiptVoucher)
class ReceiptVoucherAdmin(admin.ModelAdmin):
    list_display = ('voucher_no', 'customer', 'date', 'bank_account', 'amount', 'print_voucher')
    def print_voucher(self, obj):
        return format_html('<a class="button" style="background-color: #10B981; color: #000; font-weight: bold; padding: 4px 10px; border-radius: 6px; text-decoration: none;" href="/voucher/receipt/{}/" target="_blank">📄 سند قبض Print</a>', obj.pk)
    def response_add(self, request, obj, post_url_continue=None):
        obj.post_accounting(); return super().response_add(request, obj, post_url_continue)

@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('voucher_no', 'supplier', 'date', 'bank_account', 'amount', 'print_voucher')
    def print_voucher(self, obj):
        return format_html('<a class="button" style="background-color: #F59E0B; color: #000; font-weight: bold; padding: 4px 10px; border-radius: 6px; text-decoration: none;" href="/voucher/payment/{}/" target="_blank">📄 سند صرف Print</a>', obj.pk)
    def response_add(self, request, obj, post_url_continue=None):
        obj.post_accounting(); return super().response_add(request, obj, post_url_continue)

@admin.register(PurchaseBill)
class PurchaseBillAdmin(admin.ModelAdmin):
    list_display = ('bill_no', 'supplier', 'warehouse', 'date', 'total_amount', 'payment_status')
    inlines = [PurchaseBillItemInline]
    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals_and_post_accounting(); return super().response_add(request, obj, post_url_continue)

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'customer', 'date', 'total_amount', 'status')
    inlines = [QuotationItemInline]

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'balance', 'company')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('cat_no', 'name', 'item_type', 'sale_price', 'cost_price', 'current_stock', 'company')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'customer', 'warehouse', 'date', 'total_amount', 'amount_paid', 'payment_status', 'print_tax_invoice')
    inlines = [InvoiceItemInline]
    def print_tax_invoice(self, obj):
        return format_html('<a class="button" style="background-color: #00F0FF; color: #000; font-weight: bold; padding: 4px 10px; border-radius: 6px; text-decoration: none;" href="/invoice/{}/" target="_blank">🖨️ Print Tax Invoice</a>', obj.pk)
    def response_add(self, request, obj, post_url_continue=None):
        obj.update_totals_and_post_accounting(); return super().response_add(request, obj, post_url_continue)

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'date', 'description', 'company')
    inlines = [JournalEntryLineInline]
