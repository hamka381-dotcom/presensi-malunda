from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database import supabase
from PIL import Image, ImageDraw, ImageFont
import qrcode
import io
import os
from zipfile import ZipFile
import tempfile
import requests

router = APIRouter(prefix="/idcard", tags=["ID Card Generator (Final)"])

# ==============================
# 📐 KONFIGURASI DASAR
# ==============================
W, H = 591, 1004  # 300 DPI
DPI = 300
MM_TO_PX = 11.811  # 1 mm ≈ 11.811 px @300dpi

def mm(val):
    return int(val * MM_TO_PX)

# ==============================
# 📂 ASSETS & FONT
# ==============================
BG_PATH = "assets/idcard_bg.png"
LOGO_PATH = "assets/logo/logo.png"
FONT_MONTSERRAT = "assets/fonts/Montserrat-Regular.ttf"
FONT_POPPINS = "assets/fonts/Poppins-Bold.ttf"

COLOR_BLACK = "#1a1a1a"
COLOR_WHITE = "#ffffff"

# ==============================
# ⚙️ HELPER FUNCTIONS
# ==============================
def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def get_text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def generate_qr(data, box_size=6):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGBA")

# ==============================
# 🧠 GENERATOR ID CARD
# ==============================
def generate_idcard_image(name, role, idnum, token, photo_path=None):
    if not os.path.exists(BG_PATH):
        raise FileNotFoundError("❌ Background ID card (idcard_bg.png) tidak ditemukan.")

    card = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(card)

    # 🏫 LOGO SEKOLAH
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((mm(8), mm(7.38)))
        card.paste(logo, (mm(21), mm(5.89)), logo)

    # 🏷️ JUDUL
    font_title = load_font(FONT_MONTSERRAT, 27)
    font_school = load_font(FONT_MONTSERRAT, 27)
    draw.text((mm(7.7), mm(14.61)), "KARTU PRESENSI", fill=COLOR_BLACK, font=font_title)
    draw.text((mm(7.7), mm(17.01)), "UPTD SMA NEGERI 1 MALUNDA", fill=COLOR_BLACK, font=font_school)

    # 👤 FOTO (CINCIN)
    ring_w, ring_h = mm(24.15), mm(24.15)
    ring_x, ring_y = mm(12.92), mm(19.66)

    ring = Image.new("RGBA", (ring_w, ring_h), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(ring)
    rdraw.ellipse((0, 0, ring_w, ring_h), fill="#1f365a")
    rdraw.ellipse((mm(1.5), mm(1.5), ring_w - mm(1.5), ring_h - mm(1.5)), fill=(255, 255, 255, 0))

    photo_size = ring_w - mm(3)
    if photo_path and os.path.exists(photo_path):
        p = Image.open(photo_path).convert("RGBA").resize((photo_size, photo_size))
    else:
        p = Image.new("RGBA", (photo_size, photo_size), (240, 240, 240, 255))
        d = ImageDraw.Draw(p)
        initials = "".join([x[0].upper() for x in name.split()[:2]])
        f_init = load_font(FONT_POPPINS, 80)
        iw, ih = get_text_size(d, initials, f_init)
        d.text(((photo_size - iw) / 2, (photo_size - ih) / 2), initials, font=f_init, fill="#1f365a")

    mask = Image.new("L", (photo_size, photo_size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, photo_size, photo_size), fill=255)
    card.paste(ring, (ring_x, ring_y), ring)
    card.paste(p, (ring_x + mm(1.5), ring_y + mm(1.5)), mask)

    # 🧾 TEKS (NAMA, ROLE, ID)
    font_name = load_font(FONT_POPPINS, 50)
    font_info = load_font(FONT_MONTSERRAT, 35)
    draw.text((mm(8.11), mm(51.52)), name.upper(), fill=COLOR_WHITE, font=font_name)
    draw.text((mm(11.97), mm(59.59)), role.capitalize(), fill=COLOR_WHITE, font=font_info)
    id_label = f"NIP: {idnum}" if role.lower() == "guru" else f"NISN: {idnum}"
    draw.text((mm(10.2), mm(62.08)), id_label, fill=COLOR_WHITE, font=font_info)

    # 🔲 QR CODE
    qr_data = f"PRESENSI|ROLE={role}|TOKEN={token}"
    qr_img = generate_qr(qr_data)
    qr_img = qr_img.resize((mm(12.45), mm(12.1)))
    card.paste(qr_img, (mm(18.77), mm(65.8)), qr_img)

    # 📍 FOOTER
    font_footer = load_font(FONT_MONTSERRAT, 25)
    draw.text((mm(7.34), mm(78.8)), "Jl. Poros Majene-Mamuju Km. 85", fill=COLOR_WHITE, font=font_footer)

    buf = io.BytesIO()
    card.save(buf, format="PNG", dpi=(DPI, DPI))
    buf.seek(0)
    return buf

# ==============================
# 📦 ENDPOINT BULK ZIP
# ==============================
@router.get("/bulk")
async def generate_bulk_idcards(role: str = None):
    """
    Generate ID Card massal (ZIP)
    Contoh:
      /idcard/bulk
      /idcard/bulk?role=siswa
      /idcard/bulk?role=guru
    """
    try:
        query = supabase.table("users").select("*")
        if role:
            query = query.eq("role", role.lower())
        users = query.execute().data

        if not users:
            raise HTTPException(status_code=404, detail=f"Tidak ada user dengan role {role or 'semua'} ditemukan.")

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"idcards_{role or 'all'}.zip")

        with ZipFile(zip_path, "w") as zipf:
            for user in users:
                name = user.get("nama", "Tanpa Nama")
                role_user = user.get("role", "unknown")
                token = user.get("presensi_token", "TOKEN_TIDAK_ADA")
                idnum = user.get("nip") if role_user == "guru" else user.get("nisn", "Belum diisi")

                # Ambil foto user dari Supabase URL (kalau ada)
                photo_url = user.get("photo_url")
                photo_path = None
                if photo_url:
                    try:
                        img_data = requests.get(photo_url).content
                        photo_path = os.path.join(temp_dir, f"{name}.png")
                        with open(photo_path, "wb") as f:
                            f.write(img_data)
                    except Exception as e:
                        print(f"⚠️ Gagal download foto {name}: {e}")

                buf = generate_idcard_image(name, role_user, idnum, token, photo_path)
                filename = f"{role_user}_{name.replace(' ', '_')}.png"
                card_path = os.path.join(temp_dir, filename)
                with open(card_path, "wb") as f:
                    f.write(buf.getvalue())
                zipf.write(card_path, arcname=filename)

        zip_file = open(zip_path, "rb")
        return StreamingResponse(zip_file, media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=idcards_{role or 'all'}.zip"
        })

    except Exception as e:
        print("❌ Gagal generate ID Card massal:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ==============================
# 🧍‍♂️ ENDPOINT INDIVIDU
# ==============================
@router.get("/single/{user_id}")
async def get_idcard(user_id: str, download: bool = False):
    """
    Generate ID Card untuk 1 user.
    Jika ?download=true maka auto-download, kalau tidak maka tampil preview di browser.
    """
    try:
        user_res = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        user = user_res.data[0]
        name = user.get("nama", "Tanpa Nama")
        role = user.get("role", "unknown")
        token = user.get("presensi_token", "TOKEN_TIDAK_ADA")
        idnum = user.get("nip") if role == "guru" else user.get("nisn", "Belum diisi")

        # Ambil foto user
        photo_url = user.get("photo_url")
        photo_path = None
        if photo_url:
            try:
                img_data = requests.get(photo_url).content
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_file.write(img_data)
                temp_file.close()
                photo_path = temp_file.name
            except Exception as e:
                print(f"⚠️ Gagal ambil foto {name}: {e}")
                
        image_bytes = generate_idcard_image(name, role, idnum, token, photo_path)

        if download:
            # 📦 Mode download
            return StreamingResponse(
                image_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"attachment; filename={name.replace(' ', '_')}_idcard.png"
                },
            )
        else:
            # 👁️ Mode preview (langsung tampil di browser)
            return StreamingResponse(image_bytes, media_type="image/png")

    except Exception as e:
        print("❌ Gagal generate ID Card:", e)
        raise HTTPException(status_code=500, detail=str(e))

