from django.db import models, transaction
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
import uuid
from datetime import datetime
from .zatca import generate_zatca_qr_base64, generate_qr_image_base64

class Company(models.Model):
    name = models.CharField(max_length=255, help_text="Company Name (English)")
    name_ar = models.CharField(max_length=255, blank=True, null=True, help_text="اسم الشركة بالعربية")
    vat_number = models.CharField(max_length=50, default="310122456700003", help_text="Saudi 15-Digit VAT ID")
    cr_number = models.CharField(max_length=50, default="1010445566", help_text="Commercial Registration No")
    address = models.TextField(default="Riyadh Industrial City, Saudi Arabia")
    phone = models.CharField(max_length=50, default="+966 11 000 0000")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CompanySettings(models.Model):
    company_name_en = models.CharField(max_length=255, default="SECOND ADVANCE MEDICAL COMPANY")
    company_name_ar = models.CharField(max_length=255, default="الشركة الطبية المتقدمة الثانية")
    vat_number = models.CharField(max_length=50, default="310122456700003")
    cr_number = models.CharField(max_length=50, default="1010445566")
    address_en = models.TextField(default="Riyadh Industrial City, Saudi Arabia")
    address_ar = models.TextField(default="المنطقة الصناعية، الرياض، المملكة العربية السعودية")
    phone = models.CharField(max_length=50, default="+966 11 000 0000")

    def __str__(self):
        return self.company_name_en

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    price_monthly_sar = models.DecimalField(max_digits=10, decimal_places=2, default=99.00)
    price_yearly_sar = models.DecimalField(max_digits=10, decimal_places=2, default=999.00)
    max_users = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CompanySubscription(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, default='ACTIVE')
    start_date = models.DateField(default=datetime.now)
    expiry_date = models.DateField(default=datetime.now)

    def __str__(self):
        return f"{self.company.name} ({self.status})"

class PaymentTransaction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payments')
    transaction_id = models.CharField(max_length=100, default=uuid.uuid4)
    amount_sar = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Mada')
    status = models.CharField(max_length=20, default='PAID')
    payment_date = models.DateTimeField(auto_now_add=True)

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin / General Manager (المدير العام)'),
        ('ACCOUNTANT', 'Accountant (المحاسب)'),
        ('SALESMAN', 'Salesman (مندوب مبيعات)'),
        ('WAREHOUSE_KEEPER', 'Warehouse Keeper (أمين المستودع)'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='ADMIN')
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        comp, _ = Company.objects.get_or_create(id=1, defaults={"name": "SECOND ADVANCE MEDICAL COMPANY (SAMCO)", "vat_number": "310122456700003"})
        UserProfile.objects.create(user=instance, company=comp)
    else:
        try:
            instance.profile.save()
        except UserProfile.DoesNotExist:
            comp, _ = Company.objects.get_or_create(id=1, defaults={"name": "SECOND ADVANCE MEDICAL COMPANY (SAMCO)", "vat_number": "310122456700003"})
            UserProfile.objects.create(user=instance, company=comp)

class CostCenter(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="cost_centers")
    code = models.CharField(max_length=50)
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"[{self.code}] {self.name_en}"

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('Asset', 'Asset (الأصول)'),
        ('Liability', 'Liability (الخصوم)'),
        ('Equity', 'Equity (حقوق الملكية)'),
        ('Revenue', 'Revenue (الإيرادات)'),
        ('Expense', 'Expense (المصروفات)'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="accounts")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type})"

class FixedAsset(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="fixed_assets")
    asset_code = models.CharField(max_length=50, default="AST-001")
    name = models.CharField(max_length=255)
    purchase_date = models.DateField(default=datetime.now)
    purchase_cost = models.DecimalField(max_digits=15, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    useful_life_years = models.IntegerField(default=5)
    depreciation_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)

    def current_book_value(self):
        return self.purchase_cost - self.accumulated_depreciation

    def __str__(self):
        return f"{self.name} ({self.current_book_value():.2f} SAR)"

class Employee(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="employees")
    employee_no = models.CharField(max_length=50, default="EMP-001")
    name_en = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    iqama_no = models.CharField(max_length=50, help_text="Saudi National ID / Iqama")
    iqama_expiry = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=100, default="Saudi")
    bank_iban = models.CharField(max_length=50, help_text="Saudi IBAN")
    bank_name = models.CharField(max_length=100, default="Al Rajhi Bank")
    joining_date = models.DateField(default=datetime.now)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=3000.00)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    other_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def total_monthly_salary(self):
        return self.basic_salary + self.housing_allowance + self.transport_allowance + self.other_allowance

    def __str__(self):
        return f"{self.name_en} ({self.employee_no})"

class MonthlyPayroll(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="payrolls")
    month_year = models.CharField(max_length=20)
    processed_date = models.DateField(default=datetime.now)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Payroll {self.month_year} - {self.total_amount:.2f} SAR"

class PayrollItem(models.Model):
    payroll = models.ForeignKey(MonthlyPayroll, on_delete=models.CASCADE, related_name="items")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    housing = models.DecimalField(max_digits=10, decimal_places=2)
    transport = models.DecimalField(max_digits=10, decimal_places=2)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)

class Warehouse(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="warehouses")
    code = models.CharField(max_length=50)
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150)
    location = models.CharField(max_length=255, default="Riyadh, KSA")
    manager_name = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.name_en} ({self.name_ar})"

class BankAccount(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="banks")
    name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    branch = models.CharField(max_length=150, blank=True, null=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    chart_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="bank_records")

    def __str__(self):
        return f"{self.name} ({self.balance:.2f} SAR)"

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="customers")
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=50000.00)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="suppliers")
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    ITEM_TYPES = [
        ('FINISHED_GOOD', 'Finished Good (منتج نهائي)'),
        ('RAW_MATERIAL', 'Raw Material (مادة خام)'),
        ('PACKAGING', 'Packaging Material (مواد تعبئة)'),
        ('SERVICE', 'Service (خدمة)'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="products")
    cat_no = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    item_type = models.CharField(max_length=30, choices=ITEM_TYPES, default='FINISHED_GOOD')
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)
    barcode = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"[{self.cat_no}] {self.name} (Stock: {self.current_stock})"

class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='division_stocks')
    stock_qty = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.warehouse.name_en} - {self.product.name} ({self.stock_qty} Pcs)"

class StockAdjustment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="stock_adjustments")
    adjustment_no = models.CharField(max_length=100, default="ADJ-001")
    date = models.DateField(default=datetime.now)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    system_qty = models.IntegerField()
    physical_qty = models.IntegerField()
    variance_qty = models.IntegerField()
    reason = models.CharField(max_length=255)

    def apply_adjustment(self):
        diff = self.physical_qty - self.system_qty
        self.product.current_stock = models.F('current_stock') + diff
        self.product.save()

class Quotation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="quotations")
    quote_no = models.CharField(max_length=100)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, default='PENDING')
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

class SalesOrder(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="sales_orders")
    so_number = models.CharField(max_length=100, default="SO-001")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    date = models.DateField(default=datetime.now)
    status = models.CharField(max_length=20, default='CONFIRMED')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"SO #{self.so_number} - {self.customer.name}"

class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid (غير مدفوع) 🔴'),
        ('PARTIALLY_PAID', 'Partially Paid (مدفوع جزئياً) 🟡'),
        ('PAID', 'Paid (مدفوع) 🟢'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="invoices")
    invoice_no = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    invoice_type = models.CharField(max_length=50, default='Tax Invoice (فاتورة ضريبية)')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    zatca_qr_b64 = models.TextField(blank=True, null=True, editable=False)

    def remaining_due(self):
        return max(Decimal('0.00'), self.total_amount - self.amount_paid)

    def __str__(self):
        return f"Invoice #{self.invoice_no} - {self.customer.name} ({self.get_payment_status_display()})"

    def recalculate_payment_status(self):
        paid = sum(rv.amount for rv in self.receipts.all())
        self.amount_paid = paid
        if paid >= self.total_amount and self.total_amount > 0:
            self.payment_status = 'PAID'
        elif paid > 0:
            self.payment_status = 'PARTIALLY_PAID'
        else:
            self.payment_status = 'UNPAID'
        Invoice.objects.filter(pk=self.pk).update(amount_paid=self.amount_paid, payment_status=self.payment_status)

    def update_totals_and_post_accounting(self):
        with transaction.atomic():
            sub = sum(item.total for item in self.items.all())
            vat = sub * Decimal('0.15')
            tot = sub + vat
            comp = self.company or Company.objects.get_or_create(id=1)[0]
            time_str = self.date.strftime("%Y-%m-%dT%H:%M:%SZ") if self.date else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            qr_b64 = generate_zatca_qr_base64(seller_name=comp.name, vat_no=comp.vat_number or "310122456700003", timestamp_iso=time_str, total_amount=f"{tot:.2f}", vat_amount=f"{vat:.2f}")
            Invoice.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot, zatca_qr_b64=qr_b64)
            ar_acc, _ = Account.objects.get_or_create(company=comp, code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})
            sales_acc, _ = Account.objects.get_or_create(company=comp, code="4000", defaults={"name": "Sales Revenue", "account_type": "Revenue"})
            vat_acc, _ = Account.objects.get_or_create(company=comp, code="2100", defaults={"name": "VAT Output Tax (15%)", "account_type": "Liability"})
            je, _ = JournalEntry.objects.get_or_create(company=comp, reference_no=f"INV-{self.invoice_no}", defaults={"description": f"Sales Tax Invoice #{self.invoice_no} to {self.customer.name}"})
            je.lines.all().delete()
            JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=tot, credit=0, description=f"Receivable from {self.customer.name}")
            JournalEntryLine.objects.create(journal_entry=je, account=sales_acc, debit=0, credit=sub, description=f"Revenue for Inv #{self.invoice_no}")
            JournalEntryLine.objects.create(journal_entry=je, account=vat_acc, debit=0, credit=vat, description="15% ZATCA Output VAT")
            self.recalculate_payment_status()

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

    def delete(self, *args, **kwargs):
        self.product.current_stock = models.F('current_stock') + self.qty
        self.product.save()
        super().delete(*args, **kwargs)

class CreditNote(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="credit_notes")
    credit_note_no = models.CharField(max_length=100, default="CN-001")
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="credit_notes")
    date = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, default="Goods Returned by Customer (مرتجع بضاعة)")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    zatca_qr_b64 = models.TextField(blank=True, null=True, editable=False)

    def __str__(self):
        return f"Credit Note #{self.credit_note_no} (For Inv #{self.invoice.invoice_no})"

    def update_totals_and_post_accounting(self):
        with transaction.atomic():
            sub = sum(item.total for item in self.items.all())
            vat = sub * Decimal('0.15')
            tot = sub + vat
            comp = self.company or Company.objects.get_or_create(id=1)[0]
            time_str = self.date.strftime("%Y-%m-%dT%H:%M:%SZ") if self.date else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            qr_b64 = generate_zatca_qr_base64(seller_name=comp.name, vat_no=comp.vat_number or "310122456700003", timestamp_iso=time_str, total_amount=f"-{tot:.2f}", vat_amount=f"-{vat:.2f}")
            CreditNote.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot, zatca_qr_b64=qr_b64)
            sales_acc, _ = Account.objects.get_or_create(company=comp, code="4000", defaults={"name": "Sales Revenue", "account_type": "Revenue"})
            vat_acc, _ = Account.objects.get_or_create(company=comp, code="2100", defaults={"name": "VAT Output Tax (15%)", "account_type": "Liability"})
            ar_acc, _ = Account.objects.get_or_create(company=comp, code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})
            je, _ = JournalEntry.objects.get_or_create(company=comp, reference_no=f"CN-{self.credit_note_no}", defaults={"description": f"Credit Note #{self.credit_note_no} for Inv #{self.invoice.invoice_no}"})
            je.lines.all().delete()
            JournalEntryLine.objects.create(journal_entry=je, account=sales_acc, debit=sub, credit=0, description=f"Sales Return #{self.credit_note_no}")
            JournalEntryLine.objects.create(journal_entry=je, account=vat_acc, debit=vat, credit=0, description="Reversal of Output VAT 15%")
            JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=0, credit=tot, description=f"Credit Adjust for {self.invoice.customer.name}")

class CreditNoteItem(models.Model):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total = Decimal(self.qty) * Decimal(self.unit_price)
        super().save(*args, **kwargs)
        self.product.current_stock = models.F('current_stock') + self.qty
        self.product.save()

    def delete(self, *args, **kwargs):
        self.product.current_stock = models.F('current_stock') - self.qty
        self.product.save()
        super().delete(*args, **kwargs)

class PurchaseOrder(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="purchase_orders")
    po_number = models.CharField(max_length=100, default="PO-001")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    date = models.DateField(default=datetime.now)
    status = models.CharField(max_length=20, default='ISSUED')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"PO #{self.po_number} - {self.supplier.name}"

class PurchaseBill(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid (غير مدفوع) 🔴'),
        ('PARTIALLY_PAID', 'Partially Paid (مدفوع جزئياً) 🟡'),
        ('PAID', 'Paid (مدفوع) 🟢'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="purchases")
    bill_no = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')

    def remaining_due(self):
        return max(Decimal('0.00'), self.total_amount - self.amount_paid)

    def __str__(self):
        return f"Bill #{self.bill_no} - {self.supplier.name}"

    def recalculate_payment_status(self):
        paid = sum(pv.amount for pv in self.payments.all())
        self.amount_paid = paid
        if paid >= self.total_amount and self.total_amount > 0:
            self.payment_status = 'PAID'
        elif paid > 0:
            self.payment_status = 'PARTIALLY_PAID'
        else:
            self.payment_status = 'UNPAID'
        PurchaseBill.objects.filter(pk=self.pk).update(amount_paid=self.amount_paid, payment_status=self.payment_status)

    def update_totals_and_post_accounting(self):
        with transaction.atomic():
            sub = sum(item.total for item in self.items.all())
            vat = sub * Decimal('0.15')
            tot = sub + vat
            comp = self.company or Company.objects.get_or_create(id=1)[0]
            PurchaseBill.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot)
            inv_acc, _ = Account.objects.get_or_create(company=comp, code="1300", defaults={"name": "Inventory Asset", "account_type": "Asset"})
            vat_in_acc, _ = Account.objects.get_or_create(company=comp, code="1400", defaults={"name": "VAT Input Tax (15%)", "account_type": "Asset"})
            ap_acc, _ = Account.objects.get_or_create(company=comp, code="2000", defaults={"name": "Accounts Payable (Suppliers)", "account_type": "Liability"})
            je, _ = JournalEntry.objects.get_or_create(company=comp, reference_no=f"BILL-{self.bill_no}", defaults={"description": f"Purchase Bill #{self.bill_no} from {self.supplier.name}"})
            je.lines.all().delete()
            JournalEntryLine.objects.create(journal_entry=je, account=inv_acc, debit=sub, credit=0, description=f"Stock In from {self.supplier.name}")
            JournalEntryLine.objects.create(journal_entry=je, account=vat_in_acc, debit=vat, credit=0, description="15% Input VAT Paid")
            JournalEntryLine.objects.create(journal_entry=je, account=ap_acc, debit=0, credit=tot, description=f"Payable to {self.supplier.name}")
            self.recalculate_payment_status()

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
        self.product.cost_price = self.unit_cost
        self.product.save()

    def delete(self, *args, **kwargs):
        self.product.current_stock = models.F('current_stock') - self.qty
        self.product.save()
        super().delete(*args, **kwargs)

class StockTransfer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="transfers")
    transfer_no = models.CharField(max_length=100, default="TR-001")
    date = models.DateField(default=datetime.now)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out')
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in')
    status = models.CharField(max_length=20, default='COMPLETED')
    notes = models.TextField(blank=True, null=True)

    def execute_transfer(self):
        if self.status == 'COMPLETED':
            with transaction.atomic():
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

class ReceiptVoucher(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="receipts")
    voucher_no = models.CharField(max_length=100, default="RV-001")
    date = models.DateField(default=datetime.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="receipts")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="Bank Transfer")
    notes = models.TextField(blank=True, null=True)

    def post_accounting(self):
        with transaction.atomic():
            self.bank_account.balance = models.F('balance') + self.amount
            self.bank_account.save()
            comp = self.company or Company.objects.get_or_create(id=1)[0]
            bank_chart_acc = self.bank_account.chart_account or Account.objects.get_or_create(company=comp, code="1010", defaults={"name": "Cash & Bank Asset", "account_type": "Asset"})[0]
            ar_acc, _ = Account.objects.get_or_create(company=comp, code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})
            je, _ = JournalEntry.objects.get_or_create(company=comp, reference_no=f"RV-{self.voucher_no}", defaults={"description": f"Receipt Voucher #{self.voucher_no} from {self.customer.name}"})
            je.lines.all().delete()
            JournalEntryLine.objects.create(journal_entry=je, account=bank_chart_acc, debit=self.amount, credit=0, description=f"Received via {self.payment_method}")
            JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=0, credit=self.amount, description=f"Payment from {self.customer.name}")
            if self.invoice:
                self.invoice.recalculate_payment_status()

class PaymentVoucher(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="payments_vouchers")
    voucher_no = models.CharField(max_length=100, default="PV-001")
    date = models.DateField(default=datetime.now)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_bill = models.ForeignKey(PurchaseBill, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="Bank Transfer")
    expense_reason = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def post_accounting(self):
        with transaction.atomic():
            self.bank_account.balance = models.F('balance') - self.amount
            self.bank_account.save()
            comp = self.company or Company.objects.get_or_create(id=1)[0]
            bank_chart_acc = self.bank_account.chart_account or Account.objects.get_or_create(company=comp, code="1010", defaults={"name": "Cash & Bank Asset", "account_type": "Asset"})[0]
            debit_acc = Account.objects.get_or_create(company=comp, code="2000", defaults={"name": "Accounts Payable (Suppliers)", "account_type": "Liability"})[0] if self.supplier else Account.objects.get_or_create(code="5000", defaults={"name": "Operating Expense", "account_type": "Expense"})[0]
            desc = f"Payment to supplier {self.supplier.name}" if self.supplier else self.expense_reason or "General Expense"
            je, _ = JournalEntry.objects.get_or_create(company=comp, reference_no=f"PV-{self.voucher_no}", defaults={"description": f"Payment Voucher #{self.voucher_no} - {desc}"})
            je.lines.all().delete()
            JournalEntryLine.objects.create(journal_entry=je, account=debit_acc, debit=self.amount, credit=0, description=desc)
            JournalEntryLine.objects.create(journal_entry=je, account=bank_chart_acc, debit=0, credit=self.amount, description=f"Paid via {self.payment_method}")
            if self.purchase_bill:
                self.purchase_bill.recalculate_payment_status()

class BillOfMaterials(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="boms")
    bom_code = models.CharField(max_length=100, default="BOM-001")
    finished_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="boms")
    output_qty = models.IntegerField(default=1)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.bom_code} - {self.finished_product.name}"

class BOMItem(models.Model):
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.CASCADE, related_name="components")
    raw_material = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="used_in_boms")
    quantity_required = models.DecimalField(max_digits=10, decimal_places=3)
    scrap_allowance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

class WorkOrder(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="work_orders")
    order_no = models.CharField(max_length=100, default="WO-001")
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True)
    planned_qty = models.IntegerField(default=1000)
    actual_qty_produced = models.IntegerField(default=0)
    start_date = models.DateField(default=datetime.now)
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, default='DRAFT')
    material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    machine_overhead = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_batch_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def execute_production_completion(self):
        if self.status == 'COMPLETED' and self.actual_qty_produced > 0:
            with transaction.atomic():
                batch_ratio = Decimal(self.actual_qty_produced) / Decimal(self.bom.output_qty)
                calculated_mat_cost = Decimal('0.00')
                for comp in self.bom.components.all():
                    needed_qty = (comp.quantity_required * batch_ratio) * (1 + (comp.scrap_allowance_pct / 100))
                    comp.raw_material.current_stock = models.F('current_stock') - int(needed_qty)
                    comp.raw_material.save()
                    calculated_mat_cost += Decimal(needed_qty) * comp.raw_material.cost_price
                tot_cost = calculated_mat_cost + self.labor_cost + self.machine_overhead
                u_cost = tot_cost / Decimal(self.actual_qty_produced)
                WorkOrder.objects.filter(pk=self.pk).update(material_cost=calculated_mat_cost, total_batch_cost=tot_cost, unit_cost=u_cost)
                fg = self.bom.finished_product
                fg.current_stock = models.F('current_stock') + self.actual_qty_produced
                fg.cost_price = u_cost
                fg.save()
                ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.warehouse, product=fg)
                ws.stock_qty = models.F('stock_qty') + self.actual_qty_produced
                ws.save()

class JournalEntry(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="journal_entries")
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
