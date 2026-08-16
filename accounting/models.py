from django.db import models
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


# ৩. Customer
class Customer(models.Model):
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True, help_text="الاسم بالعربية")
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True, help_text="Customer VAT ID")
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৪. Product
class Product(models.Model):
    cat_no = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True, help_text="اسم الصنف")
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)

    def __str__(self):
        return f"[{self.cat_no}] {self.name} (Stock: {self.current_stock})"


# ৫. Quotation
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


# ৬. Invoice (ZATCA Phase-2)
class Invoice(models.Model):
    invoice_no = models.CharField(max_length=100, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
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

        Invoice.objects.filter(pk=self.pk).update(
            subtotal=sub, vat_amount=vat, total_amount=tot, zatca_qr_b64=qr_b64
        )

        ar_acc, _ = Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "Asset"})
        sales_acc, _ = Account.objects.get_or_create(code="4000", defaults={"name": "Sales Revenue", "account_type": "Revenue"})
        vat_acc, _ = Account.objects.get_or_create(code="2100", defaults={"name": "VAT Output Tax (15%)", "account_type": "Liability"})

        je, _ = JournalEntry.objects.get_or_create(
            reference_no=f"INV-{self.invoice_no}",
            defaults={"description": f"ZATCA Sales Tax Invoice #{self.invoice_no} to {self.customer.name}"}
        )
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


# ৭. Journal Entry Models
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
