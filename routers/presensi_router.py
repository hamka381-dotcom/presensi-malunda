from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import supabase
from datetime import datetime
from pydantic import BaseModel
import os, requests
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

load_dotenv()

router = APIRouter(prefix="/presensi", tags=["Presensi"])

# Konfigurasi dari .env
WABLAS_URL = os.getenv("WABLAS_API_URL")
WABLAS_TOKEN = os.getenv("WABLAS_API_TOKEN")
WABLAS_SECRET_KEY = os.getenv("WABLAS_SECRET_KEY")
KEPSEK_PHONE = os.getenv("KEPSEK_PHONE", "6285xxxxxxxxxx")

# Zona waktu
tz = pytz.timezone("Asia/Makassar")

class PresensiRequest(BaseModel):
    user_id: str
    status: str = "hadir"
    keterangan: str = ""

# =====================================================
# 🔧 Fungsi kirim WhatsApp + update status notifikasi
# =====================================================
def kirim_whatsapp(user_id: str, phone: str, message: str):
    """Kirim pesan WhatsApp via Wablas API dan update tabel notifikasi"""
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

        try:
            wablas_response = res.json()
        except Exception:
            wablas_response = {"status": False, "message": "Invalid response", "raw": res.text}

        print(f"📨 [WA SENT] -> {phone}: {wablas_response}")

        status = "terkirim" if wablas_response.get("status") else "gagal"
        response_message = wablas_response.get("message", "No response")

        supabase.table("notifikasi").insert({
            "user_id": user_id,
            "penerima": phone,
            "pesan": message,
            "status": status,
            "response_message": response_message,
            "sent_at": datetime.now(tz).isoformat(),
            "created_at": datetime.now(tz).isoformat()
        }).execute()

        return wablas_response

    except Exception as e:
        print(f"❌ Gagal kirim WA ke {phone}: {e}")
        supabase.table("notifikasi").insert({
            "user_id": user_id,
            "penerima": phone,
            "pesan": message,
            "status": "gagal",
            "response_message": str(e),
            "sent_at": datetime.now(tz).isoformat(),
            "created_at": datetime.now(tz).isoformat()
        }).execute()
        return {"status": False, "error": str(e)}

# =====================================================
# 🕒 Endpoint utama untuk presensi
# =====================================================
@router.post("/")
async def tambah_presensi(data: PresensiRequest):
    """
    Mencatat presensi & kirim notifikasi WhatsApp otomatis.
    - Siswa → ke orang tua (fallback: ke siswa sendiri)
    - Guru → ke kepala sekolah + dirinya sendiri
    - Admin → ke dirinya sendiri
    """
    try:
        now = datetime.now(tz)
        tanggal = now.strftime("%Y-%m-%d")
        jam_masuk = now.strftime("%H:%M:%S")

        # 🔍 Ambil data user
        user_res = supabase.table("users").select("id, nama, role, no_hp, orang_tua_phone").eq("id", data.user_id).execute()
        if not user_res.data:
            return {"ok": False, "message": "User tidak ditemukan"}

        user = user_res.data[0]
        nama_user = user.get("nama", "Tidak diketahui")
        role = user.get("role", "").lower()
        no_hp_user = user.get("no_hp")
        orang_tua_phone = user.get("orang_tua_phone")

        # 🧾 Cek apakah sudah presensi hari ini
        existing = supabase.table("presensi").select("id").eq("user_id", data.user_id).eq("tanggal", tanggal).execute().data
        if existing:
            return {"ok": False, "message": f"{role.capitalize()} sudah melakukan presensi hari ini"}

        # ⏰ Tentukan status otomatis
        batas_jam = (7, 15)
        if (now.hour, now.minute) > batas_jam:
            data.status = "terlambat"

        # 💾 Simpan presensi
        supabase.table("presensi").insert({
            "user_id": data.user_id,
            "tanggal": tanggal,
            "jam_masuk": jam_masuk,
            "status": data.status,
            "keterangan": data.keterangan
        }).execute()

        # 🧠 Pesan WA
        pesan = f"{role.capitalize()} *{nama_user}* telah melakukan presensi dengan status *{data.status.upper()}* pada {tanggal} pukul {jam_masuk}."

        # 🎯 Tentukan penerima
        if role == "siswa":
            nomor_tujuan = orang_tua_phone or no_hp_user
            if nomor_tujuan:
                kirim_whatsapp(data.user_id, nomor_tujuan, pesan)
            else:
                print(f"⚠️ Tidak ada nomor WA untuk {nama_user}")

        elif role == "guru":
            nomor_list = [KEPSEK_PHONE, no_hp_user]
            for nomor in nomor_list:
                if nomor:
                    kirim_whatsapp(data.user_id, nomor, pesan)
                else:
                    print(f"⚠️ Nomor guru/kepsek tidak ditemukan")

        else:
            if no_hp_user:
                kirim_whatsapp(data.user_id, no_hp_user, pesan)
            else:
                print(f"⚠️ Nomor user {nama_user} kosong")

        return {
            "ok": True,
            "message": f"Presensi {data.status} berhasil disimpan dan WA dikirim",
            "tanggal": tanggal,
            "jam_masuk": jam_masuk
        }

    except Exception as e:
        print("❌ Gagal simpan presensi:", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# =====================================================
# 🔁 AUTO RESEND NOTIFIKASI GAGAL / PENDING
# =====================================================
def resend_failed_notifications():
    """
    Mengecek tabel notifikasi setiap 1 jam dan kirim ulang pesan yang gagal/pending.
    """
    try:
        print("🔁 Cek notifikasi gagal/pending untuk dikirim ulang...")
        res = supabase.table("notifikasi").select("id, user_id, penerima, pesan, status").in_("status", ["gagal", "pending"]).execute()

        if not res.data:
            print("✅ Tidak ada notifikasi yang perlu dikirim ulang.")
            return

        for notif in res.data:
            kirim_whatsapp(
                notif["user_id"],
                notif["penerima"],
                f"[RESEND] {notif['pesan']}"
            )
        print(f"📨 {len(res.data)} notifikasi dikirim ulang.")
    except Exception as e:
        print("❌ Gagal melakukan resend otomatis:", e)


# =====================================================
# ⏰ SCHEDULER AUTO-RESEND SETIAP JAM
# =====================================================
scheduler = BackgroundScheduler(timezone=tz)
scheduler.add_job(resend_failed_notifications, "interval", minutes=30, id="resend_failed_notif", replace_existing=True)
scheduler.start()

print("⏰ Scheduler resend notifikasi aktif: setiap 30 menit sekali")
