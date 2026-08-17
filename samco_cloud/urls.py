from django.contrib import admin
from django.urls import path, include
from accounting.views import dashboard_view, invoice_detail_view, voucher_print_view

urlpatterns = [
    path('', dashboard_view, name='home-dashboard'),
    path('invoice/<int:pk>/', invoice_detail_view, name='invoice-detail'),
    path('voucher/<str:v_type>/<int:pk>/', voucher_print_view, name='voucher-print'),
    path('admin/', admin.site.urls),
    path('api/', include('accounting.urls')),
]
