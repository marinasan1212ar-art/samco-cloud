from django.db import models
from django.utils import timezone
import uuid

class CompanySettings(models.Model):
    company_name_en = models.CharField(max_length=255, default="SECOND ADVANCE MEDICAL COMPANY (SAMCO)")
    company_name_ar = models.CharField(max_length=255, default="شركة التقدم الطبي الثانية")
    vat_number = models.CharField(max_length=50, default="300000000000003")
    cr_number = models.CharField(max_length=50, default="1010445566")
    address = models.TextField(default="Riyadh, Kingdom of Saudi Arabia")
    phone = models.CharField(max_length=50, default="+966 11 000 0000")
    email = models.EmailField(default="info@samco.sa")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)

    class Meta:
        verbose_name = "Company Setting"
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return self.company_name_en

# -------------------------------------------------------------------------
# 👤 DIVISION USER / MANAGER REGISTRATION MODEL
# -------------------------------------------------------------------------
class DivisionManager(models.Model):
    DIVISION_CHOICES = [
        ('Warehouse', 'Warehouse Division'),
        ('Media', 'Media Division'),
        ('Plastic', 'Plastic Division'),
        ('Cosmetic', 'Cosmetic Division'),
        ('Powder', 'Powder Division'),
        ('Super Admin', 'Super Admin Suite'),
    ]
    division = models.CharField(max_length=50, choices=DIVISION_CHOICES, default='Warehouse')
    username = models.CharField(max_length=150, default="")
    password = models.CharField(max_length=128, default="")
    email = models.EmailField(verbose_name="Gmail / Email", null=True, blank=True)
    contact_number = models.CharField(max_length=50, verbose_name="Contract / Contact Number", null=True, blank=True)
    image = models.FileField(upload_to='division_users/', verbose_name="PNG Image", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)

    class Meta:
        verbose_name = "Division Manager / User"
        verbose_name_plural = "Division Managers / Users"

    def __str__(self):
        return f"{self.username} ({self.division})"

class Customer(models.Model):
    name = models.CharField(max_length=255, default="Customer")
    name_ar = models.CharField(max_length=255, null=True, blank=True)
    vat_number = models.CharField(max_length=50, null=True, blank=True)
    cr_number = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=255, default="Supplier")
    vat_number = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    contact_person = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    cat_no = models.CharField(max_length=100, default="", null=True, blank=True)
    item_name = models.CharField(max_length=255, default="")
    category = models.CharField(max_length=100, default="Warehouse")
    unit = models.CharField(max_length=50, default="Pcs")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    batch_no = models.CharField(max_length=100, null=True, blank=True)
    exp_date = models.CharField(max_length=50, null=True, blank=True)
    current_stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.cat_no}] {self.item_name}"

class PriceList(models.Model):
    name = models.CharField(max_length=100, default="Standard")
    currency = models.CharField(max_length=10, default="SAR")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.discount_percentage}%)"

class Invoice(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=100, default="")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    invoice_type = models.CharField(max_length=50, default="Tax Invoice")
    status = models.CharField(max_length=50, default="PAID")
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)

    def __str__(self):
        return f"Invoice {self.invoice_number}"

class Quotation(models.Model):
    quotation_number = models.CharField(max_length=100, default="")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default="Draft")

    def __str__(self):
        return f"Quote {self.quotation_number}"

class RecurringInvoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    frequency = models.CharField(max_length=50, default="Monthly")
    next_date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Recurring - {self.frequency}"

class PurchaseBill(models.Model):
    bill_number = models.CharField(max_length=100, default="")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True)
    bill_date = models.DateField(default=timezone.now)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default="PAID")

    def __str__(self):
        return f"Bill {self.bill_number}"

class DirectExpense(models.Model):
    date = models.DateField(default=timezone.now)
    expense_category = models.CharField(max_length=100, default="General Expense")
    vendor_name = models.CharField(max_length=255, null=True, blank=True)
    vat_number = models.CharField(max_length=50, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.expense_category} - SAR {self.total_amount}"

class Worker(models.Model):
    name = models.CharField(max_length=255, default="")
    finger_no = models.CharField(max_length=50, default="", null=True, blank=True)
    iqama_no = models.CharField(max_length=50, default="", null=True, blank=True)
    iqama_exp = models.DateField(null=True, blank=True)
    mobile = models.CharField(max_length=50, null=True, blank=True)
    nationality = models.CharField(max_length=100, default="Bangladeshi")
    org_type = models.CharField(max_length=100, default="Company Personnel")
    joining_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=50, default="Active")

    def __str__(self):
        return f"{self.name}"

class AttendanceLog(models.Model):
    date = models.DateField(default=timezone.now)
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, null=True, blank=True)
    check_in = models.CharField(max_length=50, default="08:00:00")
    check_out = models.CharField(max_length=50, default="17:00:00")
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=8.00)
    status = models.CharField(max_length=50, default="Present")

    def __str__(self):
        return f"Attendance {self.date}"

class SalarySheet(models.Model):
    month = models.CharField(max_length=50, default="")
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, null=True, blank=True)
    present_days = models.IntegerField(default=30)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=15.00)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default="PAID 🟢")
    paid_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Salary {self.month}"

class DeliveryNote(models.Model):
    date = models.DateField(default=timezone.now)
    location = models.CharField(max_length=255, default="")
    gate_no = models.CharField(max_length=50, null=True, blank=True)
    ref_po = models.CharField(max_length=100, null=True, blank=True)
    pdf_path = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Delivery Note - {self.location}"

class TransferSlip(models.Model):
    slip_no = models.CharField(max_length=100, default="")
    date = models.DateField(default=timezone.now)
    target_division = models.CharField(max_length=100, default="Media")
    cat_no = models.CharField(max_length=100, default="")
    item_name = models.CharField(max_length=255, default="")
    batch_no = models.CharField(max_length=100, null=True, blank=True)
    qty = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="TRANSFERRED")

    def __str__(self):
        return f"{self.slip_no} - {self.item_name}"

class VehicleBill(models.Model):
    entry_date = models.DateField(default=timezone.now)
    bill_type = models.CharField(max_length=50, default="Petrol")
    voucher_no = models.CharField(max_length=100, null=True, blank=True)
    driver_name = models.CharField(max_length=100, null=True, blank=True)
    qty_litres = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.bill_type} - SAR {self.amount}"

class RejectLog(models.Model):
    date = models.DateField(default=timezone.now)
    cat_no = models.CharField(max_length=100, default="")
    item_name = models.CharField(max_length=255, default="")
    lot_no = models.CharField(max_length=100, null=True, blank=True)
    qty = models.IntegerField(default=0)
    unit = models.CharField(max_length=50, default="Pcs")
    reason = models.TextField(default="")
    permission_by = models.CharField(max_length=50, default="QA")

    def __str__(self):
        return f"Reject - {self.item_name}"

class Account(models.Model):
    account_code = models.CharField(max_length=50, default="1000", null=True, blank=True)
    name = models.CharField(max_length=255, default="General Account")
    account_type = models.CharField(max_length=100, default="Asset")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    def __str__(self):
        return f"[{self.account_code}] {self.name}"

class JournalEntry(models.Model):
    date = models.DateField(default=timezone.now)
    description = models.TextField(default="General Entry")
    debit_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="debits", null=True, blank=True)
    credit_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="credits", null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"

    def __str__(self):
        return f"Entry {self.date} - SAR {self.amount}"
