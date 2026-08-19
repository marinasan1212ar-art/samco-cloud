from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.db.models import Sum, Q
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta
import csv, io

from .models import (
    Account, Customer, Supplier, Product, Invoice, PurchaseBill, 
    BankAccount, ReceiptVoucher, PaymentVoucher, JournalEntry, 
    JournalEntryLine, Company, Warehouse, WarehouseStock, StockTransfer, 
    UserProfile, BillOfMaterials, WorkOrder, Employee, MonthlyPayroll, 
    PayrollItem, CostCenter, FixedAsset, StockAdjustment, CompanySettings,
    SubscriptionPlan, CompanySubscription, PaymentTransaction,
    CreditNote, CreditNoteItem, DeliveryNote, DeliveryNoteItem, ProductBatch,
    FundTransfer, BankStatement, BankStatementLine
)
from .serializers import (
    AccountSerializer, CustomerSerializer, SupplierSerializer, ProductSerializer,
    InvoiceSerializer, PurchaseBillSerializer, BankAccountSerializer,
    ReceiptVoucherSerializer, PaymentVoucherSerializer, JournalEntrySerializer,
    WarehouseSerializer, WarehouseStockSerializer, StockTransferSerializer
)
from .zatca import generate_qr_image_base64

def get_user_company(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.company:
        return request.user.profile.company
    comp, _ = Company.objects.get_or_create(id=1, defaults={"name": "SECOND ADVANCE MEDICAL COMPANY (SAMCO)", "vat_number": "310122456700003"})
    return comp

# --- 🌟 QUYOD ADVANCED DASHBOARD ---
def dashboard_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)

    total_sales = sum(inv.total_amount for inv in Invoice.objects.filter(company=company))
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.filter(company=company))
    total_bank_balance = sum(b.balance for b in BankAccount.objects.filter(company=company))

    # Overdue/Unpaid invoices and Low stock alerts
    overdue_invoices = Invoice.objects.filter(company=company, payment_status__in=['UNPAID', 'PARTIALLY_PAID']).order_by('-date')[:5]
    low_stock_products = Product.objects.filter(company=company, current_stock__lte=10).order_by('current_stock')[:5]

    summary = {
        "total_sales_sar": total_sales,
        "total_purchases_sar": total_purchases,
        "total_bank_balance_sar": total_bank_balance,
        "net_profit_sar": total_sales - total_purchases,
        "total_products": Product.objects.filter(company=company).count(),
        "total_customers": Customer.objects.filter(company=company).count(),
        "total_suppliers": Supplier.objects.filter(company=company).count(),
        "total_employees": Employee.objects.filter(company=company).count(),
        "total_work_orders": WorkOrder.objects.filter(company=company).count(),
    }
    invoices = Invoice.objects.filter(company=company).order_by('-id')[:6]
    purchases = PurchaseBill.objects.filter(company=company).order_by('-id')[:6]
    warehouses = Warehouse.objects.filter(company=company).order_by('code')

    user_role = 'ADMIN'
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_role = request.user.profile.role

    return render(request, 'accounting/dashboard.html', {
        'company': company, 'summary': summary, 'invoices': invoices,
        'purchases': purchases, 'warehouses': warehouses, 'lang': lang,
        'is_ar': is_ar, 'lang_dir': lang_dir, 'user_role': user_role,
        'overdue_invoices': overdue_invoices, 'low_stock_products': low_stock_products
    })

# --- 🏦 BANK RECONCILIATION & STATEMENT MATCHING ---
def bank_reconciliation_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    banks = BankAccount.objects.filter(company=company)
    selected_bank_id = request.GET.get('bank_id', banks.first().id if banks.exists() else None)
    selected_bank = BankAccount.objects.filter(id=selected_bank_id).first() if selected_bank_id else None

    # Handle Bank Statement CSV Upload
    if request.method == 'POST' and request.FILES.get('statement_file'):
        file = request.FILES['statement_file']
        bs = BankStatement.objects.create(company=company, bank_account=selected_bank, filename=file.name)
        
        decoded_file = file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.reader(io_string)
        
        for row in reader:
            if len(row) >= 3:
                try:
                    d_date = row[0].strip() or datetime.now().strftime("%Y-%m-%d")
                    desc = row[1].strip()
                    amt = Decimal(row[2].strip().replace(',', ''))
                    BankStatementLine.objects.create(
                        statement=bs, date=d_date, description=desc, amount=abs(amt),
                        transaction_type="CREDIT" if amt >= 0 else "DEBIT"
                    )
                except Exception:
                    continue
        return redirect(f'/banking/reconciliation/?bank_id={selected_bank.id}')

    # Handle Line Item Reconciliation Action
    if request.method == 'POST' and 'reconcile_line_id' in request.POST:
        line_id = request.POST.get('reconcile_line_id')
        line = get_object_or_404(BankStatementLine, id=line_id)
        line.is_reconciled = not line.is_reconciled
        line.save()
        return redirect(f'/banking/reconciliation/?bank_id={selected_bank.id}')

    statement_lines = BankStatementLine.objects.filter(statement__bank_account=selected_bank).order_by('-date') if selected_bank else []
    recent_receipts = ReceiptVoucher.objects.filter(bank_account=selected_bank).order_by('-date')[:10] if selected_bank else []
    recent_payments = PaymentVoucher.objects.filter(bank_account=selected_bank).order_by('-date')[:10] if selected_bank else []

    return render(request, 'accounting/bank_reconciliation.html', {
        'company': company, 'banks': banks, 'selected_bank': selected_bank,
        'statement_lines': statement_lines, 'receipts': recent_receipts,
        'payments': recent_payments, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

# --- 💸 FUND TRANSFER VIEW ---
def fund_transfer_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    banks = BankAccount.objects.filter(company=company)
    transfers = FundTransfer.objects.filter(company=company).order_by('-id')[:15]

    if request.method == 'POST':
        from_id = request.POST.get('from_account')
        to_id = request.POST.get('to_account')
        amount = Decimal(request.POST.get('amount', '0.00'))
        notes = request.POST.get('notes', 'Internal Fund Wire')

        if from_id != to_id and amount > 0:
            from_acc = get_object_or_404(BankAccount, id=from_id)
            to_acc = get_object_or_404(BankAccount, id=to_id)
            ft = FundTransfer.objects.create(
                company=company, transfer_no=f"FT-{int(datetime.now().timestamp())}",
                from_account=from_acc, to_account=to_acc, amount=amount, notes=notes
            )
            ft.post_accounting()
            return redirect('/banking/transfer/')

    return render(request, 'accounting/fund_transfer.html', {
        'company': company, 'banks': banks, 'transfers': transfers,
        'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    comp = invoice.company or get_user_company(request)
    if not invoice.zatca_qr_b64:
        invoice.update_totals_and_post_accounting()
        invoice.refresh_from_db()
    
    qr_img = generate_qr_image_base64(invoice.zatca_qr_b64) if invoice.zatca_qr_b64 else ""
    bank_accounts = BankAccount.objects.filter(company=comp)
    
    if request.method == 'POST' and 'record_payment' in request.POST:
        pay_amount = Decimal(request.POST.get('pay_amount', '0.00'))
        bank_id = request.POST.get('bank_id')
        pay_method = request.POST.get('payment_method', 'Bank Transfer')
        notes = request.POST.get('notes', f'Payment for Invoice #{invoice.invoice_no}')

        if pay_amount > 0 and bank_id:
            bank = get_object_or_404(BankAccount, id=bank_id)
            rv_no = f"RV-INV-{invoice.invoice_no}-{int(datetime.now().timestamp())}"
            rv = ReceiptVoucher.objects.create(
                company=comp, voucher_no=rv_no, customer=invoice.customer,
                invoice=invoice, bank_account=bank, amount=pay_amount,
                payment_method=pay_method, notes=notes
            )
            rv.post_accounting()
            return redirect('invoice-detail', pk=invoice.pk)

    return render(request, 'accounting/invoice_detail.html', {
        'invoice': invoice, 'company': comp, 'qr_image': qr_img,
        'bank_accounts': bank_accounts
    })

def delivery_note_detail_view(request, pk):
    delivery_note = get_object_or_404(DeliveryNote, pk=pk)
    comp = delivery_note.company or get_user_company(request)
    qr_payload = f"DELIVERY SLIP\nNo: {delivery_note.delivery_no}\nCustomer: {delivery_note.invoice.customer.name}\nDate: {delivery_note.date}\nDriver: {delivery_note.driver_name}"
    qr_img = generate_qr_image_base64(qr_payload)
    return render(request, 'accounting/delivery_note_detail.html', {
        'dn': delivery_note, 'company': comp, 'qr_image': qr_img
    })

def create_delivery_note_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    comp = invoice.company or get_user_company(request)
    warehouses = Warehouse.objects.filter(company=company)
    
    if request.method == 'POST':
        driver = request.POST.get('driver_name', '')
        vehicle = request.POST.get('vehicle_no', '')
        wh_id = request.POST.get('warehouse_id')
        warehouse = get_object_or_404(Warehouse, id=wh_id) if wh_id else invoice.warehouse or warehouses.first()
        dn_no = f"DN-{invoice.invoice_no}"
        
        dn = DeliveryNote.objects.create(
            company=comp, delivery_no=dn_no, invoice=invoice,
            warehouse=warehouse, driver_name=driver, vehicle_no=vehicle,
            status="DELIVERED"
        )
        for item in invoice.items.all():
            qty_del = int(request.POST.get(f'qty_{item.id}', item.qty))
            b_no = request.POST.get(f'batch_{item.id}', item.batch_no or 'BATCH-01')
            exp = request.POST.get(f'exp_{item.id}', item.expiry_date or '2028-12-31')
            DeliveryNoteItem.objects.create(
                delivery_note=dn, product=item.product, batch_no=b_no, expiry_date=exp, qty_delivered=qty_del
            )
        return redirect('delivery-note-detail', pk=dn.pk)

    return render(request, 'accounting/delivery_note_create.html', {
        'invoice': invoice, 'company': comp, 'warehouses': warehouses
    })

def credit_note_detail_view(request, pk):
    credit_note = get_object_or_404(CreditNote, pk=pk)
    comp = credit_note.company or get_user_company(request)
    if not credit_note.zatca_qr_b64:
        credit_note.update_totals_and_post_accounting()
        credit_note.refresh_from_db()
    qr_img = generate_qr_image_base64(credit_note.zatca_qr_b64) if credit_note.zatca_qr_b64 else ""
    return render(request, 'accounting/credit_note_detail.html', {
        'credit_note': credit_note, 'company': comp, 'qr_image': qr_img
    })

def create_credit_note_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    comp = invoice.company or get_user_company(request)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Customer Return (مرتجع بضاعة)')
        cn_no = f"CN-{invoice.invoice_no}"
        cn = CreditNote.objects.create(
            company=comp, credit_note_no=cn_no, invoice=invoice, reason=reason
        )
        for item in invoice.items.all():
            qty_return = int(request.POST.get(f'return_qty_{item.id}', 0))
            if qty_return > 0:
                CreditNoteItem.objects.create(
                    credit_note=cn, product=item.product, qty=qty_return, unit_price=item.unit_price
                )
        cn.update_totals_and_post_accounting()
        return redirect('credit-note-detail', pk=cn.pk)

    return render(request, 'accounting/credit_note_create.html', {
        'invoice': invoice, 'company': comp
    })

def company_signup_view(request):
    error = None
    if request.method == 'POST':
        comp_name = request.POST.get('company_name')
        vat_number = request.POST.get('vat_number', '300000000000003')
        phone = request.POST.get('phone', '')
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            error = "اسم المستخدم موجود بالفعل / Username already exists."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            company = Company.objects.create(name=comp_name, vat_number=vat_number, phone=phone)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.company = company
            profile.role = 'ADMIN'
            profile.save()

            default_plan, _ = SubscriptionPlan.objects.get_or_create(
                slug='standard-plan',
                defaults={'name': 'Standard Enterprise Plan', 'price_monthly_sar': Decimal('199.00')}
            )
            CompanySubscription.objects.create(company=company, plan=default_plan, status='ACTIVE')
            login(request, user)
            return redirect('/')

    return render(request, 'accounting/signup.html', {'error': error})

def pricing_checkout_view(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    company = get_user_company(request)
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        pay_method = request.POST.get('payment_method', 'Mada')
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        PaymentTransaction.objects.create(company=company, amount_sar=plan.price_monthly_sar, payment_method=pay_method, status='PAID')
        sub, _ = CompanySubscription.objects.get_or_create(company=company)
        sub.plan = plan
        sub.status = 'ACTIVE'
        sub.save()
        return redirect('/')
    return render(request, 'accounting/pricing.html', {'plans': plans, 'company': company})

def statement_of_account_view(request, party_type, pk):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    ledger_lines = []
    running_balance = Decimal('0.00')

    if party_type == 'customer':
        party = get_object_or_404(Customer, pk=pk)
        title_en, title_ar = "Customer Statement of Account", "كشف حساب عميل تفصيلي"
        invoices = Invoice.objects.filter(customer=party).order_by('date')
        receipts = ReceiptVoucher.objects.filter(customer=party).order_by('date')

        for inv in invoices:
            running_balance += inv.total_amount
            ledger_lines.append({
                'date': inv.date.strftime("%Y-%m-%d"), 'ref': f"Invoice #{inv.invoice_no}",
                'desc': f"Tax Sales Invoice ({inv.get_payment_status_display()})",
                'debit': inv.total_amount, 'credit': Decimal('0.00'), 'balance': running_balance
            })
        for rc in receipts:
            running_balance -= rc.amount
            ledger_lines.append({
                'date': str(rc.date), 'ref': f"Receipt #{rc.voucher_no}",
                'desc': f"Payment received via {rc.payment_method}",
                'debit': Decimal('0.00'), 'credit': rc.amount, 'balance': running_balance
            })
    else:
        party = get_object_or_404(Supplier, pk=pk)
        title_en, title_ar = "Supplier Statement of Account", "كشف حساب مورد تفصيلي"
        bills = PurchaseBill.objects.filter(supplier=party).order_by('date')
        payments = PaymentVoucher.objects.filter(supplier=party).order_by('date')

        for b in bills:
            running_balance += b.total_amount
            ledger_lines.append({
                'date': str(b.date), 'ref': f"Bill #{b.bill_no}",
                'desc': "Vendor Purchase Bill",
                'debit': Decimal('0.00'), 'credit': b.total_amount, 'balance': running_balance
            })
        for pv in payments:
            running_balance -= pv.amount
            ledger_lines.append({
                'date': str(pv.date), 'ref': f"Payment #{pv.voucher_no}",
                'desc': f"Settlement paid via {pv.payment_method}",
                'debit': pv.amount, 'credit': Decimal('0.00'), 'balance': running_balance
            })

    ledger_lines.sort(key=lambda x: x['date'])
    return render(request, 'accounting/statement.html', {
        'company': company, 'party': party, 'party_type': party_type,
        'title_en': title_en, 'title_ar': title_ar, 'ledger_lines': ledger_lines,
        'final_balance': running_balance, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def wps_sif_export_view(request, payroll_id):
    payroll = get_object_or_404(MonthlyPayroll, pk=payroll_id)
    company = get_user_company(request)
    sif_content = f"SCR|{company.cr_number or '1010445566'}|{company.name}|{payroll.processed_date.strftime('%Y%m%d')}|{payroll.month_year.replace('-','')}|{payroll.items.count()}|{payroll.total_amount:.2f}|SAR\n"
    for idx, item in enumerate(payroll.items.all(), 1):
        emp = item.employee
        sif_content += f"EDR|{emp.iqama_no}|{emp.bank_iban}|{emp.name_en}|{item.basic_salary:.2f}|{item.housing:.2f}|{item.transport:.2f}|{item.deductions:.2f}|{item.net_salary:.2f}|SAR\n"
    response = HttpResponse(sif_content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="WPS_SIF_{company.cr_number}_{payroll.month_year}.sif"'
    return response

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

class WarehouseViewSet(viewsets.ModelViewSet): queryset = Warehouse.objects.all(); serializer_class = WarehouseSerializer
class WarehouseStockViewSet(viewsets.ModelViewSet): queryset = WarehouseStock.objects.all(); serializer_class = WarehouseStockSerializer
class StockTransferViewSet(viewsets.ModelViewSet): queryset = StockTransfer.objects.all(); serializer_class = StockTransferSerializer
class AccountViewSet(viewsets.ModelViewSet): queryset = Account.objects.all(); serializer_class = AccountSerializer
class BankAccountViewSet(viewsets.ModelViewSet): queryset = BankAccount.objects.all(); serializer_class = BankAccountSerializer
class CustomerViewSet(viewsets.ModelViewSet): queryset = Customer.objects.all(); serializer_class = CustomerSerializer
class SupplierViewSet(viewsets.ModelViewSet): queryset = Supplier.objects.all(); serializer_class = SupplierSerializer
class ProductViewSet(viewsets.ModelViewSet): queryset = Product.objects.all(); serializer_class = ProductSerializer
class InvoiceViewSet(viewsets.ModelViewSet): queryset = Invoice.objects.all(); serializer_class = InvoiceSerializer
class PurchaseBillViewSet(viewsets.ModelViewSet): queryset = PurchaseBill.objects.all(); serializer_class = PurchaseBillSerializer
class ReceiptVoucherViewSet(viewsets.ModelViewSet): queryset = ReceiptVoucher.objects.all(); serializer_class = ReceiptVoucherSerializer
class PaymentVoucherViewSet(viewsets.ModelViewSet): queryset = PaymentVoucher.objects.all(); serializer_class = PaymentVoucherSerializer
class JournalEntryViewSet(viewsets.ModelViewSet): queryset = JournalEntry.objects.all(); serializer_class = JournalEntrySerializer
