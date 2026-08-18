from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
import uuid
from datetime import datetime
from .zatca import generate_zatca_qr_base64, generate_qr_image_base64

# ১. Chart of Accounts
class Account(models.Model):
    ACCOUNT_TYPES = [
        ('Asset', 'Asset (সম্পদ)'),
        ('Liability', 'Liability (দায়)'),
        ('Equity', 'Equity (মূলধন)'),
        ('Revenue', 'Revenue (আয়)'),
        ('Expense', 'Expense (ব্যয়)'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type})"


# ২. Company Profile
class CompanySettings(models.Model):
    company_name_en = models.CharField(max_length=255, default="SECOND ADVANCE MEDICAL COMPANY")
    company_name_ar = models.CharField(max_length=255, default="الشركة الطبية المتقدمة الثانية")
    vat_number = models.CharField(max_length=50, default="310122456700003", help_text="Saudi 15-Digit VAT ID")
    cr_number = models.CharField(max_length=50, default="1010445566", help_text="Commercial Registration No")
    address_en = models.TextField(default="Riyadh Industrial City, Saudi Arabia")
    address_ar = models.TextField(default="المنطقة الصناعية، الرياض، المملكة العربية السعودية")
    phone = models.CharField(max_length=50, default="+966 11 000 0000")

    def __str__(self):
        return self.company_name_en


# ৩. Divisions & Warehouses
class Warehouse(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, help_text="اسم الفرع / المستودع")
    location = models.CharField(max_length=255, default="Riyadh, KSA")
    manager_name = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.name_en} ({self.name_ar})"


# ৪. User Roles & RBAC
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin / General Manager (المدير العام)'),
        ('ACCOUNTANT', 'Accountant (المحاسب)'),
        ('SALESMAN', 'Salesman (مندوب مبيعات)'),
        ('WAREHOUSE_KEEPER', 'Warehouse Keeper (أمين المستودع)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='ADMIN')
    assigned_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        try:
            instance.profile.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)


# ৫. Bank & Cash Accounts
class BankAccount(models.Model):
    name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    branch = models.CharField(max_length=150, blank=True, null=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    chart_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="bank_records")

    def __str__(self):
        return f"{self.name} (Balance: {self.balance:.2f} SAR)"


# ৬. Customer
class Customer(models.Model):
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৭. Supplier
class Supplier(models.Model):
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৮. Product & Materials
class Product(models.Model):
    ITEM_TYPES = [
        ('FINISHED_GOOD', 'Finished Good (منتج نهائي)'),
        ('RAW_MATERIAL', 'Raw Material (مادة خام)'),
        ('PACKAGING', 'Packaging Material (مواد تعبئة)'),
    ]

    cat_no = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    item_type = models.CharField(max_length=30, choices=ITEM_TYPES, default='FINISHED_GOOD')
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)

    def __str__(self):
        return f"[{self.cat_no}] {self.name} (Stock: {self.current_stock})"


# ৯. Division-specific Stock
class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='division_stocks')
    stock_qty = models.IntegerField(default=0)

    class Meta:
        unique_together = ('warehouse', 'product')

    def __str__(self):
        return f"{self.warehouse.name_en} - {self.product.name} ({self.stock_qty} Pcs)"


# =========================================================================
# 🏭 ১০. MASTER MANUFACTURING ENGINE (BOM & WORK ORDERS) - QUYOD 120%
# =========================================================================
class BillOfMaterials(models.Model):
    bom_code = models.CharField(max_length=100, unique=True, default="BOM-001")
    finished_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="boms", limit_choices_to={'item_type': 'FINISHED_GOOD'})
    output_qty = models.IntegerField(default=1, help_text="Standard Batch Yield (e.g. 1000 Pcs)")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.bom_code} - Recipe for {self.finished_product.name}"


class BOMItem(models.Model):
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.CASCADE, related_name="components")
    raw_material = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="used_in_boms")
    quantity_required = models.DecimalField(max_digits=10, decimal_places=3, help_text="Qty in Kg/Liters/Pcs per batch")
    scrap_allowance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Expected wastage %")

    def __str__(self):
        return f"{self.raw_material.name} ({self.quantity_required})"


class WorkOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft (مسودة)'),
        ('IN_PROGRESS', 'In Production (قيد التشغيل)'),
        ('QC_PENDING', 'QC Inspection (فحص الجودة)'),
        ('COMPLETED', 'Completed 🟢 (تم الإنتاج)'),
        ('CANCELLED', 'Cancelled 🔴'),
    ]

    order_no = models.CharField(max_length=100, unique=True, default="WO-001")
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, help_text="Manufacturing Factory Division")
    planned_qty = models.IntegerField(default=1000)
    actual_qty_produced = models.IntegerField(default=0)
    
    start_date = models.DateField(default=datetime.now)
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')

    # কস্টিং ব্রেকডাউন (Cost Allocation Engine)
    material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    machine_overhead = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_batch_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Work Order #{self.order_no} - {self.bom.finished_product.name} ({self.status})"

    def execute_production_completion(self):
        """স্বয়ংক্রিয় ম্যাটেরিয়াল বিয়োগ, কস্টিং হিসাব ও ফিনিশড স্টক বৃদ্ধি"""
        if self.status == 'COMPLETED' and self.actual_qty_produced > 0:
            batch_ratio = Decimal(self.actual_qty_produced) / Decimal(self.bom.output_qty)
            calculated_mat_cost = Decimal('0.00')

            # ১. কাঁচামাল স্টক থেকে মাইনাস করা
            for comp in self.bom.components.all():
                needed_qty = (comp.quantity_required * batch_ratio) * (1 + (comp.scrap_allowance_pct / 100))
                comp.raw_material.current_stock = models.F('current_stock') - int(needed_qty)
                comp.raw_material.save()
                calculated_mat_cost += Decimal(needed_qty) * comp.raw_material.cost_price

            # ২. মোট কস্টিং ও ইউনিট কস্ট হিসাব
            tot_cost = calculated_mat_cost + self.labor_cost + self.machine_overhead
            u_cost = tot_cost / Decimal(self.actual_qty_produced)

            WorkOrder.objects.filter(pk=self.pk).update(
                material_cost=calculated_mat_cost,
                total_batch_cost=tot_cost,
                unit_cost=u_cost
            )

            # ৩. ফিনিশড গুডস স্টকে যোগ করা
            fg = self.bom.finished_product
            fg.current_stock = models.F('current_stock') + self.actual_qty_produced
            fg.cost_price = u_cost
            fg.save()

            # ডিভিশনাল স্টকে যোগ করা
            ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.warehouse, product=fg)
            ws.stock_qty = models.F('stock_qty') + self.actual_qty_produced
            ws.save()


# ১১. Quotation
class Quotation(models.Model):
    quote_no = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, default='PENDING', choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted'), ('CONVERTED', 'Converted to Invoice'), ('REJECTED', 'Rejected')])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)

    def __str__(self):
        return f"Quote #{self.quote_no} - {self.customer.name}"

    def update_totals(self):
        sub = sum(item.total for item in self.items.all())
        vat = sub * Decimal('0.15')
        tot = sub + vat
        Quotation.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot)


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total = Decimal(self.qty) * Decimal(self.unit_price)
        super().save(*args, **kwargs)


# ১২. Sales Invoice (ZATCA Phase-2)
class Invoice(models.Model):
    invoice_no = models.CharField(max_length=100, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    invoice_type = models.CharField(max_length=50, default='Tax Invoice (فاتورة ضريبية)')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    
    zatca_qr_b64 = models.TextField(blank=True, null=True, editable=False)

    def __str__(self):
        return f"Invoice #{self.invoice_no} - {self.customer.name}"

    def update_totals_and_post_accounting(self):
        sub = sum(item.total for item in self.items.all())
        vat = sub * Decimal('0.15')
        tot = sub + vat

        company, _ = CompanySettings.objects.get_or_create(id=1)
        time_str = self.date.strftime("%Y-%m-%dT%H:%M:%SZ") if self.date else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        qr_b64 = generate_zatca_qr_base64(
            seller_name=company.company_name_en,
            vat_no=company.vat_number,
            timestamp_iso=time_str,
            total_amount=f"{tot:.2f}",
            vat_amount=f"{vat:.2f}"
        )

        Invoice.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot, zatca_qr_b64=qr_b64)

        ar_acc, _ = Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})
        sales_acc, _ = Account.objects.get_or_create(code="4000", defaults={"name": "Sales Revenue", "account_type": "Revenue"})
        vat_acc, _ = Account.objects.get_or_create(code="2100", defaults={"name": "VAT Output Tax (15%)", "account_type": "Liability"})

        je, _ = JournalEntry.objects.get_or_create(reference_no=f"INV-{self.invoice_no}", defaults={"description": f"Sales Tax Invoice #{self.invoice_no} to {self.customer.name}"})
        je.lines.all().delete()

        JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=tot, credit=0, description=f"Receivable from {self.customer.name}")
        JournalEntryLine.objects.create(journal_entry=je, account=sales_acc, debit=0, credit=sub, description=f"Revenue for Inv #{self.invoice_no}")
        JournalEntryLine.objects.create(journal_entry=je, account=vat_acc, debit=0, credit=vat, description="15% ZATCA Output VAT")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total = Decimal(self.qty) * Decimal(self.unit_price)
        super().save(*args, **kwargs)
        self.product.current_stock = models.F('current_stock') - self.qty
        self.product.save()

        if self.invoice.warehouse:
            ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.invoice.warehouse, product=self.product)
            ws.stock_qty = models.F('stock_qty') - self.qty
            ws.save()


# ১৩. Purchase Bill
class PurchaseBill(models.Model):
    bill_no = models.CharField(max_length=100, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)

    def __str__(self):
        return f"Bill #{self.bill_no} - {self.supplier.name}"

    def update_totals_and_post_accounting(self):
        sub = sum(item.total for item in self.items.all())
        vat = sub * Decimal('0.15')
        tot = sub + vat

        PurchaseBill.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot)

        inv_acc, _ = Account.objects.get_or_create(code="1300", defaults={"name": "Inventory Asset", "account_type": "Asset"})
        vat_in_acc, _ = Account.objects.get_or_create(code="1400", defaults={"name": "VAT Input Tax (15% Recoverable)", "account_type": "Asset"})
        ap_acc, _ = Account.objects.get_or_create(code="2000", defaults={"name": "Accounts Payable (Suppliers)", "account_type": "Liability"})

        je, _ = JournalEntry.objects.get_or_create(reference_no=f"BILL-{self.bill_no}", defaults={"description": f"Purchase Bill #{self.bill_no} from {self.supplier.name}"})
        je.lines.all().delete()

        JournalEntryLine.objects.create(journal_entry=je, account=inv_acc, debit=sub, credit=0, description=f"Stock In from {self.supplier.name}")
        JournalEntryLine.objects.create(journal_entry=je, account=vat_in_acc, debit=vat, credit=0, description="15% Input VAT Paid")
        JournalEntryLine.objects.create(journal_entry=je, account=ap_acc, debit=0, credit=tot, description=f"Payable to {self.supplier.name}")


class PurchaseBillItem(models.Model):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total = Decimal(self.qty) * Decimal(self.unit_cost)
        super().save(*args, **kwargs)
        self.product.current_stock = models.F('current_stock') + self.qty
        self.product.save()

        if self.bill.warehouse:
            ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.bill.warehouse, product=self.product)
            ws.stock_qty = models.F('stock_qty') + self.qty
            ws.save()


# ১৪. Inter-Warehouse Transfer
class StockTransfer(models.Model):
    transfer_no = models.CharField(max_length=100, unique=True, default="TR-001")
    date = models.DateField(default=datetime.now)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out')
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in')
    status = models.CharField(max_length=20, default='COMPLETED', choices=[('PENDING', 'Pending'), ('COMPLETED', 'Completed 🟢'), ('CANCELLED', 'Cancelled 🔴')])
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"سند تحويل #{self.transfer_no} ({self.source_warehouse.code} ➔ {self.destination_warehouse.code})"

    def execute_transfer(self):
        if self.status == 'COMPLETED':
            for item in self.items.all():
                s_ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.source_warehouse, product=item.product)
                s_ws.stock_qty = models.F('stock_qty') - item.qty
                s_ws.save()

                d_ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.destination_warehouse, product=item.product)
                d_ws.stock_qty = models.F('stock_qty') + item.qty
                d_ws.save()


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} ({self.qty} Pcs)"


# ১৫. Receipt & Payment Vouchers
class ReceiptVoucher(models.Model):
    voucher_no = models.CharField(max_length=100, unique=True, default="RV-001")
    date = models.DateField(default=datetime.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="Bank Transfer", choices=[
        ('Cash', 'Cash (نقدي)'), ('Bank Transfer', 'Bank Transfer (تحويل بنكي)'),
        ('Mada / Card', 'Mada / Card (شبكة)'), ('Cheque', 'Cheque (شيك)')
    ])
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"سند قبض #{self.voucher_no} - {self.customer.name} ({self.amount} SAR)"

    def post_accounting(self):
        self.bank_account.balance = models.F('balance') + self.amount
        self.bank_account.save()
        bank_chart_acc = self.bank_account.chart_account or Account.objects.get_or_create(code="1010", defaults={"name": "Cash & Bank Asset", "account_type": "Asset"})[0]
        ar_acc, _ = Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})

        je, _ = JournalEntry.objects.get_or_create(reference_no=f"RV-{self.voucher_no}", defaults={"description": f"Receipt Voucher #{self.voucher_no} from {self.customer.name}"})
        je.lines.all().delete()
        JournalEntryLine.objects.create(journal_entry=je, account=bank_chart_acc, debit=self.amount, credit=0, description=f"Received via {self.payment_method}")
        JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=0, credit=self.amount, description=f"Payment from {self.customer.name}")


class PaymentVoucher(models.Model):
    voucher_no = models.CharField(max_length=100, unique=True, default="PV-001")
    date = models.DateField(default=datetime.now)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_bill = models.ForeignKey(PurchaseBill, on_delete=models.SET_NULL, null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="Bank Transfer", choices=[
        ('Cash', 'Cash (نقدي)'), ('Bank Transfer', 'Bank Transfer (تحويل بنكي)'),
        ('Card', 'Card (بطاقة)'), ('Cheque', 'Cheque (شيك)')
    ])
    expense_reason = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        payee = self.supplier.name if self.supplier else self.expense_reason or "General Expense"
        return f"سند صرف #{self.voucher_no} - {payee} ({self.amount} SAR)"

    def post_accounting(self):
        self.bank_account.balance = models.F('balance') - self.amount
        self.bank_account.save()
        bank_chart_acc = self.bank_account.chart_account or Account.objects.get_or_create(code="1010", defaults={"name": "Cash & Bank Asset", "account_type": "Asset"})[0]
        debit_acc = Account.objects.get_or_create(code="2000", defaults={"name": "Accounts Payable (Suppliers)", "account_type": "Liability"})[0] if self.supplier else Account.objects.get_or_create(code="5000", defaults={"name": "Operating Expense", "account_type": "Expense"})[0]

        desc = f"Payment to supplier {self.supplier.name}" if self.supplier else self.expense_reason or "General Expense"
        je, _ = JournalEntry.objects.get_or_create(reference_no=f"PV-{self.voucher_no}", defaults={"description": f"Payment Voucher #{self.voucher_no} - {desc}"})
        je.lines.all().delete()
        JournalEntryLine.objects.create(journal_entry=je, account=debit_acc, debit=self.amount, credit=0, description=desc)
        JournalEntryLine.objects.create(journal_entry=je, account=bank_chart_acc, debit=0, credit=self.amount, description=f"Paid via {self.payment_method}")


# ১৬. Journal Entry Models
class JournalEntry(models.Model):
    date = models.DateField(auto_now_add=True)
    reference_no = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.reference_no} | {self.date}"

class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True, null=True)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
