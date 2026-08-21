from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
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
# 5 DIVISIONS WEB WORKSPACES (Warehouse, Media, Cosmetic, Powder, Plastic)
# -------------------------------------------------------------------------
def division_hub_view(request, dept='warehouse'):
    company = get_user_company(request)
    dept_lower = dept.lower()
    
    dept_meta = {
        'warehouse': {'name': 'Warehouse Division', 'icon': '🏭', 'color': 'cyan', 'theme_code': '#06B6D4', 'sub': 'Master Finished Goods, Racking Map & Delivery'},
        'media': {'name': 'Media Division', 'icon': '📺', 'color': 'emerald', 'theme_code': '#10B981', 'sub': 'Overtime Processing, Transfer Slips & Worker Dossier'},
        'cosmetic': {'name': 'Cosmetic Division', 'icon': '💄', 'color': 'rose', 'theme_code': '#EC4899', 'sub': 'Cosmetic Formulations, Packaging & Batch QC'},
        'powder': {'name': 'Powder Division', 'icon': '🧪', 'color': 'amber', 'theme_code': '#F59E0B', 'sub': 'GRN (Moisture/Purity), Lab QC Dual Release & Drum Labels'},
        'plastic': {'name': 'Plastic Division', 'icon': '♻️', 'color': 'blue', 'theme_code': '#3B82F6', 'sub': 'Machine Injection Molding, Day/Night Shifts & Tender Delivery'}
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

# -------------------------------------------------------------------------
# 👑 SUPER ADMIN EXECUTIVE COMMAND CENTER
# -------------------------------------------------------------------------
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
    
    vehicle_bills = VehicleBill.objects.all().order_by('-id')[:15]
    recent_invoices = Invoice.objects.all().order_by('-id')[:10]
    
    return render(request, 'accounting/super_admin_hub.html', {
        'company': company,
        'total_sales': total_sales,
        'total_purchases': total_purchases,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'salesmen_stats': salesmen_stats,
        'iqama_alerts': iqama_alerts,
        'vehicle_bills': vehicle_bills,
        'recent_invoices': recent_invoices,
    })

# -------------------------------------------------------------------------
# OTHER COMMON VIEWS
# -------------------------------------------------------------------------
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

def settings_page_view(request):
    company = get_user_company(request)
    return render(request, 'accounting/settings.html', {'company': company})
