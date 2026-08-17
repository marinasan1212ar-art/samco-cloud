from rest_framework import serializers
from .models import Account, Customer, Supplier, Product, Invoice, InvoiceItem, PurchaseBill, PurchaseBillItem, JournalEntry, JournalEntryLine

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class PurchaseBillItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = PurchaseBillItem
        fields = ['id', 'product', 'product_name', 'qty', 'unit_cost', 'total']

class PurchaseBillSerializer(serializers.ModelSerializer):
    items = PurchaseBillItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    class Meta:
        model = PurchaseBill
        fields = ['id', 'bill_no', 'supplier', 'supplier_name', 'date', 'subtotal', 'vat_amount', 'total_amount', 'items']

class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = InvoiceItem
        fields = ['id', 'product', 'product_name', 'qty', 'unit_price', 'total']

class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    class Meta:
        model = Invoice
        fields = ['id', 'invoice_no', 'customer', 'customer_name', 'date', 'subtotal', 'vat_amount', 'total_amount', 'items']

class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    class Meta:
        model = JournalEntryLine
        fields = ['id', 'account', 'account_name', 'description', 'debit', 'credit']

class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    class Meta:
        model = JournalEntry
        fields = ['id', 'reference_no', 'date', 'description', 'lines']
