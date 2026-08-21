from django.contrib import admin
from django.urls import path
from accounting.views import (
    home_dashboard_view,
    division_hub_view,
    super_admin_hub_view,
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
    
    # 5 Divisions Dedicated Web Workspaces
    path('division/<str:dept>/', division_hub_view, name='division-hub'),
    
    # Super Admin Command Center
    path('super-admin/', super_admin_hub_view, name='super-admin-hub'),
    
    # Compliance & Accounting Hubs
    path('vat/', vat_return_view, name='vat-return'),
    path('reports/aging/', aging_report_view, name='aging-report'),
    path('sales/price-lists/', price_list_view, name='price-lists'),
    path('sales/recurring/', recurring_invoice_view, name='recurring-invoices'),
    path('statement/<str:party_type>/<int:pk>/', statement_of_account_view, name='statement-of-account'),
    path('statement/', statement_of_account_view, name='statement-default'),
    path('scanner/', ocr_scanner_view, name='ocr-scanner'),
]
