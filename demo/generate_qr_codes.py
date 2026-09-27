import qrcode
import os

# Create output folders
os.makedirs("demo/scam_qr_codes", exist_ok=True)
os.makedirs("demo/safe_qr_codes", exist_ok=True)

print("="*60)
print("QuishGuard AI - Demo QR Code Generator")
print("="*60)

# SCAM QR CODES
scam_payloads = {
    "1_upi_receive_scam.png": {
        "data": "upi://pay?pa=scammer123@ybl&pn=FakeCashback&am=5000&tn=Reward",
        "label": "📱 UPI Scam: RECEIVE vs PAY Mismatch"
    },
    "2_free_tld_phishing.png": {
        "data": "http://paytm-verify-reward.tk/login",
        "label": "🌐 Free TLD (.tk) Phishing"
    },
    "3_brand_impersonation.png": {
        "data": "http://secure-gpay-verify.xyz/claim",
        "label": "🎭 Brand Impersonation (GPay fake)"
    },
    "4_http_insecure.png": {
        "data": "http://hdfc-secure-login.com/update",
        "label": "🔓 HTTP (not HTTPS) Banking Site"
    },
    "5_suspicious_keywords.png": {
        "data": "https://amazon-prize-winner.link/claim-now",
        "label": "⚠️ Suspicious Keywords (prize, claim)"
    }
}

print("\n🚨 Generating SCAM QR Codes...")
for filename, payload in scam_payloads.items():
    qr = qrcode.QRCode(
        version=5,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload["data"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    path = f"demo/scam_qr_codes/{filename}"
    img.save(path)
    print(f"✅ {filename} - {payload['label']}")

# SAFE QR CODES
safe_payloads = {
    "safe_google.png": {
        "data": "https://www.google.com",
        "label": "✅ Legitimate: Google"
    },
    "safe_github.png": {
        "data": "https://github.com",
        "label": "✅ Legitimate: GitHub"
    },
    "safe_upi_small.png": {
        "data": "upi://pay?pa=teashop@paytm&pn=RajTeaStall&am=20&tn=Tea",
        "label": "✅ Safe UPI: Small Amount Tea Shop"
    }
}

print("\n✅ Generating SAFE QR Codes...")
for filename, payload in safe_payloads.items():
    qr = qrcode.QRCode(
        version=5,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload["data"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    path = f"demo/safe_qr_codes/{filename}"
    img.save(path)
    print(f"✅ {filename} - {payload['label']}")

print("\n" + "="*60)
print("✅ QR Code Generation Complete!")
print("="*60)
print(f"\nSCAM QR Codes: demo/scam_qr_codes/ ({len(scam_payloads)} files)")
print(f"SAFE QR Codes: demo/safe_qr_codes/ ({len(safe_payloads)} files)")
print("\n📋 Next Steps:")
print("1. Print these QR codes on paper")
print("2. For UPI scam, write on paper: 'Scan to RECEIVE ₹5000'")
print("3. Use Flutter app or Extension to scan during demo")
print("="*60)