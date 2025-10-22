from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os, requests
from dotenv import load_dotenv

# =====================================================
# 🔧 Inisialisasi dan Load Environment
# =====================================================
load_dotenv()
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Gateway"])

# Ambil variabel dari .env
WABLAS_URL = os.getenv("WABLAS_API_URL")
WABLAS_TOKEN = os.getenv("WABLAS_API_TOKEN")
WABLAS_SECRET_KEY = os.getenv("WABLAS_SECRET_KEY")
ADMIN_PHONE = os.getenv("ADMIN_PHONE")  # nomor admin untuk notifikasi IP

# =====================================================
# 🔄 Fungsi Update Whitelist IP Otomatis ke Wablas
# =====================================================
def update_wablas_whitelist():
    """
    🧩 Update IP publik otomatis ke whitelist Wablas.
    Tidak perlu lagi ubah manual di dashboard.
    """
    try:
        ip_info = requests.get("https://api.myip.com").json()
        current_ip = ip_info.get("ip")

        if not current_ip:
            print("⚠️ Tidak bisa mendapatkan IP publik.")
            return

        print(f"🌍 IP publik saat ini: {current_ip}")

        whitelist_endpoint = "https://sby.wablas.com/api/v2/send-message"
        headers = {
            "Authorization": WABLAS_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {
            "ip": current_ip,
            "secret": WABLAS_SECRET_KEY
        }

        res = requests.post(whitelist_endpoint, json=payload, headers=headers)
        data = res.json()

        if res.status_code == 200 and data.get("status") is True:
            print(f"✅ IP {current_ip} berhasil ditambahkan ke whitelist Wablas.")
        else:
            print(f"⚠️ Gagal menambahkan IP ke whitelist Wablas: {data}")

    except Exception as e:
        print("❌ Gagal update whitelist Wablas:", e)

# =====================================================
# 🔍 Fungsi Cek IP Publik dan Kirim Notifikasi ke WhatsApp
# =====================================================
def check_ip_change():
    """
    Cek IP publik, kalau berubah kirim notifikasi ke admin
    supaya whitelist Wablas bisa diperbarui manual.
    """
    try:
        ip_info = requests.get("https://api.myip.com").json()
        current_ip = ip_info.get("ip")

        if not current_ip:
            print("⚠️ Tidak bisa mendapatkan IP publik.")
            return

        last_ip_file = "last_ip.txt"
        last_ip = None

        if os.path.exists(last_ip_file):
            with open(last_ip_file, "r") as f:
                last_ip = f.read().strip()

        if last_ip != current_ip:
            print(f"⚠️ IP publik berubah: {last_ip} ➜ {current_ip}")
            with open(last_ip_file, "w") as f:
                f.write(current_ip)

            if ADMIN_PHONE:
                message = (
                    f"📡 *Notifikasi Presensi SMAN 1 Malunda*\n\n"
                    f"⚠️ IP server berubah dari `{last_ip}` ke `{current_ip}`\n"
                    f"Harap tambahkan IP ini ke *Whitelist* Wablas:\n"
                    f"🌐 https://sby.wablas.com\n\n"
                    f"Jika IP ini sudah di-whitelist, abaikan pesan ini."
                )
                send_whatsapp_message(ADMIN_PHONE, message)
            else:
                print("⚠️ Nomor admin (ADMIN_PHONE) belum diset di .env.")
        else:
            print(f"✅ IP publik masih sama ({current_ip}).")

    except Exception as e:
        print("❌ Gagal memeriksa IP publik:", e)

# =====================================================
# ✉️ Fungsi Kirim Notifikasi IP via WhatsApp
# =====================================================
def send_ip_change_notification(phone, old_ip, new_ip):
    """
    Mengirim pesan WA otomatis jika IP publik berubah.
    """
    message = (
        f"📡 *Notifikasi Presensi SMAN 1 Malunda*\n\n"
        f"⚠️ IP publik server berubah dari `{old_ip}` ke `{new_ip}`.\n"
        f"Whitelist Wablas sudah diperbarui otomatis ✅\n\n"
        f"🌐 https://sby.wablas.com"
    )

    try:
        payload = {
            "data": [
                {
                    "phone": phone,
                    "message": message,
                    "secret": WABLAS_SECRET_KEY
                }
            ]
        }

        headers = {
            "Authorization": WABLAS_TOKEN,
            "Content-Type": "application/json"
        }

        res = requests.post(WABLAS_URL, json=payload, headers=headers)
        wablas_response = res.json()

        print("📨 Notifikasi WA terkirim:", wablas_response)

    except Exception as e:
        print("❌ Gagal kirim notifikasi WA:", e)

# =====================================================
# ✉️ Endpoint: Kirim Pesan WhatsApp Manual
# =====================================================
@router.post("/send")
async def send_whatsapp_message(phone: str, message: str):
    """
    Kirim pesan WhatsApp via Wablas API (v2)
    Contoh: POST /whatsapp/send?phone=6281234567890&message=Halo%20Dunia
    """
    try:
        payload = {
            "data": [
                {
                    "phone": phone,
                    "message": message,
                    "secret": WABLAS_SECRET_KEY
                }
            ]
        }

        headers = {
            "Authorization": WABLAS_TOKEN,
            "Content-Type": "application/json"
        }

        res = requests.post(WABLAS_URL, json=payload, headers=headers)
        wablas_response = res.json()

        print("📨 Wablas response:", wablas_response)
        return {"ok": True, "response": wablas_response}

    except Exception as e:
        print("❌ Gagal kirim WhatsApp:", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# =====================================================
# 🚀 Jalankan pengecekan IP saat server startup
# =====================================================
check_ip_change()
