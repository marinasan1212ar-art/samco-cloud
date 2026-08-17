from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccountViewSet, CustomerViewSet, SupplierViewSet, ProductViewSet,
    InvoiceViewSet, PurchaseBillViewSet, BankAccountViewSet,
    ReceiptVoucherViewSet, PaymentVoucherViewSet, JournalEntryViewSet
)

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'banks', BankAccountViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'products', ProductViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'purchases', PurchaseBillViewSet)
router.register(r'receipt-vouchers', ReceiptVoucherViewSet)
router.register(r'payment-vouchers', PaymentVoucherViewSet)
router.register(r'journal-entries', JournalEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
