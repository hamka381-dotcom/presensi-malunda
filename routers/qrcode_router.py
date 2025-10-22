from PIL import Image, ImageDraw, ImageFont
from zipfile import ZipFile
import tempfile
import os
import io
import qrcode
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database import supabase

router = APIRouter(prefix="/qrcode", tags=["QR Code Generator"])

LOGO_PATH = "assets/logo.png"  # ganti sesuai lokasi logo kamu

@router.get("/bulk")
async def generate_bulk_qrcode():
    """
    Generate QR Code untuk SEMUA pengguna dengan nama, role, dan logo sekolah.
    """
    try:
        users = supabase.table("users").select("id, nama, role, presensi_token").execute().data
        if not users:
            raise HTTPException(status_code=404, detail="Tidak ada data user ditemukan.")

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "qrcode_users.zip")

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((100, 100))  # kecilkan biar pas di QR

        # Gunakan font default (atau ganti pakai font custom)
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        with ZipFile(zip_path, "w") as zipf:
            for user in users:
                nama = user.get("nama", "Tanpa_Nama")
                nama_file = nama.replace(" ", "_")
                role = user.get("role", "unknown").capitalize()
                token = user.get("presensi_token")

                if not token:
                    continue

                # --- Buat QR utama ---
                qr_data = f"PRESENSI|ROLE={role}|TOKEN={token}"
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

                # --- Tempel logo di tengah QR ---
                qr_width, qr_height = qr_img.size
                logo_size = 100
                logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                qr_img.paste(logo, logo_pos, logo)

                # --- Tambahkan nama & role di bawah QR ---
                new_height = qr_height + 80
                final_img = Image.new("RGBA", (qr_width, new_height), "white")
                final_img.paste(qr_img, (0, 0))

                draw = ImageDraw.Draw(final_img)
                text = f"{nama} | {role}"
                text_width = draw.textlength(text, font=font)
                draw.text(
                    ((qr_width - text_width) // 2, qr_height + 20),
                    text,
                    font=font,
                    fill="black"
                )

                # --- Simpan & masukkan ke ZIP ---
                img_path = os.path.join(temp_dir, f"{role}_{nama_file}.png")
                final_img.save(img_path)
                zipf.write(img_path, arcname=f"{role}_{nama_file}.png")

        # Kembalikan ZIP ke browser
        zip_file = open(zip_path, "rb")
        return StreamingResponse(zip_file, media_type="application/zip", headers={
            "Content-Disposition": "attachment; filename=qrcode_users.zip"
        })

    except Exception as e:
        print("❌ Gagal generate QR massal:", e)
        raise HTTPException(status_code=500, detail=str(e))
