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


# ৩. Divisions & Warehouses (SAMCO-এর ৫টি ডিভিশন)
class Warehouse(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150, help_text="اسم الفرع / المستودع")
    location = models.CharField(max_length=255, default="Riyadh, KSA")
    manager_name = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.name_en} ({self.name_ar})"


# ৪. Bank & Cash Accounts
class BankAccount(models.Model):
    name = models.CharField(max_length=150, help_text="Ex: Al Rajhi Bank, Petty Cash (الخزينة)")
    account_number = models.CharField(max_length=100, blank=True, null=True)
    branch = models.CharField(max_length=150, blank=True, null=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    chart_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="bank_records")

    def __str__(self):
        return f"{self.name} (Balance: {self.balance:.2f} SAR)"


# ৫. Customer
class Customer(models.Model):
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৬. Supplier
class Supplier(models.Model):
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ৭. Product (পণ্য ও কেন্দ্রীয় স্টক)
class Product(models.Model):
    cat_no = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)

    def __str__(self):
        return f"[{self.cat_no}] {self.name} (Total Stock: {self.current_stock})"


# ৮. Division-specific Stock (প্রতি ডিভিশনের আলাদা স্টক)
class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='division_stocks')
    stock_qty = models.IntegerField(default=0)

    class Meta:
        unique_together = ('warehouse', 'product')

    def __str__(self):
        return f"{self.warehouse.name_en} - {self.product.name} ({self.stock_qty} Pcs)"


# ৯. Quotation
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


# ১০. Sales Invoice (ZATCA Phase-2)
class Invoice(models.Model):
    invoice_no = models.CharField(max_length=100, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, help_text="Dispatching Division")
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
            defaults={"description": f"Sales Tax Invoice #{self.invoice_no} to {self.customer.name}"}
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

        # যদি কোনো নির্দিষ্ট ডিভিশন থাকে সেখান থেকেও স্টক মাইনাস হবে
        if self.invoice.warehouse:
            ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.invoice.warehouse, product=self.product)
            ws.stock_qty = models.F('stock_qty') - self.qty
            ws.save()


# ১১. Purchase Bill
class PurchaseBill(models.Model):
    bill_no = models.CharField(max_length=100, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, help_text="Receiving Division")
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

        je, _ = JournalEntry.objects.get_or_create(
            reference_no=f"BILL-{self.bill_no}",
            defaults={"description": f"Purchase Bill #{self.bill_no} from {self.supplier.name}"}
        )
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

        # নির্দিষ্ট ডিভিশন স্টকে যোগ করা
        if self.bill.warehouse:
            ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.bill.warehouse, product=self.product)
            ws.stock_qty = models.F('stock_qty') + self.qty
            ws.save()


# ১২. Inter-Warehouse Transfer (تحويل مخزني - ডিভিশন ট্রান্সফার স্লিপ)
class StockTransfer(models.Model):
    transfer_no = models.CharField(max_length=100, unique=True, default="TR-001")
    date = models.DateField(default=datetime.now)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out', help_text="From Division / من فرع")
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in', help_text="To Division / إلى فرع")
    status = models.CharField(max_length=20, default='COMPLETED', choices=[('PENDING', 'Pending'), ('COMPLETED', 'Completed 🟢'), ('CANCELLED', 'Cancelled 🔴')])
    notes = models.TextField(blank=True, null=True, help_text="Driver / Gate Pass notes")

    def __str__(self):
        return f"سند تحويل #{self.transfer_no} ({self.source_warehouse.code} ➔ {self.destination_warehouse.code})"

    def execute_transfer(self):
        """এক ডিভিশন থেকে স্টক কমিয়ে অন্য ডিভিশনে স্টক স্থানান্তর"""
        if self.status == 'COMPLETED':
            for item in self.items.all():
                # সোর্স ডিভিশন থেকে কমানো
                s_ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.source_warehouse, product=item.product)
                s_ws.stock_qty = models.F('stock_qty') - item.qty
                s_ws.save()

                # ডেস্টিনেশন ডিভিশনে বাড়ানো
                d_ws, _ = WarehouseStock.objects.get_or_create(warehouse=self.destination_warehouse, product=item.product)
                d_ws.stock_qty = models.F('stock_qty') + item.qty
                d_ws.save()


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} ({self.qty} Pcs)"


# ১৩. Receipt Voucher & Payment Voucher
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

        je, _ = JournalEntry.objects.get_or_create(
            reference_no=f"RV-{self.voucher_no}",
            defaults={"description": f"Receipt Voucher #{self.voucher_no} received from {self.customer.name}"}
        )
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
        je, _ = JournalEntry.objects.get_or_create(
            reference_no=f"PV-{self.voucher_no}",
            defaults={"description": f"Payment Voucher #{self.voucher_no} - {desc}"}
        )
        je.lines.all().delete()

        JournalEntryLine.objects.create(journal_entry=je, account=debit_acc, debit=self.amount, credit=0, description=desc)
        JournalEntryLine.objects.create(journal_entry=je, account=bank_chart_acc, debit=0, credit=self.amount, description=f"Paid via {self.payment_method}")


# ১৪. Journal Entry Models
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
