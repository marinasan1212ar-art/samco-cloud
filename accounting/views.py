from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import datetime, timedelta
from .models import (
    Account, Customer, Supplier, Product, Invoice, PurchaseBill, 
    BankAccount, ReceiptVoucher, PaymentVoucher, JournalEntry, 
    JournalEntryLine, CompanySettings, Warehouse, WarehouseStock, StockTransfer, UserProfile
)
from .serializers import (
    AccountSerializer, CustomerSerializer, SupplierSerializer, ProductSerializer,
    InvoiceSerializer, PurchaseBillSerializer, BankAccountSerializer,
    ReceiptVoucherSerializer, PaymentVoucherSerializer, JournalEntrySerializer,
    WarehouseSerializer, WarehouseStockSerializer, StockTransferSerializer
)
from .zatca import generate_qr_image_base64

# --- API ViewSets ---
class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by('code')
    serializer_class = WarehouseSerializer

class WarehouseStockViewSet(viewsets.ModelViewSet):
    queryset = WarehouseStock.objects.all().order_by('warehouse')
    serializer_class = WarehouseStockSerializer

class StockTransferViewSet(viewsets.ModelViewSet):
    queryset = StockTransfer.objects.all().order_by('-id')
    serializer_class = StockTransferSerializer

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('code')
    serializer_class = AccountSerializer

class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all().order_by('name')
    serializer_class = BankAccountSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('-id')
    serializer_class = CustomerSerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('-id')
    serializer_class = SupplierSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('cat_no')
    serializer_class = ProductSerializer

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-id')
    serializer_class = InvoiceSerializer

class PurchaseBillViewSet(viewsets.ModelViewSet):
    queryset = PurchaseBill.objects.all().order_by('-id')
    serializer_class = PurchaseBillSerializer

class ReceiptVoucherViewSet(viewsets.ModelViewSet):
    queryset = ReceiptVoucher.objects.all().order_by('-id')
    serializer_class = ReceiptVoucherSerializer

class PaymentVoucherViewSet(viewsets.ModelViewSet):
    queryset = PaymentVoucher.objects.all().order_by('-id')
    serializer_class = PaymentVoucherSerializer

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all().order_by('-id')
    serializer_class = JournalEntrySerializer

# 🌐 Language Switcher
def set_language_view(request, lang):
    if lang in ['ar', 'en']:
        request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', '/'))

# --- 🌟 QUYOD A-TO-Z DASHBOARD VIEW ---
def dashboard_view(request):
    lang = request.session.get('lang', 'en')
    is_ar = (lang == 'ar')
    lang_dir = 'rtl' if is_ar else 'ltr'

    # Ensure 5 divisions exist
    default_divisions = [
        ("WH-01", "Warehouse Division", "المستودع الرئيسي"),
        ("MED-02", "Media Division", "قسم الميديا"),
        ("COS-03", "Cosmetic Division", "قسم التجميل"),
        ("POW-04", "Powder Division", "قسم البودرة"),
        ("PLA-05", "Plastic Division", "قسم البلاستيك")
    ]
    for code, en, ar in default_divisions:
        Warehouse.objects.get_or_create(code=code, defaults={"name_en": en, "name_ar": ar})

    total_sales = sum(inv.total_amount for inv in Invoice.objects.all())
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.all())
    total_bank_balance = sum(b.balance for b in BankAccount.objects.all())
    total_vat_sales = sum(inv.vat_amount for inv in Invoice.objects.all())
    total_vat_purchase = sum(bill.vat_amount for bill in PurchaseBill.objects.all())

    user_role = 'ADMIN'
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_role = request.user.profile.role

    summary = {
        "total_sales_sar": total_sales,
        "total_purchases_sar": total_purchases,
        "total_bank_balance_sar": total_bank_balance,
        "net_vat_due_sar": total_vat_sales - total_vat_purchase,
        "net_profit_sar": total_sales - total_purchases,
        "total_products": Product.objects.count(),
        "total_customers": Customer.objects.count(),
        "total_suppliers": Supplier.objects.count(),
        "total_warehouses": Warehouse.objects.count(),
    }
    invoices = Invoice.objects.all().order_by('-id')[:8]
    purchases = PurchaseBill.objects.all().order_by('-id')[:8]
    transfers = StockTransfer.objects.all().order_by('-id')[:6]
    warehouses = Warehouse.objects.all().order_by('code')

    return render(request, 'accounting/dashboard.html', {
        'summary': summary,
        'invoices': invoices,
        'purchases': purchases,
        'transfers': transfers,
        'warehouses': warehouses,
        'lang': lang,
        'is_ar': is_ar,
        'lang_dir': lang_dir,
        'user_role': user_role
    })

# --- 📱 DYNAMIC MOBILE & DESKTOP CUSTOM REPORT ENGINE ---
def custom_reports_view(request):
    lang = request.session.get('lang', 'en')
    is_ar = (lang == 'ar')
    lang_dir = 'rtl' if is_ar else 'ltr'
    company, _ = CompanySettings.objects.get_or_create(id=1)

    # Filters from GET request
    report_type = request.GET.get('report_type', 'sales')
    start_date = request.GET.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.GET.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    customer_id = request.GET.get('customer', '')
    warehouse_id = request.GET.get('warehouse', '')

    data_rows = []
    tot_amount = Decimal('0.00')
    tot_vat = Decimal('0.00')
    tot_grand = Decimal('0.00')

    customers = Customer.objects.all().order_by('name')
    warehouses = Warehouse.objects.all().order_by('name_en')

    if report_type == 'sales':
        invoices = Invoice.objects.filter(date__date__range=[start_date, end_date])
        if customer_id:
            invoices = invoices.filter(customer_id=customer_id)
        if warehouse_id:
            invoices = invoices.filter(warehouse_id=warehouse_id)

        for inv in invoices.order_by('-date'):
            tot_amount += inv.subtotal
            tot_vat += inv.vat_amount
            tot_grand += inv.total_amount
            data_rows.append({
                'col1': inv.invoice_no,
                'col2': inv.customer.name,
                'col3': inv.warehouse.name_en if inv.warehouse else 'General',
                'col4': inv.date.strftime("%Y-%m-%d"),
                'amount': inv.subtotal,
                'vat': inv.vat_amount,
                'total': inv.total_amount,
                'link': f"/invoice/{inv.id}/"
            })

    elif report_type == 'purchases':
        bills = PurchaseBill.objects.filter(date__range=[start_date, end_date])
        if warehouse_id:
            bills = bills.filter(warehouse_id=warehouse_id)

        for b in bills.order_by('-date'):
            tot_amount += b.subtotal
            tot_vat += b.vat_amount
            tot_grand += b.total_amount
            data_rows.append({
                'col1': b.bill_no,
                'col2': b.supplier.name,
                'col3': b.warehouse.name_en if b.warehouse else 'General',
                'col4': str(b.date),
                'amount': b.subtotal,
                'vat': b.vat_amount,
                'total': b.total_amount,
                'link': '#'
            })

    elif report_type == 'transfers':
        trans = StockTransfer.objects.filter(date__range=[start_date, end_date])
        for t in trans.order_by('-date'):
            item_count = sum(i.qty for i in t.items.all())
            tot_grand += item_count
            data_rows.append({
                'col1': t.transfer_no,
                'col2': f"{t.source_warehouse.name_en} ➔ {t.destination_warehouse.name_en}",
                'col3': t.status,
                'col4': str(t.date),
                'amount': Decimal(item_count),
                'vat': Decimal('0.00'),
                'total': Decimal(item_count),
                'link': f"/transfer/{t.id}/"
            })

    return render(request, 'accounting/custom_reports.html', {
        'company': company,
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'customers': customers,
        'warehouses': warehouses,
        'selected_customer': customer_id,
        'selected_warehouse': warehouse_id,
        'data_rows': data_rows,
        'tot_amount': tot_amount,
        'tot_vat': tot_vat,
        'tot_grand': tot_grand,
        'lang': lang,
        'is_ar': is_ar,
        'lang_dir': lang_dir,
    })

# --- Standard Reports View ---
def reports_view(request):
    lang = request.session.get('lang', 'en')
    is_ar = (lang == 'ar')
    lang_dir = 'rtl' if is_ar else 'ltr'

    company, _ = CompanySettings.objects.get_or_create(id=1)
    accounts = Account.objects.all().order_by('code')
    trial_balance = []
    tot_debit_all = Decimal('0.00')
    tot_credit_all = Decimal('0.00')

    for acc in accounts:
        debit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
        credit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('credit'))['credit__sum'] or Decimal('0.00')
        net_balance = debit_sum - credit_sum
        tot_debit_all += debit_sum
        tot_credit_all += credit_sum
        trial_balance.append({
            'code': acc.code, 'name': acc.name, 'type': acc.account_type,
            'debit_total': debit_sum, 'credit_total': credit_sum, 'net_balance': net_balance
        })

    total_sales_revenue = sum(inv.subtotal for inv in Invoice.objects.all())
    total_cogs = sum(bill.subtotal for bill in PurchaseBill.objects.all())
    gross_profit = total_sales_revenue - total_cogs
    operating_expenses = JournalEntryLine.objects.filter(account__account_type='Expense').aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
    net_profit = gross_profit - operating_expenses

    total_bank_cash = sum(b.balance for b in BankAccount.objects.all())
    accounts_receivable = sum(inv.total_amount for inv in Invoice.objects.all()) - sum(rv.amount for rv in ReceiptVoucher.objects.all())
    inventory_valuation = sum(p.current_stock * Decimal('15.00') for p in Product.objects.all())
    vat_input_tax = sum(bill.vat_amount for bill in PurchaseBill.objects.all())
    total_assets = total_bank_cash + max(Decimal('0.00'), accounts_receivable) + inventory_valuation + vat_input_tax

    accounts_payable = sum(bill.total_amount for bill in PurchaseBill.objects.all()) - sum(pv.amount for pv in PaymentVoucher.objects.all())
    vat_output_tax = sum(inv.vat_amount for inv in Invoice.objects.all())
    total_liabilities = max(Decimal('0.00'), accounts_payable) + vat_output_tax
    total_equity = total_assets - total_liabilities

    vat_sales_subtotal = sum(inv.subtotal for inv in Invoice.objects.all())
    vat_sales_tax = sum(inv.vat_amount for inv in Invoice.objects.all())
    vat_purchase_subtotal = sum(bill.subtotal for bill in PurchaseBill.objects.all())
    vat_purchase_tax = sum(bill.vat_amount for bill in PurchaseBill.objects.all())
    net_vat_due = vat_sales_tax - vat_purchase_tax

    recent_ledger_entries = JournalEntryLine.objects.select_related('journal_entry', 'account').order_by('-id')[:30]

    return render(request, 'accounting/reports.html', {
        'company': company,
        'trial_balance': trial_balance,
        'tot_debit_all': tot_debit_all,
        'tot_credit_all': tot_credit_all,
        'pnl': {'revenue': total_sales_revenue, 'cogs': total_cogs, 'gross_profit': gross_profit, 'expenses': operating_expenses, 'net_profit': net_profit},
        'bs': {'bank_cash': total_bank_cash, 'ar': max(Decimal('0.00'), accounts_receivable), 'inventory': inventory_valuation, 'vat_input': vat_input_tax, 'total_assets': total_assets, 'ap': max(Decimal('0.00'), accounts_payable), 'vat_output': vat_output_tax, 'total_liabilities': total_liabilities, 'equity': total_equity},
        'vat': {'sales_base': vat_sales_subtotal, 'sales_vat': vat_sales_tax, 'pur_base': vat_purchase_subtotal, 'pur_vat': vat_purchase_tax, 'net_due': net_vat_due},
        'ledger_entries': recent_ledger_entries,
        'lang': lang,
        'is_ar': is_ar,
        'lang_dir': lang_dir
    })

# --- Views for Printing ---
def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if not invoice.zatca_qr_b64:
        invoice.update_totals_and_post_accounting()
        invoice.refresh_from_db()

    qr_img = ""
    if invoice.zatca_qr_b64:
        qr_img = generate_qr_image_base64(invoice.zatca_qr_b64)

    return render(request, 'accounting/invoice_detail.html', {
        'invoice': invoice, 'company': company, 'qr_image': qr_img
    })

def voucher_print_view(request, v_type, pk):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if v_type == 'receipt':
        voucher = get_object_or_404(ReceiptVoucher, pk=pk)
        title_en, title_ar, party_label = "RECEIPT VOUCHER", "سند قبض", "Received From / استلمنا من"
        party_name = voucher.customer.name
    else:
        voucher = get_object_or_404(PaymentVoucher, pk=pk)
        title_en, title_ar, party_label = "PAYMENT VOUCHER", "سند صرف", "Paid To / يصرف إلى"
        party_name = voucher.supplier.name if voucher.supplier else voucher.expense_reason or "Expense"

    return render(request, 'accounting/voucher_print.html', {
        'voucher': voucher, 'v_type': v_type, 'title_en': title_en,
        'title_ar': title_ar, 'party_label': party_label, 'party_name': party_name, 'company': company
    })

def transfer_slip_print_view(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    company, _ = CompanySettings.objects.get_or_create(id=1)
    qr_payload = f"SAMCO STOCK TRANSFER\nSlip: {transfer.transfer_no}\nFrom: {transfer.source_warehouse.name_en}\nTo: {transfer.destination_warehouse.name_en}\nDate: {transfer.date}\nStatus: {transfer.status}"
    qr_img = generate_qr_image_base64(qr_payload)

    return render(request, 'accounting/transfer_print.html', {
        'transfer': transfer, 'company': company, 'qr_image': qr_img
    })
