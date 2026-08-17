from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from .models import Account, Customer, Product, Invoice, JournalEntry, CompanySettings
from .serializers import (
    AccountSerializer, CustomerSerializer, ProductSerializer,
    InvoiceSerializer, JournalEntrySerializer
)
from .zatca import generate_qr_image_base64

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('code')
    serializer_class = AccountSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('-id')
    serializer_class = CustomerSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('cat_no')
    serializer_class = ProductSerializer

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-id')
    serializer_class = InvoiceSerializer

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all().order_by('-id')
    serializer_class = JournalEntrySerializer

def dashboard_view(request):
    total_sales = sum(inv.total_amount for inv in Invoice.objects.all())
    total_vat = sum(inv.vat_amount for inv in Invoice.objects.all())
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()

    summary = {
        "total_sales_sar": total_sales,
        "total_vat_sar": total_vat,
        "total_products": total_products,
        "total_customers": total_customers,
    }
    invoices = Invoice.objects.all().order_by('-id')[:10]

    return render(request, 'accounting/dashboard.html', {
        'summary': summary,
        'invoices': invoices
    })

def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    company, _ = CompanySettings.objects.get_or_create(id=1)
    
    # কিউআর কোড না থাকলে অটো-জেনারেট করা
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

class FinancialSummaryAPIView(APIView):
    def get(self, request):
        total_sales = sum(inv.total_amount for inv in Invoice.objects.all())
        total_vat = sum(inv.vat_amount for inv in Invoice.objects.all())
        return Response({
            "total_sales_sar": total_sales,
            "total_vat_sar": total_vat,
            "total_products": Product.objects.count(),
            "total_customers": Customer.objects.count(),
            "currency": "SAR",
            "system_status": "ZATCA Phase-2 Ready 🟢"
        })
