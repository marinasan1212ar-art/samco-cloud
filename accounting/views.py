from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta
import csv, io

from .models import *
from .serializers import *
from .zatca import generate_qr_image_base64

def get_user_company(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.company:
        return request.user.profile.company
    comp, _ = Company.objects.get_or_create(id=1, defaults={"name": "SECOND ADVANCE MEDICAL COMPANY (SAMCO)", "vat_number": "310122456700003"})
    return comp

def dashboard_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    total_sales = sum(inv.total_amount for inv in Invoice.objects.filter(company=company))
    total_purchases = sum(bill.total_amount for bill in PurchaseBill.objects.filter(company=company)) + sum(exp.total_amount for exp in DirectExpense.objects.filter(company=company))
    total_bank_balance = sum(b.balance for b in BankAccount.objects.filter(company=company))
    overdue_invoices = Invoice.objects.filter(company=company, payment_status__in=['UNPAID', 'PARTIALLY_PAID']).order_by('-date')[:5]
    low_stock_products = Product.objects.filter(company=company, current_stock__lte=10).order_by('current_stock')[:5]

    summary = {
        "total_sales_sar": total_sales, "total_purchases_sar": total_purchases, "total_bank_balance_sar": total_bank_balance,
        "net_profit_sar": total_sales - total_purchases, "total_products": Product.objects.filter(company=company).count(),
        "total_customers": Customer.objects.filter(company=company).count(), "total_suppliers": Supplier.objects.filter(company=company).count(),
        "total_employees": Employee.objects.filter(company=company).count(), "total_work_orders": WorkOrder.objects.filter(company=company).count(),
    }
    invoices = Invoice.objects.filter(company=company).order_by('-id')[:6]
    purchases = PurchaseBill.objects.filter(company=company).order_by('-id')[:6]
    warehouses = Warehouse.objects.filter(company=company).order_by('code')
    user_role = request.user.profile.role if request.user.is_authenticated and hasattr(request.user, 'profile') else 'ADMIN'

    return render(request, 'accounting/dashboard.html', {
        'company': company, 'summary': summary, 'invoices': invoices, 'purchases': purchases,
        'warehouses': warehouses, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir, 'user_role': user_role,
        'overdue_invoices': overdue_invoices, 'low_stock_products': low_stock_products
    })

def invoices_list_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    status_filter = request.GET.get('status', '')
    invoices = Invoice.objects.filter(company=company).order_by('-id')
    if status_filter: invoices = invoices.filter(payment_status=status_filter)
    return render(request, 'accounting/invoices_list.html', {
        'company': company, 'invoices': invoices, 'status_filter': status_filter,
        'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def create_invoice_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    customers = Customer.objects.filter(company=company).order_by('-id')
    warehouses = Warehouse.objects.filter(company=company)
    products = Product.objects.filter(company=company)

    if request.method == 'POST' and 'create_quick_customer' in request.POST:
        new_cust = Customer.objects.create(
            company=company, name=request.POST.get('c_name'), name_ar=request.POST.get('c_name_ar', ''),
            vat_number=request.POST.get('c_vat_number', ''), cr_number=request.POST.get('c_cr_number', ''),
            phone=request.POST.get('c_phone', ''), address=request.POST.get('c_address', 'Saudi Arabia')
        )
        return redirect('/invoices/create/')

    if request.method == 'POST' and 'create_invoice' in request.POST:
        cust = get_object_or_404(Customer, id=request.POST.get('customer_id'))
        wh_id = request.POST.get('warehouse_id')
        wh = get_object_or_404(Warehouse, id=wh_id) if wh_id else warehouses.first()
        issue_date = request.POST.get('issue_date') or datetime.now().strftime("%Y-%m-%d")
        supply_date = request.POST.get('supply_date') or issue_date
        due_date = request.POST.get('due_date') or issue_date
        discount_amount = Decimal(request.POST.get('discount_amount', '0.00'))

        invoice = Invoice.objects.create(
            company=company, invoice_no=f"INV-{int(datetime.now().timestamp())}", customer=cust, warehouse=wh,
            date=datetime.strptime(issue_date, "%Y-%m-%d"), supply_date=datetime.strptime(supply_date, "%Y-%m-%d"),
            due_date=datetime.strptime(due_date, "%Y-%m-%d"), discount_amount=discount_amount,
            notes=request.POST.get('notes', ''), invoice_type='Tax Invoice (فاتورة ضريبية)'
        )

        prod_ids = request.POST.getlist('product_id[]')
        descriptions = request.POST.getlist('description[]')
        qtys = request.POST.getlist('qty[]')
        prices = request.POST.getlist('price[]')
        discounts = request.POST.getlist('discount_pct[]')

        for p_id, desc, q_val, pr_val, d_val in zip(prod_ids, descriptions, qtys, prices, discounts):
            if p_id and q_val and pr_val:
                prod = get_object_or_404(Product, id=p_id)
                InvoiceItem.objects.create(
                    invoice=invoice, product=prod, description=desc,
                    qty=int(q_val), unit_price=Decimal(pr_val), discount_pct=Decimal(d_val or 0)
                )

        invoice.update_totals_and_post_accounting()
        return redirect('invoice-detail', pk=invoice.pk)

    return render(request, 'accounting/invoice_create.html', {
        'company': company, 'customers': customers, 'warehouses': warehouses,
        'products': products, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir,
        'today': datetime.now().strftime("%Y-%m-%d")
    })

# 🌟 PRICING & AUTO-SEED PLANS (Fixed)
def pricing_checkout_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    
    plans = SubscriptionPlan.objects.filter(is_active=True)
    if not plans.exists():
        SubscriptionPlan.objects.get_or_create(slug='basic', defaults={'name': 'Basic Plan (باقة البداية)', 'price_monthly_sar': Decimal('99.00'), 'price_yearly_sar': Decimal('999.00'), 'max_users': 2})
        SubscriptionPlan.objects.get_or_create(slug='pro', defaults={'name': 'Qoyod Pro (باقة الأعمال المتقدمة)', 'price_monthly_sar': Decimal('199.00'), 'price_yearly_sar': Decimal('1990.00'), 'max_users': 5})
        SubscriptionPlan.objects.get_or_create(slug='enterprise', defaults={'name': 'Enterprise Plan (باقة المؤسسات الكبرى)', 'price_monthly_sar': Decimal('399.00'), 'price_yearly_sar': Decimal('3990.00'), 'max_users': 20})
        plans = SubscriptionPlan.objects.filter(is_active=True)

    if request.method == 'POST':
        plan = get_object_or_404(SubscriptionPlan, id=request.POST.get('plan_id'))
        PaymentTransaction.objects.create(company=company, amount_sar=plan.price_monthly_sar, payment_method=request.POST.get('payment_method', 'Mada'), status='PAID')
        sub, _ = CompanySubscription.objects.get_or_create(company=company)
        sub.plan = plan
        sub.status = 'ACTIVE'
        sub.save()
        return redirect('/')

    return render(request, 'accounting/pricing.html', {'plans': plans, 'company': company, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    comp = invoice.company or get_user_company(request)
    if not invoice.zatca_qr_b64: invoice.update_totals_and_post_accounting(); invoice.refresh_from_db()
    if request.method == 'POST' and 'record_payment' in request.POST:
        pay_amount = Decimal(request.POST.get('pay_amount', '0.00'))
        if pay_amount > 0 and request.POST.get('bank_id'):
            rv = ReceiptVoucher.objects.create(company=comp, voucher_no=f"RV-INV-{invoice.invoice_no}-{int(datetime.now().timestamp())}", customer=invoice.customer, invoice=invoice, bank_account_id=request.POST.get('bank_id'), amount=pay_amount, payment_method=request.POST.get('payment_method', 'Bank Transfer'), notes=request.POST.get('notes', 'Payment'))
            rv.post_accounting(); return redirect('invoice-detail', pk=invoice.pk)
    return render(request, 'accounting/invoice_detail.html', {'invoice': invoice, 'company': comp, 'qr_image': generate_qr_image_base64(invoice.zatca_qr_b64) if invoice.zatca_qr_b64 else "", 'bank_accounts': BankAccount.objects.filter(company=comp)})

def product_bundle_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST' and 'create_bundle' in request.POST:
        Product.objects.create(company=company, name=request.POST.get('name'), cat_no=request.POST.get('cat_no'), sale_price=Decimal(request.POST.get('sale_price', '0.00')), item_type='BUNDLE')
        return redirect('/inventory/bundles/')
    if request.method == 'POST' and 'add_component' in request.POST:
        ProductBundleItem.objects.create(bundle_product_id=request.POST.get('bundle_id'), component_product_id=request.POST.get('component_id'), quantity=int(request.POST.get('qty', 1)))
        return redirect('/inventory/bundles/')
    return render(request, 'accounting/product_bundles.html', {'company': company, 'bundle_products': Product.objects.filter(company=company, item_type='BUNDLE'), 'individual_products': Product.objects.filter(company=company).exclude(item_type='BUNDLE'), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def uom_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST':
        UnitOfMeasure.objects.create(company=company, name=request.POST.get('name'), symbol=request.POST.get('symbol'))
        return redirect('/inventory/units/')
    return render(request, 'accounting/uom_manage.html', {'company': company, 'units': UnitOfMeasure.objects.filter(company=company), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def aging_report_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    now = datetime.now().date(); customers = Customer.objects.filter(company=company); customer_aging = []
    for c in customers:
        invs = Invoice.objects.filter(customer=c, payment_status__in=['UNPAID', 'PARTIALLY_PAID'])
        b0_30 = Decimal('0.00'); b31_60 = Decimal('0.00'); b61_90 = Decimal('0.00'); b90_plus = Decimal('0.00')
        for inv in invs:
            days = (now - inv.date.date()).days
            due = inv.remaining_due()
            if days <= 30: b0_30 += due
            elif days <= 60: b31_60 += due
            elif days <= 90: b61_90 += due
            else: b90_plus += due
        tot = b0_30 + b31_60 + b61_90 + b90_plus
        if tot > 0: customer_aging.append({'name': c.name, 'b0_30': b0_30, 'b31_60': b31_60, 'b61_90': b61_90, 'b90_plus': b90_plus, 'total': tot})
    return render(request, 'accounting/aging_report.html', {'company': company, 'customer_aging': customer_aging, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def recurring_invoice_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST':
        cust = get_object_or_404(Customer, id=request.POST.get('customer_id'))
        prod = get_object_or_404(Product, id=request.POST.get('product_id'))
        qty = int(request.POST.get('qty', 1))
        sub = prod.sale_price * Decimal(qty); vat = sub * Decimal('0.15'); tot = sub + vat
        rec = RecurringInvoice.objects.create(company=company, customer=cust, frequency=request.POST.get('frequency', 'MONTHLY'), subtotal=sub, vat_amount=vat, total_amount=tot)
        RecurringInvoiceItem.objects.create(recurring_invoice=rec, product=prod, qty=qty, unit_price=prod.sale_price, total=sub)
        return redirect('/sales/recurring/')
    return render(request, 'accounting/recurring_invoices.html', {'company': company, 'recurring_list': RecurringInvoice.objects.filter(company=company).order_by('-id'), 'customers': Customer.objects.filter(company=company), 'products': Product.objects.filter(company=company), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def price_list_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST' and 'create_list' in request.POST:
        PriceList.objects.create(company=company, name=request.POST.get('name'))
        return redirect('/sales/price-lists/')
    if request.method == 'POST' and 'add_item' in request.POST:
        PriceListItem.objects.update_or_create(price_list=get_object_or_404(PriceList, id=request.POST.get('price_list_id')), product=get_object_or_404(Product, id=request.POST.get('product_id')), defaults={'custom_price': Decimal(request.POST.get('custom_price', '0.00'))})
        return redirect('/sales/price-lists/')
    return render(request, 'accounting/price_lists.html', {'company': company, 'price_lists': PriceList.objects.filter(company=company), 'products': Product.objects.filter(company=company), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def debit_note_detail_view(request, pk):
    debit_note = get_object_or_404(DebitNote, pk=pk)
    return render(request, 'accounting/debit_note_detail.html', {'debit_note': debit_note, 'company': debit_note.company or get_user_company(request)})

def create_debit_note_view(request, bill_id):
    bill = get_object_or_404(PurchaseBill, pk=bill_id)
    comp = bill.company or get_user_company(request)
    if request.method == 'POST':
        dbn = DebitNote.objects.create(company=comp, debit_note_no=f"DBN-{bill.bill_no}", purchase_bill=bill, reason=request.POST.get('reason', 'Damaged return'))
        for item in bill.items.all():
            qty_ret = int(request.POST.get(f'return_qty_{item.id}', 0))
            if qty_ret > 0: DebitNoteItem.objects.create(debit_note=dbn, product=item.product, qty=qty_ret, unit_cost=item.unit_cost)
        dbn.update_totals_and_post_accounting()
        return redirect('debit-note-detail', pk=dbn.pk)
    return render(request, 'accounting/debit_note_create.html', {'bill': bill, 'company': comp})

def direct_expense_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST':
        subtotal = Decimal(request.POST.get('subtotal', '0.00'))
        vat = subtotal * Decimal('0.15') if request.POST.get('has_vat') == '1' else Decimal('0.00')
        exp = DirectExpense.objects.create(
            company=company, expense_no=f"EXP-{int(datetime.now().timestamp())}",
            expense_account_id=request.POST.get('account_id'), bank_account_id=request.POST.get('bank_id'),
            cost_center_id=request.POST.get('cost_center_id') or None, description=request.POST.get('description', 'Office Expense'),
            subtotal=subtotal, vat_amount=vat, total_amount=subtotal+vat, payment_method=request.POST.get('payment_method', 'Bank Transfer')
        )
        exp.post_accounting()
        return redirect('/expenses/')
    return render(request, 'accounting/direct_expense.html', {
        'company': company, 'expenses': DirectExpense.objects.filter(company=company).order_by('-id'),
        'expense_accounts': Account.objects.filter(company=company, account_type='Expense'),
        'banks': BankAccount.objects.filter(company=company), 'cost_centers': CostCenter.objects.filter(company=company),
        'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def bank_reconciliation_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    banks = BankAccount.objects.filter(company=company)
    selected_bank_id = request.GET.get('bank_id', banks.first().id if banks.exists() else None)
    selected_bank = BankAccount.objects.filter(id=selected_bank_id).first() if selected_bank_id else None

    if request.method == 'POST' and request.FILES.get('statement_file'):
        file = request.FILES['statement_file']
        bs = BankStatement.objects.create(company=company, bank_account=selected_bank, filename=file.name)
        reader = csv.reader(io.StringIO(file.read().decode('utf-8')))
        for row in reader:
            if len(row) >= 3:
                try:
                    amt = Decimal(row[2].strip().replace(',', ''))
                    BankStatementLine.objects.create(statement=bs, date=row[0].strip() or datetime.now().strftime("%Y-%m-%d"), description=row[1].strip(), amount=abs(amt), transaction_type="CREDIT" if amt >= 0 else "DEBIT")
                except Exception: continue
        return redirect(f'/banking/reconciliation/?bank_id={selected_bank.id}')

    if request.method == 'POST' and 'reconcile_line_id' in request.POST:
        line = get_object_or_404(BankStatementLine, id=request.POST.get('reconcile_line_id'))
        line.is_reconciled = not line.is_reconciled; line.save()
        return redirect(f'/banking/reconciliation/?bank_id={selected_bank.id}')

    statement_lines = BankStatementLine.objects.filter(statement__bank_account=selected_bank).order_by('-date') if selected_bank else []
    return render(request, 'accounting/bank_reconciliation.html', {'company': company, 'banks': banks, 'selected_bank': selected_bank, 'statement_lines': statement_lines, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def fund_transfer_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    if request.method == 'POST':
        from_acc = get_object_or_404(BankAccount, id=request.POST.get('from_account'))
        to_acc = get_object_or_404(BankAccount, id=request.POST.get('to_account'))
        amount = Decimal(request.POST.get('amount', '0.00'))
        if from_acc != to_acc and amount > 0:
            ft = FundTransfer.objects.create(company=company, transfer_no=f"FT-{int(datetime.now().timestamp())}", from_account=from_acc, to_account=to_acc, amount=amount, notes=request.POST.get('notes', 'Fund Transfer'))
            ft.post_accounting(); return redirect('/banking/transfer/')
    return render(request, 'accounting/fund_transfer.html', {'company': company, 'banks': BankAccount.objects.filter(company=company), 'transfers': FundTransfer.objects.filter(company=company).order_by('-id')[:15], 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def delivery_note_detail_view(request, pk):
    dn = get_object_or_404(DeliveryNote, pk=pk)
    return render(request, 'accounting/delivery_note_detail.html', {'dn': dn, 'company': dn.company or get_user_company(request), 'qr_image': generate_qr_image_base64(f"DELIVERY: {dn.delivery_no}")})

def create_delivery_note_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    comp = invoice.company or get_user_company(request)
    if request.method == 'POST':
        wh = get_object_or_404(Warehouse, id=request.POST.get('warehouse_id')) if request.POST.get('warehouse_id') else invoice.warehouse or Warehouse.objects.filter(company=comp).first()
        dn = DeliveryNote.objects.create(company=comp, delivery_no=f"DN-{invoice.invoice_no}", invoice=invoice, warehouse=wh, driver_name=request.POST.get('driver_name', ''), vehicle_no=request.POST.get('vehicle_no', ''), status="DELIVERED")
        for item in invoice.items.all():
            DeliveryNoteItem.objects.create(delivery_note=dn, product=item.product, batch_no=request.POST.get(f'batch_{item.id}', 'BATCH-01'), expiry_date=request.POST.get(f'exp_{item.id}', '2028-12-31'), qty_delivered=int(request.POST.get(f'qty_{item.id}', item.qty)))
        return redirect('delivery-note-detail', pk=dn.pk)
    return render(request, 'accounting/delivery_note_create.html', {'invoice': invoice, 'company': comp, 'warehouses': Warehouse.objects.filter(company=comp)})

def credit_note_detail_view(request, pk):
    cn = get_object_or_404(CreditNote, pk=pk)
    if not cn.zatca_qr_b64: cn.update_totals_and_post_accounting(); cn.refresh_from_db()
    return render(request, 'accounting/credit_note_detail.html', {'credit_note': cn, 'company': cn.company or get_user_company(request), 'qr_image': generate_qr_image_base64(cn.zatca_qr_b64) if cn.zatca_qr_b64 else ""})

def create_credit_note_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    comp = invoice.company or get_user_company(request)
    if request.method == 'POST':
        cn = CreditNote.objects.create(company=comp, credit_note_no=f"CN-{invoice.invoice_no}", invoice=invoice, reason=request.POST.get('reason', 'Customer Return'))
        for item in invoice.items.all():
            qty_return = int(request.POST.get(f'return_qty_{item.id}', 0))
            if qty_return > 0: CreditNoteItem.objects.create(credit_note=cn, product=item.product, qty=qty_return, unit_price=item.unit_price)
        cn.update_totals_and_post_accounting(); return redirect('credit-note-detail', pk=cn.pk)
    return render(request, 'accounting/credit_note_create.html', {'invoice': invoice, 'company': comp})

def company_signup_view(request):
    if request.method == 'POST':
        user = User.objects.create_user(username=request.POST.get('username'), email=request.POST.get('email', ''), password=request.POST.get('password'))
        comp = Company.objects.create(name=request.POST.get('company_name'), vat_number=request.POST.get('vat_number', '300000000000003'), phone=request.POST.get('phone', ''))
        profile, _ = UserProfile.objects.get_or_create(user=user); profile.company = comp; profile.role = 'ADMIN'; profile.save()
        plan, _ = SubscriptionPlan.objects.get_or_create(slug='standard', defaults={'name': 'Standard Plan', 'price_monthly_sar': Decimal('199.00')})
        CompanySubscription.objects.create(company=comp, plan=plan, status='ACTIVE')
        login(request, user); return redirect('/')
    return render(request, 'accounting/signup.html')

def statement_of_account_view(request, party_type, pk):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    ledger_lines = []; running_balance = Decimal('0.00')
    if party_type == 'customer':
        party = get_object_or_404(Customer, pk=pk)
        for inv in Invoice.objects.filter(customer=party).order_by('date'):
            running_balance += inv.total_amount; ledger_lines.append({'date': inv.date.strftime("%Y-%m-%d"), 'ref': f"Invoice #{inv.invoice_no}", 'desc': 'Sales Invoice', 'debit': inv.total_amount, 'credit': Decimal('0.00'), 'balance': running_balance})
        for rc in ReceiptVoucher.objects.filter(customer=party).order_by('date'):
            running_balance -= rc.amount; ledger_lines.append({'date': str(rc.date), 'ref': f"Receipt #{rc.voucher_no}", 'desc': 'Payment received', 'debit': Decimal('0.00'), 'credit': rc.amount, 'balance': running_balance})
    else:
        party = get_object_or_404(Supplier, pk=pk)
        for b in PurchaseBill.objects.filter(supplier=party).order_by('date'):
            running_balance += b.total_amount; ledger_lines.append({'date': str(b.date), 'ref': f"Bill #{b.bill_no}", 'desc': 'Vendor Bill', 'debit': Decimal('0.00'), 'credit': b.total_amount, 'balance': running_balance})
        for pv in PaymentVoucher.objects.filter(supplier=party).order_by('date'):
            running_balance -= pv.amount; ledger_lines.append({'date': str(pv.date), 'ref': f"Payment #{pv.voucher_no}", 'desc': 'Payment sent', 'debit': pv.amount, 'credit': Decimal('0.00'), 'balance': running_balance})
    ledger_lines.sort(key=lambda x: x['date'])
    return render(request, 'accounting/statement.html', {'company': company, 'party': party, 'party_type': party_type, 'title_en': f'{party_type.capitalize()} Statement', 'title_ar': 'كشف حساب', 'ledger_lines': ledger_lines, 'final_balance': running_balance, 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def wps_sif_export_view(request, payroll_id):
    payroll = get_object_or_404(MonthlyPayroll, pk=payroll_id); company = get_user_company(request)
    sif = f"SCR|{company.cr_number or '1010445566'}|{company.name}|{payroll.processed_date.strftime('%Y%m%d')}|{payroll.month_year.replace('-','')}|{payroll.items.count()}|{payroll.total_amount:.2f}|SAR\n"
    for item in payroll.items.all():
        sif += f"EDR|{item.employee.iqama_no}|{item.employee.bank_iban}|{item.employee.name_en}|{item.basic_salary:.2f}|{item.housing:.2f}|{item.transport:.2f}|{item.deductions:.2f}|{item.net_salary:.2f}|SAR\n"
    res = HttpResponse(sif, content_type='text/plain'); res['Content-Disposition'] = f'attachment; filename="WPS_{payroll.month_year}.sif"'
    return res

def set_language_view(request, lang):
    if lang in ['ar', 'en']: request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', '/'))

def manufacturing_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    wos = WorkOrder.objects.filter(company=company).order_by('-id')
    return render(request, 'accounting/manufacturing.html', {'company': company, 'work_orders': wos, 'boms': BillOfMaterials.objects.filter(company=company), 'tot_produced': sum(w.actual_qty_produced for w in wos.filter(status='COMPLETED')), 'tot_mfg_cost': sum(w.total_batch_cost for w in wos.filter(status='COMPLETED')), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def scanner_view(request):
    return render(request, 'accounting/scanner.html', {'lang': request.session.get('lang', 'en'), 'is_ar': request.session.get('lang', 'en') == 'ar', 'lang_dir': 'rtl' if request.session.get('lang', 'en') == 'ar' else 'ltr'})

def custom_reports_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    return render(request, 'accounting/custom_reports.html', {'company': company, 'report_type': 'sales', 'customers': Customer.objects.filter(company=company), 'warehouses': Warehouse.objects.filter(company=company), 'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir})

def reports_view(request):
    lang = request.session.get('lang', 'en'); is_ar = (lang == 'ar'); lang_dir = 'rtl' if is_ar else 'ltr'
    company = get_user_company(request)
    accounts = Account.objects.filter(company=company).order_by('code')
    trial_balance = []; tot_debit_all = Decimal('0.00'); tot_credit_all = Decimal('0.00')
    for acc in accounts:
        debit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
        credit_sum = JournalEntryLine.objects.filter(account=acc).aggregate(Sum('credit'))['credit__sum'] or Decimal('0.00')
        tot_debit_all += debit_sum; tot_credit_all += credit_sum
        trial_balance.append({'code': acc.code, 'name': acc.name, 'type': acc.account_type, 'debit_total': debit_sum, 'credit_total': credit_sum, 'net_balance': debit_sum - credit_sum})

    total_sales = sum(inv.subtotal for inv in Invoice.objects.filter(company=company))
    total_cogs = sum(b.subtotal for b in PurchaseBill.objects.filter(company=company))
    expenses = JournalEntryLine.objects.filter(account__company=company, account__account_type='Expense').aggregate(Sum('debit'))['debit__sum'] or Decimal('0.00')
    ar = sum(inv.total_amount for inv in Invoice.objects.filter(company=company)) - sum(rv.amount for rv in ReceiptVoucher.objects.filter(company=company))
    ap = sum(b.total_amount for b in PurchaseBill.objects.filter(company=company)) - sum(pv.amount for pv in PaymentVoucher.objects.filter(company=company))
    bank_cash = sum(b.balance for b in BankAccount.objects.filter(company=company))
    inv_val = sum(p.current_stock * Decimal('15.00') for p in Product.objects.filter(company=company))
    vat_in = sum(b.vat_amount for b in PurchaseBill.objects.filter(company=company)) + sum(e.vat_amount for e in DirectExpense.objects.filter(company=company))
    vat_out = sum(inv.vat_amount for inv in Invoice.objects.filter(company=company))
    tot_assets = bank_cash + max(Decimal('0.00'), ar) + inv_val + vat_in
    tot_liab = max(Decimal('0.00'), ap) + vat_out

    return render(request, 'accounting/reports.html', {
        'company': company, 'trial_balance': trial_balance, 'tot_debit_all': tot_debit_all, 'tot_credit_all': tot_credit_all,
        'pnl': {'revenue': total_sales, 'cogs': total_cogs, 'gross_profit': total_sales - total_cogs, 'expenses': expenses, 'net_profit': total_sales - total_cogs - expenses},
        'bs': {'bank_cash': bank_cash, 'ar': max(Decimal('0.00'), ar), 'inventory': inv_val, 'vat_input': vat_in, 'total_assets': tot_assets, 'ap': max(Decimal('0.00'), ap), 'vat_output': vat_out, 'total_liabilities': tot_liab, 'equity': tot_assets - tot_liab},
        'vat': {'sales_base': total_sales, 'sales_vat': vat_out, 'pur_base': total_cogs, 'pur_vat': vat_in, 'net_due': vat_out - vat_in},
        'ledger_entries': JournalEntryLine.objects.filter(account__company=company).select_related('journal_entry', 'account').order_by('-id')[:30],
        'lang': lang, 'is_ar': is_ar, 'lang_dir': lang_dir
    })

def voucher_print_view(request, v_type, pk):
    voucher = get_object_or_404(ReceiptVoucher if v_type == 'receipt' else PaymentVoucher, pk=pk)
    return render(request, 'accounting/voucher_print.html', {'voucher': voucher, 'v_type': v_type, 'title_en': 'Voucher', 'title_ar': 'سند', 'party_label': 'Entity', 'party_name': getattr(voucher, 'customer', getattr(voucher, 'supplier', 'Expense')), 'company': get_user_company(request)})

def transfer_slip_print_view(request, pk):
    t = get_object_or_404(StockTransfer, pk=pk)
    return render(request, 'accounting/transfer_print.html', {'transfer': t, 'company': get_user_company(request), 'qr_image': generate_qr_image_base64(f"TR: {t.transfer_no}")})

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
