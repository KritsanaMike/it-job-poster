"""
image_gen.py
สร้างภาพ infographic ประกาศงานสำหรับโพส Facebook ด้วย Pillow ล้วนๆ (ฟรี 100% เสมอ)

หมายเหตุ: เคยลองใช้ Gemini image generation (Imagen 3 / gemini-2.5-flash-image) มาก่อน
แต่พบว่า API key แบบฟรี (ไม่เปิด billing) มี quota = 0 สำหรับสร้างภาพเสมอ (ยืนยันจาก error
จริง: "Quota exceeded ... limit: 0") ไม่ใช่แค่ rate limit ชั่วคราว จึงตัดสินใจใช้ Pillow
วาด infographic เองทั้งหมด รับประกันว่าตัวอักษรไทยถูกต้อง 100% (ต่างจาก AI image gen ที่มัก
เขียนตัวอักษรผิดเพี้ยน) และไม่มีค่าใช้จ่ายเลย
"""

import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

IMAGE_WIDTH = 1080

PAGE_BG = (247, 249, 252)
PRIMARY = (13, 71, 161)  # น้ำเงินเข้ม
PRIMARY_DARK = (9, 50, 115)
ACCENT = (245, 166, 35)  # เหลืองทอง
CARD_BG = (255, 255, 255)
CARD_BORDER = (225, 230, 238)
TEXT_DARK = (30, 41, 59)
TEXT_MUTED = (100, 116, 139)
TEXT_ON_PRIMARY = (255, 255, 255)

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# หมายเหตุ: เดิมเคยพึ่งพา apt package "fonts-thai-tlwg" บน GitHub Actions runner แต่พบว่า
# แพ็กเกจนั้น (TLWG font collection) ไม่มีไฟล์ชื่อ Sarabun.ttf อยู่จริงๆ เลยแม้แต่ไฟล์เดียว
# (Sarabun เป็นฟอนต์ของ Google Fonts คนละชุดกับ TLWG) ทำให้ path เดาทั้งหมดหาไม่เจอ แล้ว
# Pillow fallback ไปใช้ ImageFont.load_default() ซึ่งไม่รองรับภาษาไทยเลย เป็นสาเหตุที่ตัวอักษร
# ในภาพออกมาเพี้ยนเป็นภาษาต่างดาว จึงเปลี่ยนมาแนบไฟล์ฟอนต์ Sarabun จริงไว้ในโปรเจกต์เอง
# (fonts/Sarabun-Regular.ttf, fonts/Sarabun-Bold.ttf) รับประกันว่ามีอยู่จริงเสมอ ทั้งตอนรัน
# บนเครื่อง Windows และบน GitHub Actions โดยไม่ต้องพึ่ง apt-get ให้ตรงกับชื่อไฟล์ที่เดาไว้
THAI_FONT_CANDIDATES = {
    "regular": [
        os.path.join(FONTS_DIR, "Sarabun-Regular.ttf"),
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/leelawad.ttf",
    ],
    "bold": [
        os.path.join(FONTS_DIR, "Sarabun-Bold.ttf"),
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/leelawad.ttf",
    ],
}

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """หาฟอนต์ที่รองรับภาษาไทยในเครื่อง (cache ไว้กันโหลดซ้ำ)"""
    key = (weight, size)
    if key not in _font_cache:
        for path in THAI_FONT_CANDIDATES[weight]:
            if os.path.exists(path):
                _font_cache[key] = ImageFont.truetype(path, size)
                break
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """ตัดบรรทัดข้อความให้พอดีกับความกว้างที่กำหนด โดยวัดความกว้างจริงของตัวอักษร (ไม่ใช่นับตัวอักษร)"""
    lines = []
    current = ""
    for ch in text:
        candidate = current + ch
        if draw.textlength(candidate, font=font) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_gradient_band(img: Image.Image, box: tuple[int, int, int, int], top: tuple, bottom: tuple) -> None:
    """วาดแถบพื้นหลังไล่สี (แนวตั้ง) — ใช้ทำแถบหัว/ท้ายภาพให้ดูมีมิติ"""
    x0, y0, x1, y1 = box
    height = max(y1 - y0, 1)
    band = Image.new("RGB", (1, height))
    for i in range(height):
        t = i / max(height - 1, 1)
        color = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
        band.putpixel((0, i), color)
    band = band.resize((x1 - x0, height))
    img.paste(band, (x0, y0))


def _rounded_rect(draw: ImageDraw.ImageDraw, box: tuple, radius: int, fill=None, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _extract_salary(description: str) -> str | None:
    """ดึงเงินเดือนจากเนื้อหาประกาศ (รูปแบบ "เงินเดือน X บาท") — คืนค่า None ถ้าไม่เจอ"""
    matches = re.findall(r"เงินเดือน\s*([\d,]+(?:\.\d{1,2})?)\s*บาท", description)
    if not matches:
        return None
    unique = list(dict.fromkeys(matches))
    return " / ".join(f"{amount} บาท" for amount in unique[:3])


def _card_height(draw: ImageDraw.ImageDraw, value: str, width: int, margin: int) -> int:
    """คำนวณความสูงของการ์ดข้อมูล 1 แถว ล่วงหน้า (ใช้ตอนวัดความสูงรวมของภาพก่อนสร้าง canvas จริง)"""
    value_font = _font("bold", 38)
    value_lines = _wrap_text(draw, value, value_font, width - margin * 2 - 60)
    return 46 + len(value_lines) * 48 + 24


def _draw_info_card(
    draw: ImageDraw.ImageDraw,
    y: int,
    width: int,
    margin: int,
    label: str,
    value: str,
) -> int:
    """วาดการ์ดข้อมูล 1 แถว (แถบสีซ้าย + label + value) คืนค่า y ถัดไปหลังวาดเสร็จ"""
    label_font = _font("regular", 30)
    value_font = _font("bold", 38)

    value_lines = _wrap_text(draw, value, value_font, width - margin * 2 - 60)
    card_height = 46 + len(value_lines) * 48 + 24

    box = (margin, y, width - margin, y + card_height)
    _rounded_rect(draw, box, radius=18, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.rectangle((margin, y, margin + 8, y + card_height), fill=ACCENT)

    text_x = margin + 34
    draw.text((text_x, y + 16), label, font=label_font, fill=TEXT_MUTED)
    line_y = y + 54
    for line in value_lines:
        draw.text((text_x, line_y), line, font=value_font, fill=TEXT_DARK)
        line_y += 48

    return y + card_height + 22


def _collect_fields(job: dict) -> list[tuple[str, str]]:
    """รวบรวม field ที่จะแสดงเป็นการ์ดข้อมูล จาก job dict (ข้ามฟิลด์ที่ไม่มีข้อมูล)"""
    info = job.get("info", {})
    salary = _extract_salary(job.get("description", ""))

    fields = []
    if salary:
        fields.append(("เงินเดือน", salary))
    if info.get("วันที่เปิดรับสมัคร"):
        fields.append(("วันที่เปิดรับสมัคร", info["วันที่เปิดรับสมัคร"]))
    if job.get("close_date"):
        fields.append(("ปิดรับสมัคร", job["close_date"]))
    if info.get("วิธีการสมัคร"):
        fields.append(("วิธีการสมัคร", info["วิธีการสมัคร"]))
    if info.get("เงื่อนไข"):
        fields.append(("เงื่อนไข", info["เงื่อนไข"]))
    return fields


def _generate_with_pillow(job: dict) -> bytes:
    """
    สร้างภาพ infographic ประกาศงานจากข้อมูลจริงของ job (title, positions, info, close_date)
    ความสูงของภาพคำนวณจากเนื้อหาจริงก่อนสร้าง canvas (ป้องกันพื้นที่ว่างเหลือเมื่อมีข้อมูลน้อย
    หรือข้อความล้นเมื่อมีข้อมูลเยอะ)
    """
    width = IMAGE_WIDTH
    margin = 60
    header_height = 210
    footer_height = 90

    # pass 1: วัดขนาดเนื้อหาก่อน ด้วย dummy draw (textlength ไม่ขึ้นกับขนาดภาพจริง)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    tag_font = _font("bold", 32)
    agency_font = _font("regular", 30)
    position_font = _font("bold", 50)

    agency_lines = _wrap_text(measure, job.get("title", ""), agency_font, width - 120)[:2]
    positions = job.get("positions") or [job.get("title", "ไม่ระบุตำแหน่ง")]
    position_text = " • ".join(positions[:3])
    position_lines = _wrap_text(measure, position_text, position_font, width - 120)[:4]

    fields = _collect_fields(job)
    # +22 ต่อการ์ด คือช่องว่างระหว่างการ์ด (ตรงกับที่ _draw_info_card คืนค่า y + card_height + 22 จริง)
    cards_height = sum(_card_height(measure, value, width, margin) + 22 for _, value in fields)

    # หมายเหตุ: agency_lines วาดอยู่ "ภายใน" แถบ header (คงที่ header_height) ไม่ใช่ต่อท้ายด้านล่าง
    # จึงไม่นับความสูงของ agency_lines ซ้ำในสูตรนี้ (ต้องตรงกับตำแหน่งวาดจริงด้านล่างเป๊ะๆ)
    content_top = header_height + 30 + len(position_lines) * 62 + 20
    total_height = content_top + cards_height + 30 + footer_height

    # pass 2: วาดจริงบน canvas ที่คำนวณความสูงพอดีแล้ว
    img = Image.new("RGB", (width, int(total_height)), color=PAGE_BG)
    _draw_gradient_band(img, (0, 0, width, header_height), PRIMARY, PRIMARY_DARK)
    draw = ImageDraw.Draw(img)

    draw.text((60, 50), "ประกาศรับสมัครงาน", font=tag_font, fill=TEXT_ON_PRIMARY)
    tag_text = "สายไอที"
    tag_w = draw.textlength(tag_text, font=tag_font) + 50
    _rounded_rect(draw, (width - 60 - tag_w, 45, width - 60, 105), radius=28, fill=ACCENT)
    draw.text((width - 60 - tag_w + 25, 55), tag_text, font=tag_font, fill=PRIMARY_DARK)

    y = 130
    for line in agency_lines:
        draw.text((60, y), line, font=agency_font, fill=TEXT_ON_PRIMARY)
        y += 38

    y = header_height + 30
    for line in position_lines:
        draw.text((60, y), line, font=position_font, fill=PRIMARY)
        y += 62

    y += 20
    for label, value in fields:
        y = _draw_info_card(draw, y, width, margin, label, value)

    footer_top = int(total_height) - footer_height
    _draw_gradient_band(img, (0, footer_top, width, int(total_height)), PRIMARY_DARK, PRIMARY)
    footer_font = _font("bold", 30)
    footer_text = "งานราชการสายไอที"
    footer_w = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - footer_w) / 2, footer_top + 28), footer_text, font=footer_font, fill=TEXT_ON_PRIMARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_job_image(job: dict) -> bytes:
    """สร้างภาพ infographic ประกาศงาน คืนค่าเป็นไบต์ของไฟล์ PNG"""
    return _generate_with_pillow(job)
