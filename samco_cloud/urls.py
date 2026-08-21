from django.contrib import admin
from django.urls import path
from accounting.views import (
    home_dashboard_view,
    invoices_list_view,
    create_invoice_view,
    invoice_detail_view,
    financial_reports_view,
    banking_transfer_view,
    division_hub_view,
    super_admin_hub_view,
    settings_page_view,
    vat_return_view,
    aging_report_view,
    price_list_view,
    recurring_invoice_view,
    statement_of_account_view,
    ocr_scanner_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_dashboard_view, name='home-dashboard'),
    
    # Invoices & Billing
    path('invoices/', invoices_list_view, name='invoices-list'),
    path('invoices/create/', create_invoice_view, name='create-invoice'),
    path('invoice/<int:pk>/', invoice_detail_view, name='invoice-detail'),
    
    # Financial Reports & Banking
    path('reports/', financial_reports_view, name='financial-reports'),
    path('banking/transfer/', banking_transfer_view, name='banking-transfer'),
    
    # 5 Divisions & Super Admin
    path('division/<str:dept>/', division_hub_view, name='division-hub'),
    path('super-admin/', super_admin_hub_view, name='super-admin-hub'),
    path('settings/', settings_page_view, name='settings-page'),
    
    # Compliance
    path('vat/', vat_return_view, name='vat-return'),
    path('reports/aging/', aging_report_view, name='aging-report'),
    path('sales/price-lists/', price_list_view, name='price-lists'),
    path('sales/recurring/', recurring_invoice_view, name='recurring-invoices'),
    path('statement/<str:party_type>/<int:pk>/', statement_of_account_view, name='statement-of-account'),
    path('statement/', statement_of_account_view, name='statement-default'),
    path('scanner/', ocr_scanner_view, name='ocr-scanner'),
]
