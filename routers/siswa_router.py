from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from database import supabase
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/siswa", tags=["Siswa"])

# Struktur data siswa
class Siswa(BaseModel):
    nama: str
    role: str = "siswa"
    no_hp: str

# -----------------------------
# 1️⃣ Ambil semua data siswa
# -----------------------------
@router.get("/")
def get_all_siswa():
    """Mengambil semua data siswa dari tabel users"""
    try:
        result = supabase.table("users").select("*").order("created_at", desc=True).execute()
        return {"status": "ok", "data": result.data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# -----------------------------
# 2️⃣ Tambahkan data siswa baru
# -----------------------------
@router.post("/")
def tambah_siswa(data: Siswa):
    """Menambahkan data siswa ke tabel users"""
    try:
        res = supabase.table("users").insert({
            "nama": data.nama,
            "role": data.role,
            "no_hp": data.no_hp,
            "created_at": datetime.now().isoformat()
        }).execute()

        return {"status": "success", "data": res.data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# -----------------------------
# 3️⃣ Hapus siswa berdasarkan ID (opsional)
# -----------------------------
@router.delete("/{id}")
def hapus_siswa(id: str):
    """Menghapus siswa berdasarkan id"""
    try:
        res = supabase.table("users").delete().eq("id", id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
        return {"status": "deleted", "data": res.data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
