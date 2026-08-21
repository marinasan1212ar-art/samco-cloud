from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
import random
from .models import (
    CompanySettings, Customer, Supplier, Product, PriceList,
    Invoice, Quotation, RecurringInvoice, PurchaseBill, DirectExpense,
    Worker, AttendanceLog, SalarySheet, DeliveryNote, TransferSlip,
    VehicleBill, RejectLog, Account, JournalEntry
)

def get_user_company(request):
    company = CompanySettings.objects.first()
    if not company:
        company = CompanySettings.objects.create()
    return company

def home_dashboard_view(request):
    company = get_user_company(request)
    products_count = Product.objects.count()
    customers_count = Customer.objects.count()
    workers_count = Worker.objects.count()
    
    total_sales = sum(inv.grand_total for inv in Invoice.objects.all())
    total_purchases = sum(bill.grand_total for bill in PurchaseBill.objects.all())
    total_expenses = sum(exp.total_amount for exp in DirectExpense.objects.all())
    net_profit = total_sales - (total_purchases + total_expenses)
    
    return render(request, 'accounting/dashboard.html', {
        'company': company,
        'products_count': products_count,
        'customers_count': customers_count,
        'workers_count': workers_count,
        'total_sales': total_sales,
        'total_purchases': total_purchases,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
    })

# -------------------------------------------------------------------------
# INVOICE MANAGEMENT VIEWS (Fixes /invoices/ and /invoices/create/)
# -------------------------------------------------------------------------
def invoices_list_view(request):
    company = get_user_company(request)
    invoices = Invoice.objects.all().order_by('-id')
    return render(request, 'accounting/invoices_list.html', {
        'company': company,
        'invoices': invoices,
    })

def create_invoice_view(request):
    company = get_user_company(request)
    if request.method == 'POST':
        inv_no = request.POST.get('invoice_number') or f"INV-{random.randint(1000,9999)}"
        issue_date = request.POST.get('issue_date') or timezone.now().date()
        customer_name = request.POST.get('customer_name') or "General Client"
        subtotal = float(request.POST.get('subtotal') or 0)
        vat_amount = float(request.POST.get('vat_amount') or 0)
        grand_total = float(request.POST.get('grand_total') or 0)
        
        customer, _ = Customer.objects.get_or_create(name=customer_name)
        
        inv = Invoice.objects.create(
            invoice_number=inv_no,
            customer=customer,
            issue_date=issue_date,
            subtotal=subtotal,
            vat_amount=vat_amount,
            grand_total=grand_total,
            status="PAID"
        )
        return redirect('invoice-detail', pk=inv.id)

    return render(request, 'accounting/create_invoice.html', {
        'company': company,
        'random_inv': random.randint(10000, 99999)
    })

def invoice_detail_view(request, pk):
    company = get_user_company(request)
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(request, 'accounting/invoice_detail.html', {
        'company': company,
        'invoice': invoice,
    })

def financial_reports_view(request):
    company = get_user_company(request)
    total_sales = sum(inv.grand_total for inv in Invoice.objects.all())
    total_expenses = sum(exp.total_amount for exp in DirectExpense.objects.all())
    net_profit = total_sales - total_expenses
    return render(request, 'accounting/financial_reports.html', {
        'company': company,
        'total_sales': total_sales,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
    })

def banking_transfer_view(request):
    company = get_user_company(request)
    return render(request, 'accounting/banking_transfer.html', {'company': company})

def settings_page_view(request):
    company = get_user_company(request)
    models_data = [
        {'name': 'Accounts', 'admin_url': '/admin/accounting/account/', 'add_url': '/admin/accounting/account/add/'},
        {'name': 'Attendance logs', 'admin_url': '/admin/accounting/attendancelog/', 'add_url': '/admin/accounting/attendancelog/add/'},
        {'name': 'Company Settings', 'admin_url': '/admin/accounting/companysettings/', 'add_url': '/admin/accounting/companysettings/add/'},
        {'name': 'Customers', 'admin_url': '/admin/accounting/customer/', 'add_url': '/admin/accounting/customer/add/'},
        {'name': 'Delivery notes', 'admin_url': '/admin/accounting/deliverynote/', 'add_url': '/admin/accounting/deliverynote/add/'},
        {'name': 'Direct expenses', 'admin_url': '/admin/accounting/directexpense/', 'add_url': '/admin/accounting/directexpense/add/'},
        {'name': 'Invoices', 'admin_url': '/admin/accounting/invoice/', 'add_url': '/invoices/create/'},
        {'name': 'Journal Entries', 'admin_url': '/admin/accounting/journalentry/', 'add_url': '/admin/accounting/journalentry/add/'},
        {'name': 'Price lists', 'admin_url': '/admin/accounting/pricelist/', 'add_url': '/admin/accounting/pricelist/add/'},
        {'name': 'Products', 'admin_url': '/admin/accounting/product/', 'add_url': '/admin/accounting/product/add/'},
        {'name': 'Purchase bills', 'admin_url': '/admin/accounting/purchasebill/', 'add_url': '/admin/accounting/purchasebill/add/'},
        {'name': 'Quotations', 'admin_url': '/admin/accounting/quotation/', 'add_url': '/admin/accounting/quotation/add/'},
        {'name': 'Recurring invoices', 'admin_url': '/admin/accounting/recurringinvoice/', 'add_url': '/admin/accounting/recurringinvoice/add/'},
        {'name': 'Reject logs', 'admin_url': '/admin/accounting/rejectlog/', 'add_url': '/admin/accounting/rejectlog/add/'},
        {'name': 'Salary sheets', 'admin_url': '/admin/accounting/salarysheet/', 'add_url': '/admin/accounting/salarysheet/add/'},
        {'name': 'Suppliers', 'admin_url': '/admin/accounting/supplier/', 'add_url': '/admin/accounting/supplier/add/'},
        {'name': 'Transfer slips', 'admin_url': '/admin/accounting/transferslip/', 'add_url': '/admin/accounting/transferslip/add/'},
        {'name': 'Vehicle bills', 'admin_url': '/admin/accounting/vehiclebill/', 'add_url': '/admin/accounting/vehiclebill/add/'},
        {'name': 'Workers', 'admin_url': '/admin/accounting/worker/', 'add_url': '/admin/accounting/worker/add/'},
    ]
    return render(request, 'accounting/settings.html', {'company': company, 'model_list': models_data})


def division_hub_view(request, dept='warehouse'):
    company = get_user_company(request)
    dept_lower = dept.lower()
    
    dept_meta = {
        'warehouse': {'name': 'Warehouse Division', 'icon': '🏭', 'sub': 'Master Finished Goods, Racking Map & Delivery'},
        'media': {'name': 'Media Division', 'icon': '📺', 'sub': 'Overtime Processing, Transfer Slips & Worker Dossier'},
        'cosmetic': {'name': 'Cosmetic Division', 'icon': '💄', 'sub': 'Cosmetic Formulations, Packaging & Batch QC'},
        'powder': {'name': 'Powder Division', 'icon': '🧪', 'sub': 'GRN (Moisture/Purity), Lab QC Dual Release & Drum Labels'},
        'plastic': {'name': 'Plastic Division', 'icon': '♻️', 'sub': 'Machine Injection Molding, Day/Night Shifts & Tender Delivery'}
    }
    
    current_meta = dept_meta.get(dept_lower, dept_meta['warehouse'])
    products = Product.objects.all().order_by('-id')[:20]
    workers = Worker.objects.all().order_by('-id')[:20]
    transfers = TransferSlip.objects.all().order_by('-id')[:20]
    deliveries = DeliveryNote.objects.all().order_by('-id')[:20]
    
    return render(request, 'accounting/division_hub.html', {
        'company': company,
        'dept': dept_lower,
        'dept_meta': current_meta,
        'products': products,
        'workers': workers,
        'transfers': transfers,
        'deliveries': deliveries,
    })

def super_admin_hub_view(request):
    company = get_user_company(request)
    workers = Worker.objects.all()
    today = timezone.now().date()
    iqama_alerts = []
    for w in workers:
        if w.iqama_exp:
            days = (w.iqama_exp - today).days
            if days <= 45:
                iqama_alerts.append({'worker': w, 'days': days, 'is_expired': days < 0})
                
    total_sales = sum(inv.grand_total for inv in Invoice.objects.all())
    total_purchases = sum(b.grand_total for b in PurchaseBill.objects.all())
    total_expenses = sum(e.total_amount for e in DirectExpense.objects.all()) + sum(v.amount for v in VehicleBill.objects.all())
    net_profit = total_sales - (total_purchases + total_expenses)
    
    salesmen_stats = [
        {'name': 'Mr. Jamal', 'rank': '🥇 Rank 1', 'sales': total_sales * 0.40, 'profit': net_profit * 0.40, 'comm': total_sales * 0.40 * 0.05},
        {'name': 'Sheikh Sultan', 'rank': '🥈 Rank 2', 'sales': total_sales * 0.30, 'profit': net_profit * 0.30, 'comm': total_sales * 0.30 * 0.05},
        {'name': 'Dr. Omar', 'rank': '🥉 Rank 3', 'sales': total_sales * 0.20, 'profit': net_profit * 0.20, 'comm': total_sales * 0.20 * 0.05},
        {'name': 'Saud Abdul Aziz', 'rank': '🎖️ Rank 4', 'sales': total_sales * 0.10, 'profit': net_profit * 0.10, 'comm': total_sales * 0.10 * 0.05},
    ]
    
    return render(request, 'accounting/super_admin_hub.html', {
        'company': company,
        'total_sales': total_sales,
        'total_purchases': total_purchases,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'salesmen_stats': salesmen_stats,
        'iqama_alerts': iqama_alerts,
        'vehicle_bills': VehicleBill.objects.all()[:10],
        'recent_invoices': Invoice.objects.all()[:10],
    })

def vat_return_view(request):
    company = get_user_company(request)
    sales_base = sum(inv.subtotal for inv in Invoice.objects.all())
    sales_vat = sum(inv.vat_amount for inv in Invoice.objects.all())
    pur_base = sum(b.subtotal for b in PurchaseBill.objects.all()) + sum(e.subtotal for e in DirectExpense.objects.all())
    pur_vat = sum(b.vat_amount for b in PurchaseBill.objects.all()) + sum(e.vat_amount for e in DirectExpense.objects.all())
    net_vat = sales_vat - pur_vat
    return render(request, 'accounting/vat_return.html', {
        'company': company, 'sales_base': sales_base, 'sales_vat': sales_vat,
        'pur_base': pur_base, 'pur_vat': pur_vat, 'net_vat': net_vat,
    })

def aging_report_view(request):
    company = get_user_company(request)
    return render(request, 'accounting/aging_report.html', {'company': company, 'customer_aging': []})

def price_list_view(request):
    price_lists = PriceList.objects.filter(is_active=True)
    return render(request, 'accounting/price_lists.html', {'price_lists': price_lists})

def recurring_invoice_view(request):
    recurring_invoices = RecurringInvoice.objects.filter(is_active=True)
    return render(request, 'accounting/recurring_invoices.html', {'recurring_invoices': recurring_invoices})

def statement_of_account_view(request, party_type='customer', pk=1):
    company = get_user_company(request)
    class DummyParty:
        name = "SECOND ADVANCE MEDICAL CLIENT"
        phone = "+966 50 123 4567"
        email = "finance@samco.sa"
    return render(request, 'accounting/statement_of_account.html', {
        'company': company, 'party': DummyParty(), 'party_type': party_type,
        'ledger_rows': [], 'total_billed': 0.0, 'outstanding_balance': 0.0
    })

def ocr_scanner_view(request):
    company = get_user_company(request)
    return render(request, 'accounting/ocr_scanner.html', {'company': company})
