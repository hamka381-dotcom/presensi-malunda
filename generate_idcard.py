# generate_idcard.py
from PIL import Image, ImageDraw, ImageFont
import qrcode
import io
import os
from typing import Optional

# Ukuran kartu (pixels) untuk 10cm x 7cm @300dpi
W, H = 1181, 827

LOGO_PATH = "logo.png"
FONT_PATH = None
OUTPUT_DIR = "out_cards"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Helper: Load font
# --------------------------------------------------
def load_font(size):
    if FONT_PATH and os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()

# --------------------------------------------------
# Helper: Hitung ukuran teks (Pillow 11 fix)
# --------------------------------------------------
def get_text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h

# --------------------------------------------------
# Buat gradasi biru–putih
# --------------------------------------------------
def make_gradient(width, height, start_color=(7,78,146), end_color=(245,247,250)):
    base = Image.new('RGB', (width, height), start_color)
    top = Image.new('RGB', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        a = int(255 * (y / (height-1)))
        mask_data.extend([a]*width)
    mask.putdata(mask_data)
    base.paste(top, (0,0), mask)
    return base

# --------------------------------------------------
# Bikin foto bulat
# --------------------------------------------------
def circle_crop(im, size):
    im = im.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0,0,size,size), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(im, (0,0), mask)
    return out

# --------------------------------------------------
# Generate QR
# --------------------------------------------------
def generate_qr(data, box_size=6):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img

# --------------------------------------------------
# Gambar kartu ID
# --------------------------------------------------
def draw_card(name: str,
              role: str,
              token_or_text: str,
              idnum: Optional[str] = None,
              photo_path: Optional[str] = None,
              logo_path: Optional[str] = LOGO_PATH,
              filename: Optional[str] = None):

    # Canvas dasar
    card = make_gradient(W, H, start_color=(3,70,148), end_color=(255,255,255))
    draw = ImageDraw.Draw(card)

    # Logo di atas tengah
    logo_h = 0
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = int(W * 0.18)
        ratio = logo_w / logo.width
        logo_h = int(logo.height * ratio)
        logo = logo.resize((logo_w, logo_h))
        card.paste(logo, ((W - logo_w)//2, 30), logo)

    # Nama sekolah
    font_school = load_font(36)
    text_school = "UPTD SMA NEGERI 1 MALUNDA"
    tw, th = get_text_size(draw, text_school, font_school)
    draw.text(((W - tw)//2, 50 + logo_h), text_school, fill="black", font=font_school)

    # Foto profil kiri
    photo_size = int(H * 0.42)
    photo_x, photo_y = 100, int(H * 0.25)
    if photo_path and os.path.exists(photo_path):
        p = Image.open(photo_path).convert("RGBA")
        p_circ = circle_crop(p, photo_size)
    else:
        p_circ = Image.new("RGBA", (photo_size, photo_size), (240,240,240,255))
        initials = "".join([n[0].upper() for n in name.split()[:2]]) or "?"
        f_init = load_font(int(photo_size*0.3))
        d = ImageDraw.Draw(p_circ)
        iw, ih = get_text_size(d, initials, f_init)
        d.text(((photo_size-iw)//2, (photo_size-ih)//2), initials, font=f_init, fill=(30,30,30))
    card.paste(p_circ, (photo_x, photo_y), p_circ)

    # QR kanan
    qr_data = f"PRESENSI|ROLE={role}|TOKEN={token_or_text}"
    qr_img = generate_qr(qr_data)
    qr_size = int(H * 0.4)
    qr_img = qr_img.resize((qr_size, qr_size))
    qr_x, qr_y = W - qr_size - 100, int(H * 0.27)
    card.paste(qr_img, (qr_x, qr_y), qr_img)

    # Nama & Role
    font_name = load_font(52)
    font_role = load_font(30)
    name_x = photo_x + photo_size + 50
    name_y = photo_y + 20
    draw.text((name_x, name_y), name, font=font_name, fill="black")
    role_display = role.capitalize()
    draw.text((name_x, name_y + 70), role_display, font=font_role, fill=(60,60,60))

    # ID number
    if idnum:
        font_id = load_font(24)
        draw.text((name_x, name_y + 120), f"ID: {idnum}", font=font_id, fill=(80,80,80))

    # Footer bar
    bar_h = 70
    bar = Image.new("RGBA", (W, bar_h), (7,78,146,255))
    card.paste(bar, (0, H - bar_h), bar)
    font_footer = load_font(22)
    footer_text = "Scan QR untuk presensi otomatis"
    fw, fh = get_text_size(draw, footer_text, font_footer)
    draw.text(((W - fw)//2, H - bar_h + 20), footer_text, font=font_footer, fill="white")

    # Simpan
    if not filename:
        safe = name.replace(" ", "_")
        filename = os.path.join(OUTPUT_DIR, f"{safe}_{role}.png")
    card.save(filename, dpi=(300,300))
    print(f"✅ Saved: {filename}")
    return filename

# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", default="siswa")
    parser.add_argument("--token", default="TOKEN123")
    parser.add_argument("--idnum", default=None)
    parser.add_argument("--photo", default=None)
    parser.add_argument("--logo", default=LOGO_PATH)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    draw_card(
        name=args.name,
        role=args.role,
        token_or_text=args.token,
        idnum=args.idnum,
        photo_path=args.photo,
        logo_path=args.logo,
        filename=args.out
    )
