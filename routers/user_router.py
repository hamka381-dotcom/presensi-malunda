from fastapi import APIRouter, HTTPException
from database import supabase
import uuid
from datetime import datetime

router = APIRouter(prefix="/users", tags=["User Management"])

# ===============================
# 🧠 FUNGSI BUAT TOKEN UNIK
# ===============================
def generate_token(role: str):
    prefix = "SIS" if role.lower() == "siswa" else "GUR"
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

# ===============================
# ➕ CREATE USER BARU
# ===============================
@router.post("/create")
async def create_user(user_data: dict):
    """
    Tambah user baru ke Supabase.
    Otomatis generate token presensi.
    """
    try:
        nama = user_data.get("nama")
        role = user_data.get("role", "siswa")
        no_hp = user_data.get("no_hp")
        orang_tua_phone = user_data.get("orang_tua_phone")
        nisn = user_data.get("nisn")
        nip = user_data.get("nip")
        photo_url = user_data.get("photo_url")

        if not nama:
            raise HTTPException(status_code=400, detail="Nama wajib diisi.")

        # Generate token unik
        token = generate_token(role)

        # Buat payload untuk Supabase
        data = {
            "nama": nama,
            "role": role,
            "nisn": nisn,
            "nip": nip,
            "no_hp": no_hp,
            "orang_tua_phone": orang_tua_phone,
            "photo_url": photo_url,
            "presensi_token": token,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Insert ke Supabase
        result = supabase.table("users").insert(data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Gagal menambahkan user ke database.")

        return {
            "status": True,
            "message": f"User '{nama}' berhasil ditambahkan.",
            "data": result.data[0]
        }

    except Exception as e:
        print("❌ Gagal menambahkan user:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ===============================
# 📋 GET SEMUA USER
# ===============================
@router.get("/")
async def get_all_users():
    try:
        res = supabase.table("users").select("*").execute()
        return {"count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===============================
# 🔍 GET USER BY ID
# ===============================
@router.get("/{user_id}")
async def get_user(user_id: str):
    try:
        res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===============================
# 🗑️ DELETE USER
# ===============================
@router.delete("/{user_id}")
async def delete_user(user_id: str):
    try:
        res = supabase.table("users").delete().eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        return {"status": True, "message": "User berhasil dihapus."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===============================
# ✏️ UPDATE USER
# ===============================
@router.put("/{user_id}")
async def update_user(user_id: str, update_data: dict):
    try:
        res = supabase.table("users").update(update_data).eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        return {"status": True, "message": "User berhasil diperbarui.", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
