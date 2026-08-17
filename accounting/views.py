from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from .models import Account, Customer, Supplier, Product, Invoice, PurchaseBill, JournalEntry, CompanySettings
from .serializers import (
    AccountSerializer, CustomerSerializer, SupplierSerializer, ProductSerializer,
    InvoiceSerializer, PurchaseBillSerializer, JournalEntrySerializer
)
from .zatca import generate_qr_image_base64

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('code')
    serializer_class = AccountSerializer

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

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all().order_by('-id')
    serializer_class = JournalEntrySerializer

def dashboard_view(request):
    total_sales = sum(inv.total_amount for inv in Invoice.objects.all())
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.all())
    total_sales_vat = sum(inv.vat_amount for inv in Invoice.objects.all())
    total_pur_vat = sum(bill.vat_amount for bill in PurchaseBill.objects.all())
    
    net_profit = total_sales - total_purchases
    net_vat_payable = total_sales_vat - total_pur_vat

    summary = {
        "total_sales_sar": total_sales,
        "total_purchases_sar": total_purchases,
        "net_profit_sar": net_profit,
        "net_vat_payable_sar": net_vat_payable,
        "total_products": Product.objects.count(),
        "total_customers": Customer.objects.count(),
        "total_suppliers": Supplier.objects.count(),
    }
    invoices = Invoice.objects.all().order_by('-id')[:5]
    purchases = PurchaseBill.objects.all().order_by('-id')[:5]

    return render(request, 'accounting/dashboard.html', {
        'summary': summary,
        'invoices': invoices,
        'purchases': purchases
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
