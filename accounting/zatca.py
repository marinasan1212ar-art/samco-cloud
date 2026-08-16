import base64
import qrcode
import io

def get_tlv_byte(tag_num: int, value: str) -> bytes:
    """ZATCA Phase-2 Tag-Length-Value (TLV) Binary Encoder"""
    val_bytes = value.encode('utf-8')
    tag_byte = bytes([tag_num])
    length_byte = bytes([len(val_bytes)])
    return tag_byte + length_byte + val_bytes

def generate_zatca_qr_base64(seller_name: str, vat_no: str, timestamp_iso: str, total_amount: str, vat_amount: str) -> str:
    """Generates standard ZATCA compliant Base64 string from TLV data"""
    tlv = (
        get_tlv_byte(1, seller_name) +
        get_tlv_byte(2, vat_no) +
        get_tlv_byte(3, timestamp_iso) +
        get_tlv_byte(4, total_amount) +
        get_tlv_byte(5, vat_amount)
    )
    return base64.b64encode(tlv).decode('utf-8')

def generate_qr_image_base64(qr_data: str) -> str:
    """Generates an embedded PNG image representation for HTML/PDF rendering"""
    qr = qrcode.QRCode(box_size=5, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')
