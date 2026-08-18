from django.contrib import admin
from django.urls import path, include
from accounting.views import (
    dashboard_view, invoice_detail_view, voucher_print_view, 
    reports_view, transfer_slip_print_view, set_language_view,
    custom_reports_view
)

urlpatterns = [
    path('', dashboard_view, name='home-dashboard'),
    path('set-language/<str:lang>/', set_language_view, name='set-language'),
    path('reports/', reports_view, name='financial-reports'),
    path('custom-reports/', custom_reports_view, name='custom-reports'),
    path('invoice/<int:pk>/', invoice_detail_view, name='invoice-detail'),
    path('voucher/<str:v_type>/<int:pk>/', voucher_print_view, name='voucher-print'),
    path('transfer/<int:pk>/', transfer_slip_print_view, name='transfer-slip-print'),
    path('admin/', admin.site.urls),
    path('api/', include('accounting.urls')),
]
