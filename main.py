from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from routers import siswa_router, presensi_router, notifikasi_router, whatsapp_router, qrcode_router, idcard_router_bg, user_router
from routers.whatsapp_router import check_ip_change

from dotenv import load_dotenv
import sys
import os

# =====================================================
# 🔧 Load environment variable dari file .env
# =====================================================
load_dotenv()
print("🔑 WABLAS TOKEN TERBACA:", os.getenv("WABLAS_API_TOKEN"))

sys.path.append(os.path.dirname(__file__))

# =====================================================
# 🚀 Inisialisasi FastAPI
# =====================================================
app = FastAPI(title="Presensi SMAN 1 Malunda")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# 📦 Daftarkan semua router
# =====================================================
app.include_router(siswa_router.router)
app.include_router(presensi_router.router)
app.include_router(notifikasi_router.router)
app.include_router(whatsapp_router.router)
app.include_router(qrcode_router.router)
app.include_router(idcard_router_bg.router)
app.include_router(user_router.router)


# =====================================================
# 🔄 Update whitelist otomatis saat aplikasi dijalankan
# =====================================================
@app.on_event("startup")
def startup_event():
    try:
        print("🌍 Mengecek perubahan IP publik...")
        check_ip_change()
    except Exception as e:
        print("❌ Gagal memeriksa IP publik:", e)


# =====================================================
# 🌐 Endpoint utama
# =====================================================
@app.get("/")
def root():
    return {
        "ok": True,
        "message": "Backend Presensi SMAN 1 Malunda aktif",
        "time": datetime.now().isoformat()
    }
