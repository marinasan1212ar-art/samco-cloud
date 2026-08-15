from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from .models import Account, Customer, Product, Invoice, JournalEntry
from .serializers import (
    AccountSerializer, CustomerSerializer, ProductSerializer,
    InvoiceSerializer, JournalEntrySerializer
)

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

# 🌐 ড্যাশবোর্ড রেন্ডার ভিউ (HTML Frontend)
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

# 📊 API Summary
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
