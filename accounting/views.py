from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.db.models import Sum
from decimal import Decimal
from datetime import datetime, timedelta
from .models import (
    Account, Customer, Supplier, Product, Invoice, PurchaseBill, 
    BankAccount, ReceiptVoucher, PaymentVoucher, JournalEntry, 
    JournalEntryLine, Company, Warehouse, WarehouseStock, StockTransfer, 
    UserProfile, BillOfMaterials, WorkOrder, SubscriptionPlan, CompanySubscription, PaymentTransaction
)
from .serializers import (
    AccountSerializer, CustomerSerializer, SupplierSerializer, ProductSerializer,
    InvoiceSerializer, PurchaseBillSerializer, BankAccountSerializer,
    ReceiptVoucherSerializer, PaymentVoucherSerializer, JournalEntrySerializer,
    WarehouseSerializer, WarehouseStockSerializer, StockTransferSerializer
)
from .zatca import generate_qr_image_base64

# --- Helper: Get Tenant/Company for current user ---
def get_user_company(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.company:
        return request.user.profile.company
    comp, _ = Company.objects.get_or_create(id=1, defaults={"name": "SECOND ADVANCE MEDICAL COMPANY (SAMCO)", "vat_number": "310122456700003"})
    return comp

# --- 🏢 SAAS REGISTRATION & COMPANY ONBOARDING ---
def company_signup_view(request):
    if request.method == 'POST':
        comp_name = request.POST.get('company_name', '').strip()
        vat_no = request.POST.get('vat_number', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not comp_name or not username or not password:
            return render(request, 'accounting/signup.html', {'error': 'Company Name, Username and Password are required!'})

        # ১. কোম্পানি তৈরি
        company = Company.objects.create(name=comp_name, vat_number=vat_no, phone=request.POST.get('phone', ''))

        # ২. ডিফল্ট চার্ট অফ অ্যাকাউন্টস তৈরি
        default_accounts = [
            ("1010", "Cash & Bank (الخزينة والبنوك)", "Asset"),
            ("1200", "Accounts Receivable (العملاء)", "Asset"),
            ("1300", "Inventory Asset (المخزون السلعي)", "Asset"),
            ("1400", "VAT Input Tax 15% (ضريبة المدخلات)", "Asset"),
            ("2000", "Accounts Payable (الموردين)", "Liability"),
            ("2100", "VAT Output Tax 15% (ضريبة المخرجات)", "Liability"),
            ("4000", "Sales Revenue (المبيعات)", "Revenue"),
            ("5000", "Cost of Goods Sold (تكلفة المبيعات)", "Expense"),
        ]
        for c_code, c_name, c_type in default_accounts:
            Account.objects.create(company=company, code=c_code, name=c_name, account_type=c_type)

        # ৩. ডিফল্ট ওয়্যারহাউজ ও ব্যাংক
        wh = Warehouse.objects.create(company=company, code="MAIN-01", name_en="Main Warehouse", name_ar="المستودع الرئيسي")
        BankAccount.objects.create(company=company, name="Al Rajhi Bank (مصرف الراجحي)", balance=0.00)

        # ৪. ইউজার তৈরি ও লিঙ্ক
        user = User.objects.create_user(username=username, email=email, password=password)
        user.profile.company = company
        user.profile.role = 'ADMIN'
        user.profile.save()

        # ৫. ১৪ দিনের ফ্রি ট্রায়াল সাবস্ক্রিপশন চালু
        default_plan, _ = SubscriptionPlan.objects.get_or_create(slug="pro", defaults={"name": "Professional Plan (باقة المحترفين)", "price_monthly_sar": 199.00})
        CompanySubscription.objects.create(
            company=company, plan=default_plan, status='TRIAL',
            start_date=datetime.now(), expiry_date=datetime.now() + timedelta(days=14)
        )

        login(request, user)
        return redirect('/pricing/')

    return render(request, 'accounting/signup.html')

# --- 💳 MADA / APPLE PAY SAUDI CHECKOUT VIEW ---
def pricing_checkout_view(request):
    company = get_user_company(request)
    plans = SubscriptionPlan.objects.all()
    if not plans.exists():
        SubscriptionPlan.objects.create(name="Basic Plan (باقة الأعمال)", slug="basic", price_monthly_sar=99.00, price_yearly_sar=999.00)
        SubscriptionPlan.objects.create(name="Enterprise Manufacturing (باقة المصانع)", slug="enterprise", price_monthly_sar=299.00, price_yearly_sar=2990.00)
        plans = SubscriptionPlan.objects.all()

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        pay_method = request.POST.get('payment_method', 'Mada')
        plan = get_object_or_404(SubscriptionPlan, pk=plan_id)

        # পেমেন্ট ট্রানজেকশন রেকর্ড ও সাবস্ক্রিপশন অ্যাক্টিভেট
        PaymentTransaction.objects.create(
            company=company, amount_sar=plan.price_monthly_sar,
            payment_method=pay_method, status='PAID'
        )

        sub, _ = CompanySubscription.objects.get_or_create(company=company)
        sub.plan = plan
        sub.status = 'ACTIVE'
        sub.start_date = datetime.now()
        sub.expiry_date = datetime.now() + timedelta(days=30)
        sub.save()

        return redirect('/')

    return render(request, 'accounting/pricing.html', {'company': company, 'plans': plans})


# --- 🌟 DASHBOARD VIEW (TENANT FILTERED) ---
def dashboard_view(request):
    lang = request.session.get('lang', 'en')
    is_ar = (lang == 'ar')
    lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)

    total_sales = sum(inv.total_amount for inv in Invoice.objects.filter(company=company))
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.filter(company=company))
    total_bank_balance = sum(b.balance for b in BankAccount.objects.filter(company=company))
    total_work_orders = WorkOrder.objects.filter(company=company).count()
    active_work_orders = WorkOrder.objects.filter(company=company, status='IN_PROGRESS').count()

    user_role = 'ADMIN'
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_role = request.user.profile.role

    summary = {
        "total_sales_sar": total_sales,
        "total_purchases_sar": total_purchases,
        "total_bank_balance_sar": total_bank_balance,
        "net_profit_sar": total_sales - total_purchases,
        "total_products": Product.objects.filter(company=company).count(),
        "total_customers": Customer.objects.filter(company=company).count(),
        "total_work_orders": total_work_orders,
        "active_work_orders": active_work_orders,
    }
    invoices = Invoice.objects.filter(company=company).order_by('-id')[:6]
    work_orders = WorkOrder.objects.filter(company=company).order_by('-id')[:6]
    warehouses = Warehouse.objects.filter(company=company).order_by('code')

    sub = CompanySubscription.objects.filter(company=company).first()

    return render(request, 'accounting/dashboard.html', {
        'company': company,
        'subscription': sub,
        'summary': summary,
        'invoices': invoices,
        'work_orders': work_orders,
        'warehouses': warehouses,
        'lang': lang,
        'is_ar': is_ar,
        'lang_dir': lang_dir,
        'user_role': user_role
    })

def set_language_view(request, lang):
    if lang in ['ar', 'en']: request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', '/'))

def manufacturing_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    work_orders = WorkOrder.objects.filter(company=company).order_by('-id')
    boms = BillOfMaterials.objects.filter(company=company).order_by('bom_code')
    tot_produced = sum(wo.actual_qty_produced for wo in work_orders.filter(status='COMPLETED'))
    tot_mfg_cost = sum(wo.total_batch_cost for wo in work_orders.filter(status='COMPLETED'))
    return render(request, 'accounting/manufacturing.html', {'company': company, 'work_orders': work_orders, 'boms': boms, 'tot_produced': tot_produced, 'tot_mfg_cost': tot_mfg_cost, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def scanner_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    return render(request, 'accounting/scanner.html', {'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def custom_reports_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    report_type = request.GET.get('report_type', 'sales')
    start_date = request.GET.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.GET.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    customer_id = request.GET.get('customer', ''); warehouse_id = request.GET.get('warehouse', '')
    data_rows = []; tot_amount = Decimal('0.00'); tot_vat = Decimal('0.00'); tot_grand = Decimal('0.00')

    customers = Customer.objects.filter(company=company).order_by('name')
    warehouses = Warehouse.objects.filter(company=company).order_by('name_en')

    if report_type == 'sales':
        invoices = Invoice.objects.filter(company=company, date__date__range=[start_date, end_date])
        if customer_id: invoices = invoices.filter(customer_id=customer_id)
        if warehouse_id: invoices = invoices.filter(warehouse_id=warehouse_id)
        for inv in invoices.order_by('-date'):
            tot_amount += inv.subtotal; tot_vat += inv.vat_amount; tot_grand += inv.total_amount
            data_rows.append({'col1': inv.invoice_no, 'col2': inv.customer.name, 'col3': inv.warehouse.name_en if inv.warehouse else 'General', 'col4': inv.date.strftime("%Y-%m-%d"), 'amount': inv.subtotal, 'vat': inv.vat_amount, 'total': inv.total_amount, 'link': f"/invoice/{inv.id}/"})
    elif report_type == 'purchases':
        bills = PurchaseBill.objects.filter(company=company, date__range=[start_date, end_date])
        if warehouse_id: bills = bills.filter(warehouse_id=warehouse_id)
        for b in bills.order_by('-date'):
            tot_amount += b.subtotal; tot_vat += b.vat_amount; tot_grand += b.total_amount
            data_rows.append({'col1': b.bill_no, 'col2': b.supplier.name, 'col3': b.warehouse.name_en if b.warehouse else 'General', 'col4': str(b.date), 'amount': b.subtotal, 'vat': b.vat_amount, 'total': b.total_amount, 'link': '#'})

    return render(request, 'accounting/custom_reports.html', {'company': company, 'report_type': report_type, 'start_date': start_date, 'end_date': end_date, 'customers': customers, 'warehouses': warehouses, 'selected_customer': customer_id, 'selected_warehouse': warehouse_id, 'data_rows': data_rows, 'tot_amount': tot_amount, 'tot_vat': tot_vat, 'tot_grand': tot_grand, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def reports_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    accounts = Account.objects.filter(company=company).order_by('code')
    trial_balance = []; tot_debit_all = Decimal('0.00'); tot_credit_all = Decimal('0.00')

    for acc in accounts:
        debit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
        credit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('credit'))['credit__sum'] or Decimal('0.00')
        net_balance = debit_sum - credit_sum
        tot_debit_all += debit_sum; tot_credit_all += credit_sum
        trial_balance.append({'code': acc.code, 'name': acc.name, 'type': acc.account_type, 'debit_total': debit_sum, 'credit_total': credit_sum, 'net_balance': net_balance})

    total_sales_revenue = sum(inv.subtotal for inv in Invoice.objects.filter(company=company))
    total_cogs = sum(bill.subtotal for bill in PurchaseBill.objects.filter(company=company))
    gross_profit = total_sales_revenue - total_cogs
    operating_expenses = JournalEntryLine.objects.filter(account__company=company, account__account_type='Expense').aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
    net_profit = gross_profit - operating_expenses

    total_bank_cash = sum(b.balance for b in BankAccount.objects.filter(company=company))
    accounts_receivable = sum(inv.total_amount for inv in Invoice.objects.filter(company=company)) - sum(rv.amount for rv in ReceiptVoucher.objects.filter(company=company))
    inventory_valuation = sum(p.current_stock * Decimal('15.00') for p in Product.objects.filter(company=company))
    vat_input_tax = sum(bill.vat_amount for bill in PurchaseBill.objects.filter(company=company))
    total_assets = total_bank_cash + max(Decimal('0.00'), accounts_receivable) + inventory_valuation + vat_input_tax

    accounts_payable = sum(bill.total_amount for bill in PurchaseBill.objects.filter(company=company)) - sum(pv.amount for pv in PaymentVoucher.objects.filter(company=company))
    vat_output_tax = sum(inv.vat_amount for inv in Invoice.objects.filter(company=company))
    total_liabilities = max(Decimal('0.00'), accounts_payable) + vat_output_tax
    total_equity = total_assets - total_liabilities

    vat_sales_subtotal = sum(inv.subtotal for inv in Invoice.objects.filter(company=company))
    vat_sales_tax = sum(inv.vat_amount for inv in Invoice.objects.filter(company=company))
    vat_purchase_subtotal = sum(bill.subtotal for bill in PurchaseBill.objects.filter(company=company))
    vat_purchase_tax = sum(bill.vat_amount for bill in PurchaseBill.objects.filter(company=company))
    net_vat_due = vat_sales_tax - vat_purchase_tax

    recent_ledger_entries = JournalEntryLine.objects.filter(account__company=company).select_related('journal_entry', 'account').order_by('-id')[:30]

    return render(request, 'accounting/reports.html', {
        'company': company, 'trial_balance': trial_balance, 'tot_debit_all': tot_debit_all, 'tot_credit_all': tot_credit_all,
        'pnl': {'revenue': total_sales_revenue, 'cogs': total_cogs, 'gross_profit': gross_profit, 'expenses': operating_expenses, 'net_profit': net_profit},
        'bs': {'bank_cash': total_bank_cash, 'ar': max(Decimal('0.00'), accounts_receivable), 'inventory': inventory_valuation, 'vat_input': vat_input_tax, 'total_assets': total_assets, 'ap': max(Decimal('0.00'), accounts_payable), 'vat_output': vat_output_tax, 'total_liabilities': total_liabilities, 'equity': total_equity},
        'vat': {'sales_base': vat_sales_subtotal, 'sales_vat': vat_sales_tax, 'pur_base': vat_purchase_subtotal, 'pur_vat': vat_purchase_tax, 'net_due': net_vat_due},
        'ledger_entries': recent_ledger_entries, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    comp = invoice.company or get_user_company(request)
    if not invoice.zatca_qr_b64:
        invoice.update_totals_and_post_accounting()
        invoice.refresh_from_db()
    qr_img = generate_qr_image_base64(invoice.zatca_qr_b64) if invoice.zatca_qr_b64 else ""
    return render(request, 'accounting/invoice_detail.html', {'invoice': invoice, 'company': comp, 'qr_image': qr_img})

def voucher_print_view(request, v_type, pk):
    comp = get_user_company(request)
    if v_type == 'receipt':
        voucher = get_object_or_404(ReceiptVoucher, pk=pk)
        title_en, title_ar, party_label, party_name = "RECEIPT VOUCHER", "سند قبض", "Received From / استلمنا من", voucher.customer.name
    else:
        voucher = get_object_or_404(PaymentVoucher, pk=pk)
        title_en, title_ar, party_label, party_name = "PAYMENT VOUCHER", "سند صرف", "Paid To / يصرف إلى", voucher.supplier.name if voucher.supplier else voucher.expense_reason or "Expense"
    return render(request, 'accounting/voucher_print.html', {'voucher': voucher, 'v_type': v_type, 'title_en': title_en, 'title_ar': title_ar, 'party_label': party_label, 'party_name': party_name, 'company': comp})

def transfer_slip_print_view(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    comp = transfer.company or get_user_company(request)
    qr_payload = f"STOCK TRANSFER\nSlip: {transfer.transfer_no}\nFrom: {transfer.source_warehouse.name_en}\nTo: {transfer.destination_warehouse.name_en}\nDate: {transfer.date}"
    qr_img = generate_qr_image_base64(qr_payload)
    return render(request, 'accounting/transfer_print.html', {'transfer': transfer, 'company': comp, 'qr_image': qr_img})

# API ViewSets
class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
class WarehouseStockViewSet(viewsets.ModelViewSet):
    queryset = WarehouseStock.objects.all()
    serializer_class = WarehouseStockSerializer
class StockTransferViewSet(viewsets.ModelViewSet):
    queryset = StockTransfer.objects.all()
    serializer_class = StockTransferSerializer
class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
class PurchaseBillViewSet(viewsets.ModelViewSet):
    queryset = PurchaseBill.objects.all()
    serializer_class = PurchaseBillSerializer
class ReceiptVoucherViewSet(viewsets.ModelViewSet):
    queryset = ReceiptVoucher.objects.all()
    serializer_class = ReceiptVoucherSerializer
class PaymentVoucherViewSet(viewsets.ModelViewSet):
    queryset = PaymentVoucher.objects.all()
    serializer_class = PaymentVoucherSerializer
class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer
