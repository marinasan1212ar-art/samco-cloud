from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from .models import Account, Customer, Supplier, Product, Invoice, PurchaseBill, BankAccount, ReceiptVoucher, PaymentVoucher, JournalEntry, CompanySettings
from .serializers import (
    AccountSerializer, CustomerSerializer, SupplierSerializer, ProductSerializer,
    InvoiceSerializer, PurchaseBillSerializer, BankAccountSerializer,
    ReceiptVoucherSerializer, PaymentVoucherSerializer, JournalEntrySerializer
)
from .zatca import generate_qr_image_base64

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('code')
    serializer_class = AccountSerializer

class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all().order_by('name')
    serializer_class = BankAccountSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('-id')
    serializer_class = CustomerSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('-id')
    serializer_class = SupplierSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('cat_no')
    serializer_class = ProductSerializer

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-id')
    serializer_class = InvoiceSerializer

class PurchaseBillViewSet(viewsets.ModelViewSet):
    queryset = PurchaseBill.objects.all().order_by('-id')
    serializer_class = PurchaseBillSerializer

class ReceiptVoucherViewSet(viewsets.ModelViewSet):
    queryset = ReceiptVoucher.objects.all().order_by('-id')
    serializer_class = ReceiptVoucherSerializer

class PaymentVoucherViewSet(viewsets.ModelViewSet):
    queryset = PaymentVoucher.objects.all().order_by('-id')
    serializer_class = PaymentVoucherSerializer

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all().order_by('-id')
    serializer_class = JournalEntrySerializer

def dashboard_view(request):
    total_sales = sum(inv.total_amount for inv in Invoice.objects.all())
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.all())
    total_bank_balance = sum(b.balance for b in BankAccount.objects.all())
    
    total_receipts = sum(rv.amount for rv in ReceiptVoucher.objects.all())
    total_payments = sum(pv.amount for pv in PaymentVoucher.objects.all())

    summary = {
        "total_sales_sar": total_sales,
        "total_purchases_sar": total_purchases,
        "total_bank_balance_sar": total_bank_balance,
        "total_receipts_sar": total_receipts,
        "total_payments_sar": total_payments,
        "net_profit_sar": total_sales - total_purchases,
        "total_products": Product.objects.count(),
        "total_customers": Customer.objects.count(),
        "total_suppliers": Supplier.objects.count(),
    }
    invoices = Invoice.objects.all().order_by('-id')[:5]
    purchases = PurchaseBill.objects.all().order_by('-id')[:5]
    recent_receipts = ReceiptVoucher.objects.all().order_by('-id')[:5]
    recent_payments = PaymentVoucher.objects.all().order_by('-id')[:5]

    return render(request, 'accounting/dashboard.html', {
        'summary': summary,
        'invoices': invoices,
        'purchases': purchases,
        'recent_receipts': recent_receipts,
        'recent_payments': recent_payments
    })

def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    company, _ = CompanySettings.objects.get_or_create(id=1)
    
    if not invoice.zatca_qr_b64:
        invoice.update_totals_and_post_accounting()
        invoice.refresh_from_db()

    qr_img = ""
    if invoice.zatca_qr_b64:
        qr_img = generate_qr_image_base64(invoice.zatca_qr_b64)

    return render(request, 'accounting/invoice_detail.html', {
        'invoice': invoice,
        'company': company,
        'qr_image': qr_img
    })

def voucher_print_view(request, v_type, pk):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if v_type == 'receipt':
        voucher = get_object_or_404(ReceiptVoucher, pk=pk)
        title_en = "RECEIPT VOUCHER"
        title_ar = "سند قبض"
        party_label = "Received From / استلمنا من"
        party_name = voucher.customer.name
    else:
        voucher = get_object_or_404(PaymentVoucher, pk=pk)
        title_en = "PAYMENT VOUCHER"
        title_ar = "سند صرف"
        party_label = "Paid To / يصرف إلى"
        party_name = voucher.supplier.name if voucher.supplier else voucher.expense_reason or "Expense"

    return render(request, 'accounting/voucher_print.html', {
        'voucher': voucher,
        'v_type': v_type,
        'title_en': title_en,
        'title_ar': title_ar,
        'party_label': party_label,
        'party_name': party_name,
        'company': company
    })
