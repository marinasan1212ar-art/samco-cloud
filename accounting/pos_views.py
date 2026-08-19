import json
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Company, Product, Customer, Invoice, InvoiceItem, BankAccount, ReceiptVoucher, CompanySettings
from .zatca import generate_zatca_qr_base64, generate_qr_image_base64

def get_comp(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.company:
        return request.user.profile.company
    comp, _ = Company.objects.get_or_create(id=1)
    return comp

def pos_dashboard(request):
    comp = get_comp(request)
    products = Product.objects.filter(company=comp, current_stock__gt=0)
    customers = Customer.objects.filter(company=comp)
    return render(request, 'accounting/pos.html', {'products': products, 'customers': customers, 'company': comp})

def pos_checkout(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comp = get_comp(request)
            cart = data.get('cart', [])
            customer_id = data.get('customer_id')
            pay_method = data.get('payment_method', 'Cash')
            
            if not cart: return JsonResponse({'error': 'Cart is empty'}, status=400)
            
            if customer_id:
                cust = Customer.objects.get(id=customer_id)
            else:
                cust, _ = Customer.objects.get_or_create(company=comp, name="Walk-in Customer", defaults={'vat_number': 'N/A'})
            
            inv_no = f"POS-{int(datetime.now().timestamp())}"
            invoice = Invoice.objects.create(
                company=comp, invoice_no=inv_no, customer=cust, invoice_type='Simplified Tax Invoice (فاتورة ضريبية مبسطة)'
            )
            
            subtotal = Decimal('0.00')
            for item in cart:
                prod = Product.objects.get(id=item['id'])
                qty = int(item['qty'])
                price = prod.sale_price 
                
                InvoiceItem.objects.create(invoice=invoice, product=prod, qty=qty, unit_price=price)
                subtotal += price * Decimal(qty)
            
            vat = subtotal * Decimal('0.15')
            tot = subtotal + vat
            
            comp_settings, _ = CompanySettings.objects.get_or_create(id=1)
            time_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            qr_b64 = generate_zatca_qr_base64(comp_settings.company_name_en, comp_settings.vat_number or "300000000000003", time_str, f"{tot:.2f}", f"{vat:.2f}")
            
            invoice.subtotal = subtotal
            invoice.vat_amount = vat
            invoice.total_amount = tot
            invoice.zatca_qr_b64 = qr_b64
            invoice.save()
            
            bank, _ = BankAccount.objects.get_or_create(company=comp, name="POS Cash Drawer (الخزينة)")
            ReceiptVoucher.objects.create(company=comp, voucher_no=f"RV-{inv_no}", customer=cust, invoice=invoice, bank_account=bank, amount=tot, payment_method=pay_method)
            
            return JsonResponse({'success': True, 'invoice_id': invoice.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def pos_receipt_print(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    comp_settings, _ = CompanySettings.objects.get_or_create(id=1)
    qr_img = generate_qr_image_base64(invoice.zatca_qr_b64) if invoice.zatca_qr_b64 else ""
    return render(request, 'accounting/pos_receipt.html', {'invoice': invoice, 'company': comp_settings, 'qr_image': qr_img})
