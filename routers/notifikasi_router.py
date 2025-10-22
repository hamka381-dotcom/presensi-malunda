from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import supabase
from pydantic import BaseModel
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

router = APIRouter(prefix="/notifikasi", tags=["Notifikasi"])

# Struktur request body
class NotifikasiRequest(BaseModel):
    user_id: str
    penerima: str
    pesan: str

# ------------------------------
# 1️⃣ Endpoint untuk tambah notifikasi
# ------------------------------
@router.post("/")
async def tambah_notifikasi(data: NotifikasiRequest):
    """Tambah data notifikasi baru ke Supabase"""
    try:
        res = supabase.table("notifikasi").insert({
            "user_id": data.user_id,
            "penerima": data.penerima,
            "pesan": data.pesan,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }).execute()

        return {"ok": True, "message": "Notifikasi berhasil disimpan", "data": res.data}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ------------------------------
# 2️⃣ Endpoint untuk menampilkan semua notifikasi
# ------------------------------
@router.get("/")
async def get_all_notifikasi():
    """Ambil semua notifikasi dari tabel Supabase"""
    try:
        res = supabase.table("notifikasi").select("*").order("created_at", desc=True).execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ------------------------------
# 3️⃣ Endpoint untuk update status notifikasi (terkirim/gagal)
# ------------------------------
@router.put("/{id}")
async def update_status_notifikasi(id: str, status: str):
    """Ubah status notifikasi (misal: dari pending jadi terkirim/gagal)"""
    try:
        res = supabase.table("notifikasi").update({"status": status}).eq("id", id).execute()
        return {"ok": True, "message": f"Status notifikasi {id} diubah menjadi {status}", "data": res.data}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ------------------------------
# 4️⃣ AUTO ALPA — Jalankan tiap jam 12:00 WITA
# ------------------------------
def auto_alpa():
    """
    Mengecek semua siswa di tabel users.
    - Jika sudah presensi → kirim notifikasi hadir
    - Jika belum presensi → otomatis buat data alpa + kirim notifikasi alpa
    """
    try:
        tz = pytz.timezone("Asia/Makassar")
        today = datetime.now(tz).strftime("%Y-%m-%d")
        users = supabase.table("users").select("id, nama, role").execute().data

        total_alpa = 0
        total_hadir = 0

        for user in users:
            role = (user.get('role') or '').strip().lower()
            if role != 'siswa':
                continue  # skip selain siswa

            user_id = user["id"]
            nama_siswa = user.get("nama", "Tidak diketahui")

            presensi_today = supabase.table("presensi") \
                .select("id, jam_masuk, status") \
                .eq("user_id", user_id) \
                .eq("tanggal", today) \
                .execute().data

            # --- Jika belum ada presensi, otomatis tandai ALPA ---
            if not presensi_today:
                supabase.table("presensi").insert({
                    "user_id": user_id,
                    "tanggal": today,
                    "jam_masuk": None,
                    "status": "alpa",
                    "keterangan": "Tidak melakukan presensi hari ini"
                }).execute()

                supabase.table("notifikasi").insert({
                    "user_id": user_id,
                    "penerima": "orang_tua",
                    "pesan": f"Siswa {nama_siswa} tidak melakukan presensi hari ini (otomatis alpa).",
                    "status": "pending",
                    "created_at": datetime.now(tz).isoformat()
                }).execute()

                total_alpa += 1
                print(f"🚨 {nama_siswa} → ditandai ALPA ({today})")

            # --- Jika sudah presensi, kirim notifikasi hadir ---
            else:
                jam = presensi_today[0].get("jam_masuk") or "-"
                status = presensi_today[0].get("status", "hadir").capitalize()
                supabase.table("notifikasi").insert({
                    "user_id": user_id,
                    "penerima": "orang_tua",
                    "pesan": f"Siswa {nama_siswa} tercatat {status} pada {today} pukul {jam}.",
                    "status": "pending",
                    "created_at": datetime.now(tz).isoformat()
                }).execute()

                total_hadir += 1
                print(f"✅ {nama_siswa} → sudah hadir ({today})")

        summary = {
            "ok": True,
            "tanggal": today,
            "hadir": total_hadir,
            "alpa": total_alpa,
            "message": f"{total_hadir} hadir, {total_alpa} alpa"
        }

        print(f"📅 AUTO ALPA SELESAI → {summary}")
        return summary

    except Exception as e:
        print("❌ AUTO ALPA ERROR:", e)
        return {"ok": False, "error": str(e)}

# ------------------------------
# 5️⃣ JADWALKAN AUTO ALPA SETIAP JAM 12:00 WITA
# ------------------------------
tz = pytz.timezone("Asia/Makassar")
scheduler = BackgroundScheduler(timezone=tz)
scheduler.add_job(auto_alpa, CronTrigger(hour=12, minute=0), id="auto_alpa_daily", replace_existing=True)

@scheduler.scheduled_job(CronTrigger(hour=12, minute=0))
def scheduled_auto_alpa():
    auto_alpa()

scheduler.start()
print("⏰ Scheduler AUTO ALPA aktif: setiap hari jam 12:00 WITA")

# ------------------------------
# 6️⃣ ENDPOINT MANUAL UNTUK MENJALANKAN AUTO ALPA
# ------------------------------
@router.api_route("/auto_alpa", methods=["GET", "POST"])
async def run_auto_alpa():
    """
    Menjalankan fungsi auto_alpa secara manual.
    Bisa dipanggil lewat GET (browser) atau POST (otomatis).
    """
    result = auto_alpa()
    return result



