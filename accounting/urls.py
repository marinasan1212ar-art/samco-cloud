from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccountViewSet, CustomerViewSet, ProductViewSet,
    InvoiceViewSet, JournalEntryViewSet, FinancialSummaryAPIView,
    invoice_detail_view
)

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'products', ProductViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'journal-entries', JournalEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('summary/', FinancialSummaryAPIView.as_view(), name='financial-summary'),
    path('invoice/<int:pk>/', invoice_detail_view, name='api-invoice-detail'),
]
