import subprocess, sys, time, re, os
import qrcode

print("🚀 Starting SAMCO Cloud ERP Server on port 9000...")
django_proc = subprocess.Popen([sys.executable, "manage.py", "runserver", "0.0.0.0:9000"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(2)
print("🌐 Connecting Cloudflare Secure Tunnel...")

cf_path = os.path.expanduser("~/cloudflared")
cf_cmd = [cf_path, "tunnel", "--protocol", "http2", "--url", "http://localhost:9000"]
cf_proc = subprocess.Popen(cf_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

tunnel_url = None
for line in cf_proc.stdout:
    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
    if match:
        tunnel_url = match.group(0)
        break

if tunnel_url:
    print("\n" + "="*60)
    print(f"✅ LIVE CLOUD LINK: {tunnel_url}")
    print(f"✅ ADMIN LOGIN:     {tunnel_url}/admin")
    print("="*60 + "\n")
    print("📱 SCAN THIS QR CODE WITH YOUR PHONE (4G/5G Ready):\n")
    qr = qrcode.QRCode()
    qr.add_data(tunnel_url)
    qr.print_ascii(invert=True)
    print("\n⚡ Keep this terminal open! Press Control+C to stop.")
else:
    print("❌ Could not get tunnel URL. Please check internet connection.")

try:
    cf_proc.wait()
except KeyboardInterrupt:
    print("\n🛑 Stopping server and tunnel...")
    django_proc.terminate()
    cf_proc.terminate()
