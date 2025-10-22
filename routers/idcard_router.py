from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database import supabase
from PIL import Image, ImageDraw, ImageFont
import qrcode
import io
import os

router = APIRouter(prefix="/idcard", tags=["ID Card Generator"])

# ==============================
# 🔧 Konfigurasi Dasar
# ==============================
W, H = 827, 1181  # 7x10 cm (portrait @300dpi)
LOGO_PATH = "assets/logo/logo.png"

# Font paths (pastikan file ini ada di folder yang sama)
FONT_MONTSERRAT = "assets/fonts/Montserrat-Regular.ttf"
FONT_POPPINS = "assets/fonts/Poppins-Bold.ttf"


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def get_text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h


# ==============================
# 🎨 Background Desain Modern
# ==============================
def make_modern_background():
    """
    Membuat background ID Card mirip Canva style:
    - Background putih
    - Gradasi biru halus di bagian atas dan bawah
    - Garis aksen di sisi kiri
    """
    bg = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(bg)

    # Gradient biru muda di atas
    for y in range(int(H * 0.3)):
        color = (int(255 - y * 0.5), int(255 - y * 1.2), 255)
        draw.line([(0, y), (W, y)], fill=color)

    # Gradient biru muda di bawah
    for y in range(int(H * 0.7), H):
        ratio = (y - H * 0.7) / (H * 0.3)
        color = (230 - int(ratio * 80), 240 - int(ratio * 50), 255)
        draw.line([(0, y), (W, y)], fill=color)

    # Garis aksen di sisi kiri
    accent_color = (0, 85, 170)
    draw.rectangle([(0, 0), (20, H)], fill=accent_color)

    return bg


# ==============================
# 🧩 QR Code Generator
# ==============================
def generate_qr(data, box_size=8):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGBA")


# ==============================
# 🧠 Generator ID Card Modern
# ==============================
def generate_idcard_image(name, role, idnum, token, photo_path=None):
    card = make_modern_background()
    draw = ImageDraw.Draw(card)

    # ======================
    # 🏫 Logo & Header
    # ======================
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_size = 180
        logo = logo.resize((logo_size, logo_size))
        card.paste(logo, ((W - logo_size)//2, 60), logo)

    font_school = load_font(FONT_MONTSERRAT, 32)
    school_text = "UPTD SMA NEGERI 1 MALUNDA"
    tw, th = get_text_size(draw, school_text, font_school)
    draw.text(((W - tw)/2, 60 + 180 + 15), school_text, fill=(0, 60, 130), font=font_school)

    # ======================
    # 👤 Foto / Placeholder
    # ======================
    photo_y = int(H * 0.35)
    photo_size = 280
    photo_x = (W - photo_size)//2

    if photo_path and os.path.exists(photo_path):
        p = Image.open(photo_path).convert("RGBA").resize((photo_size, photo_size))
    else:
        p = Image.new("RGBA", (photo_size, photo_size), (230, 230, 230, 255))
        d = ImageDraw.Draw(p)
        d.ellipse((0, 0, photo_size, photo_size), fill=(0, 90, 180))
        f_init = load_font(FONT_POPPINS, 100)
        initials = "".join([x[0].upper() for x in name.split()[:2]])
        iw, ih = get_text_size(d, initials, f_init)
        d.text(((photo_size - iw)/2, (photo_size - ih)/2), initials, font=f_init, fill="white")

    mask = Image.new("L", (photo_size, photo_size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, photo_size, photo_size), fill=255)
    card.paste(p, (photo_x, photo_y), mask)

    # ======================
    # 🧾 Nama & Identitas
    # ======================
    font_name = load_font(FONT_POPPINS, 60)  # setara 10pt (Poppins)
    font_info = load_font(FONT_MONTSERRAT, 36)  # setara 6pt (Montserrat)

    name_y = photo_y + photo_size + 40
    name_text = name.upper()
    tw, th = get_text_size(draw, name_text, font_name)
    draw.text(((W - tw)/2, name_y), name_text, fill=(0, 40, 90), font=font_name)

    role_text = role.capitalize()
    tw, th = get_text_size(draw, role_text, font_info)
    draw.text(((W - tw)/2, name_y + 70), role_text, fill=(30, 30, 30), font=font_info)

    id_label = f"NIP: {idnum}" if role.lower() == "guru" else f"NISN: {idnum}"
    tw, th = get_text_size(draw, id_label, font_info)
    draw.text(((W - tw)/2, name_y + 110), id_label, fill=(50, 50, 50), font=font_info)

    # ======================
    # 🔲 QR Code
    # ======================
    qr_data = f"PRESENSI|ROLE={role}|TOKEN={token}"
    qr_img = generate_qr(qr_data, box_size=6)
    qr_size = 180
    qr_img = qr_img.resize((qr_size, qr_size))
    qr_x = (W - qr_size)//2
    qr_y = name_y + 220
    card.paste(qr_img, (qr_x, qr_y), qr_img)

    # Label QR
    qr_label = "Scan QR untuk presensi otomatis"
    tw, th = get_text_size(draw, qr_label, font_info)
    draw.text(((W - tw)/2, qr_y + qr_size + 20), qr_label, fill=(80, 80, 80), font=font_info)

    # ======================
    # 📍 Footer
    # ======================
    footer_text = "Jl. Poros Majene – Mamuju Km. 85"
    tw, th = get_text_size(draw, footer_text, font_info)
    draw.rectangle([(0, H - 90), (W, H)], fill=(0, 70, 160))
    draw.text(((W - tw)/2, H - 70), footer_text, fill="white", font=font_info)

    # Simpan ke buffer
    buf = io.BytesIO()
    card.save(buf, format="PNG", dpi=(300, 300))
    buf.seek(0)
    return buf


# ==============================
# ⚡ Endpoint FastAPI
# ==============================
@router.get("/{user_id}")
async def get_idcard(user_id: str):
    """
    Generate ID Card otomatis berdasarkan data user di Supabase.
    """
    try:
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        user = user_res.data[0]
        name = user.get("nama", "Tanpa Nama")
        role = user.get("role", "unknown")
        token = user.get("presensi_token", "TOKEN_TIDAK_ADA")
        idnum = user.get("nip") if role == "guru" else user.get("nisn")
        if not idnum:
            idnum = "Belum diisi"

        image_bytes = generate_idcard_image(name, role, idnum, token)
        return StreamingResponse(image_bytes, media_type="image/png")

    except Exception as e:
        print("❌ Gagal generate ID Card:", e)
        raise HTTPException(status_code=500, detail=str(e))
