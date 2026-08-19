from django.contrib import admin
from django.urls import path, include
from accounting.views import (
    dashboard_view, invoice_detail_view, voucher_print_view, 
    reports_view, transfer_slip_print_view, set_language_view,
    custom_reports_view, manufacturing_view, scanner_view,
    company_signup_view, pricing_checkout_view, statement_of_account_view, wps_sif_export_view,
    credit_note_detail_view, create_credit_note_view
)
from accounting.pos_views import pos_dashboard, pos_checkout, pos_receipt_print

urlpatterns = [
    path('', dashboard_view, name='home-dashboard'),
    path('pos/', pos_dashboard, name='pos-dashboard'),
    path('pos/checkout/', pos_checkout, name='pos-checkout'),
    path('pos/receipt/<int:pk>/', pos_receipt_print, name='pos-receipt'),
    path('signup/', company_signup_view, name='saas-signup'),
    path('pricing/', pricing_checkout_view, name='saas-pricing'),
    path('manufacturing/', manufacturing_view, name='manufacturing-hub'),
    path('scanner/', scanner_view, name='mobile-scanner'),
    path('set-language/<str:lang>/', set_language_view, name='set-language'),
    path('reports/', reports_view, name='financial-reports'),
    path('custom-reports/', custom_reports_view, name='custom-reports'),
    path('statement/<str:party_type>/<int:pk>/', statement_of_account_view, name='statement-of-account'),
    path('wps-export/<int:payroll_id>/', wps_sif_export_view, name='wps-sif-export'),
    path('invoice/<int:pk>/', invoice_detail_view, name='invoice-detail'),
    path('credit-note/<int:pk>/', credit_note_detail_view, name='credit-note-detail'),
    path('invoice/<int:invoice_id>/return/', create_credit_note_view, name='create-credit-note'),
    path('voucher/<str:v_type>/<int:pk>/', voucher_print_view, name='voucher-print'),
    path('transfer/<int:pk>/', transfer_slip_print_view, name='transfer-slip-print'),
    path('admin/', admin.site.urls),
    path('api/', include('accounting.urls')),
]
