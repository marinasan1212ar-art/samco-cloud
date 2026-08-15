from django.db import models
from decimal import Decimal

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


# ২. Customer (গ্রাহক)
class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True, help_text="Saudi 15-digit VAT ID")
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৩. Product (পণ্য ও স্টক)
class Product(models.Model):
    cat_no = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)

    def __str__(self):
        return f"[{self.cat_no}] {self.name} (Stock: {self.current_stock})"


# ৪. Journal Entry (অ্যাকাউন্টিং ট্রানজেকশন)
class JournalEntry(models.Model):
    date = models.DateField(auto_now_add=True)
    reference_no = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.reference_no} | {self.date}"


# ৫. Journal Lines (ডেবিট ও ক্রেডিট লাইন)
class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True, null=True)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.account.name} | Dr: {self.debit} | Cr: {self.credit}"


# ৬. Sales Invoice (Quyod Auto-Accounting Engine)
class Invoice(models.Model):
    invoice_no = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    date = models.DateField(auto_now_add=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)

    def __str__(self):
        return f"Invoice #{self.invoice_no} - {self.customer.name}"

    def update_totals_and_post_accounting(self):
        """স্বয়ংক্রিয়ভাবে ভ্যাট হিসাব, স্টক মাইনাস এবং ডেবিট-ক্রেডিট জার্নাল তৈরি"""
        sub = sum(item.total for item in self.items.all())
        vat = sub * Decimal('0.15') # ১৫% সৌদি ভ্যাট
        tot = sub + vat

        self.subtotal = sub
        self.vat_amount = vat
        self.total_amount = tot
        Invoice.objects.filter(pk=self.pk).update(subtotal=sub, vat_amount=vat, total_amount=tot)

        # ১. ডিফল্ট অ্যাকাউন্ট লোড করা (না থাকলে নিজে তৈরি করবে)
        ar_acc, _ = Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable (Customer)", "account_type": "Asset"})
        sales_acc, _ = Account.objects.get_or_create(code="4000", defaults={"name": "Sales Revenue", "account_type": "Revenue"})
        vat_acc, _ = Account.objects.get_or_create(code="2100", defaults={"name": "VAT Output Tax (15%)", "account_type": "Liability"})

        # ২. ডাবল-এন্ট্রি জার্নাল তৈরি
        je, _ = JournalEntry.objects.get_or_create(
            reference_no=f"INV-{self.invoice_no}",
            defaults={"description": f"Auto-Journal for Sales Invoice #{self.invoice_no} to {self.customer.name}"}
        )
        je.lines.all().delete() # রি-ক্যালকুলেশনের জন্য আগের লাইন ক্লিয়ার

        # ডেবিট: কাস্টমার অ্যাকাউন্ট (টোটাল টাকা)
        JournalEntryLine.objects.create(journal_entry=je, account=ar_acc, debit=tot, credit=0, description=f"Receivable from {self.customer.name}")
        # ক্রেডিট: সেলস রেভিনিউ (মূল টাকা)
        JournalEntryLine.objects.create(journal_entry=je, account=sales_acc, debit=0, credit=sub, description=f"Revenue for Inv #{self.invoice_no}")
        # ক্রেডিট: ভ্যাট ট্যাক্স (১৫% ভ্যাট)
        JournalEntryLine.objects.create(journal_entry=je, account=vat_acc, debit=0, credit=vat, description="15% ZATCA VAT Collected")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total = Decimal(self.qty) * Decimal(self.unit_price)
        super().save(*args, **kwargs)
        
        # স্টক থেকে পণ্য কমিয়ে দেওয়া
        self.product.current_stock = models.F('current_stock') - self.qty
        self.product.save()
