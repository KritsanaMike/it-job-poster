"""
scraper.py
STEP 2-3: ดึงรายการประกาศงานจากหน้า list แล้ว loop เข้าไปดึงรายละเอียด
แต่ละประกาศ

เว็บเป้าหมาย: https://www.xn--12c4cbf7aots1ayx.com/all-cate-prd.php?cate_id=3

หมายเหตุสำคัญ:
- selector (CSS class / tag) ด้านล่างเป็นค่าเดาเบื้องต้น ต้องปรับตาม
  HTML จริงของเว็บ (ใช้ debug_page() ด้านล่างเพื่อดู HTML ที่ดึงมาได้จริง)
- ใส่ time.sleep ระหว่าง request เพื่อไม่ให้โหลดเว็บถี่เกินไป (มารยาท + กัน block)
"""

import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.xn--12c4cbf7aots1ayx.com/all-cate-prd.php?cate_id=3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY_SECONDS = 1.5  # หน่วงเวลาระหว่างแต่ละ request


def fetch_html(url: str) -> str:
    """ดึง HTML ดิบจาก URL พร้อม error handling"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding  # กัน encoding ภาษาไทยเพี้ยน
    return resp.text


def debug_page(url: str = BASE_URL, save_path: str = "debug_list_page.html"):
    """
    ใช้ตอน setup ครั้งแรกเท่านั้น: ดึง HTML มาเซฟไว้ดู
    เพื่อหา selector ที่ถูกต้องจริงของเว็บ (เปิดไฟล์นี้ด้วย text editor
    แล้ว Ctrl+F หาคำว่า 'href' หรือชื่อประกาศงานตัวอย่าง)
    """
    html = fetch_html(url)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"บันทึก HTML ไว้ที่ {save_path} แล้ว — เปิดดูเพื่อหา selector ที่ถูกต้อง")


BASE_DOMAIN = "https://www.xn--12c4cbf7aots1ayx.com"


def _to_absolute(href: str) -> str:
    """แปลง relative path เป็น absolute URL"""
    if href.startswith("http"):
        return href
    return BASE_DOMAIN + "/" + href.lstrip("/")


def get_total_pages(list_url: str = BASE_URL) -> int:
    """
    อ่านจำนวนหน้าทั้งหมดจากข้อความ 'หน้า 1 จาก 50 | รวม 500 รายการ'
    เผื่อ pagination-meta หาไม่เจอ ให้ default = 1 หน้า (กันพัง)
    """
    html = fetch_html(list_url)
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.select_one(".pagination-meta")
    if not meta:
        return 1
    text = meta.get_text(strip=True)  # เช่น "หน้า 1 จาก 50 | รวม 500 รายการ"
    try:
        # ดึงตัวเลขหลังคำว่า "จาก"
        total = text.split("จาก")[1].split("|")[0].strip()
        return int(total)
    except (IndexError, ValueError):
        return 1


def _parse_close_date(text: str) -> date | None:
    """แปลงข้อความ เช่น 'ปิดรับ 02/10/2026' (dd/mm/yyyy ค.ศ.) เป็น date object คืน None ถ้า parse ไม่ได้"""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def get_job_links_on_page(page_url: str) -> list[dict]:
    """
    ดึงลิงก์ + ชื่อเรื่อง + วันปิดรับสมัคร ของประกาศงานทั้งหมดในหน้าเดียว
    selector จริง: <article class="listing-card"> > h3.listing-card-title > a[href]
    วันปิดรับสมัครอยู่ที่ .listing-date-note (เช่น "ปิดรับ 02/10/2026") — ดึงจากหน้า list
    ได้เลยโดยไม่ต้องเข้าไปหน้า detail ทำให้กรองประกาศที่ปิดรับสมัครแล้วออกได้เร็วตั้งแต่ต้น

    คืนค่าเป็น list ของ {"url", "title", "close_date"} — เก็บไว้ตั้งแต่ตอนนี้เพื่อให้
    main.py กรองทั้งงานที่ปิดรับสมัครแล้วและ (ในขั้นถัดไป) สาย IT ได้ก่อนเสียเวลาเข้า detail
    """
    html = fetch_html(page_url)
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    for card in soup.select("article.listing-card"):
        title_link = card.select_one("h3.listing-card-title a[href]")
        if not title_link:
            continue
        date_note = card.select_one(".listing-date-note")
        close_date = _parse_close_date(date_note.get_text(strip=True)) if date_note else None
        jobs.append({
            "url": _to_absolute(title_link["href"]),
            "title": title_link.get_text(strip=True),
            "close_date": close_date,
        })

    return jobs


def get_job_links(list_url: str = BASE_URL, max_pages: int | None = None) -> list[dict]:
    """
    ดึงรายการ {"url", "title"} ของประกาศงานทั้งหมด — loop ทุกหน้า pagination
    max_pages: จำกัดจำนวนหน้าที่จะดึง (ใช้ตอนทดสอบ) ถ้า None = ดึงทุกหน้า
    """
    total_pages = get_total_pages(list_url)
    if max_pages:
        total_pages = min(total_pages, max_pages)

    print(f"เว็บมีทั้งหมด {total_pages} หน้า")

    all_jobs = []
    for page in range(1, total_pages + 1):
        page_url = f"{BASE_URL}&page={page}" if page > 1 else list_url
        print(f"  ดึงหน้า {page}/{total_pages} ...")
        all_jobs.extend(get_job_links_on_page(page_url))
        if page < total_pages:
            time.sleep(REQUEST_DELAY_SECONDS)

    # เอาซ้ำออกตาม url (บางทีการ์ด urgent + การ์ด popular มีลิงก์เดียวกันซ้ำ)
    seen = set()
    deduped = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            deduped.append(job)
    return deduped


SOURCE_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def _extract_source_url(description: str) -> str | None:
    """
    ดึงลิงก์ต้นทาง (เว็บสมัครงานจริงของหน่วยงาน เช่น https://xxx.thaijobjob.com) จากเนื้อหา
    ประกาศ โดยตัดลิงก์ที่อยู่ภายใต้โดเมนของเว็บรวมประกาศเอง (เช่นไฟล์ PDF) ออก เพราะโพส
    Facebook ต้องแนบลิงก์ไปต้นทางจริงเท่านั้น ไม่ใช่ลิงก์ของเว็บรวมประกาศ

    ลิงก์ต้นทางบางประกาศเป็น <a href> จริง บางประกาศเป็นแค่ข้อความ URL เฉยๆ ในย่อหน้า
    (ไม่ได้ทำเป็นลิงก์) จึงต้องหาแบบ regex จาก plain text แทนการหาแค่ <a> tag
    คืนค่า None ถ้าไม่มีลิงก์เว็บเลย (เช่น ประกาศที่ให้สมัครด้วยตนเองเท่านั้น)
    """
    own_domain = BASE_DOMAIN.replace("https://", "")
    for match in SOURCE_URL_PATTERN.finditer(description):
        url = match.group().rstrip(".,)\"'”’")
        if own_domain not in url:
            return url
    return None


POSITION_LINE_PATTERN = re.compile(r"^\d*[.)]?\s*ตำแหน่ง(?!ที่)(.+)")
QUOTA_PATTERN = re.compile(r"จำนวน\s*([\d,]+)\s*อัตรา")


def _extract_position_details(description: str) -> list[dict]:
    """
    ดึงชื่อตำแหน่งพร้อมจำนวนอัตราที่รับของแต่ละตำแหน่ง จากบรรทัดที่ขึ้นต้นด้วย "ตำแหน่ง" (แต่ไม่ใช่
    หัวข้อ "ตำแหน่งที่เปิดรับสมัคร"/"ตำแหน่งที่รับเปิดรับสมัคร") แล้วไล่หาบรรทัด "จำนวน N อัตรา" ที่
    ตามหลังตำแหน่งนั้นก่อนจะเจอหัวข้อตำแหน่งถัดไป

    ใช้แยกตำแหน่งสาย IT ออกจากตำแหน่งอื่นเมื่อประกาศเดียวเปิดรับหลายตำแหน่ง (ดู filter.split_it_positions
    และ main.py) เพื่อตัดตำแหน่งที่ไม่เกี่ยวข้องออกจากโพส และปรับจำนวนอัตราให้ตรงเฉพาะตำแหน่งสายคอมพิวเตอร์
    quota เป็น None ถ้าหาบรรทัด "จำนวน...อัตรา" ของตำแหน่งนั้นไม่เจอ (เช่น เปลี่ยนรูปแบบข้อความ)
    """
    details: list[dict] = []
    current: dict | None = None

    for line in description.split("\n"):
        line = line.strip()
        m = POSITION_LINE_PATTERN.match(line)
        if m:
            current = {"name": m.group(1).strip(" :-"), "quota": None}
            details.append(current)
            continue
        if current is not None and current["quota"] is None:
            qm = QUOTA_PATTERN.search(line)
            if qm:
                current["quota"] = int(qm.group(1).replace(",", ""))

    return details


def get_job_detail(job_url: str) -> dict:
    """
    เข้าไปในแต่ละประกาศ (auto-click) แล้วดึงรายละเอียด
    selector ยืนยันแล้วจาก debug_detail_page.html (prd_id=623)
    """
    html = fetch_html(job_url)
    soup = BeautifulSoup(html, "html.parser")

    header = soup.select_one("header.job-detail-header")
    title_el = header.select_one("h1") if header else None
    title = title_el.get_text(strip=True) if title_el else "ไม่ระบุ"

    # badge เช่น "ยังเปิดรับสมัคร", "ปิดรับสมัครแล้ว", "ไม่ต้องผ่าน ก.พ."
    badges = [b.get_text(strip=True) for b in soup.select(".detail-badge-row .detail-badge")]

    # meta แถวหัวเรื่อง เช่น "อัปเดตล่าสุด ...", "เปิดรับสมัคร ...", "ปิดรับสมัคร ..."
    meta_items = [m.get_text(strip=True) for m in soup.select(".job-detail-header .job-meta .meta-item")]
    close_date = next(
        (m.replace("ปิดรับสมัคร", "", 1).strip() for m in meta_items if m.startswith("ปิดรับสมัคร")),
        None,
    )

    # เนื้อหาประกาศแบบเต็ม (การ์ดแรกใน job-detail-content)
    content_el = soup.select_one(".job-main-content")
    description = content_el.get_text("\n", strip=True) if content_el else ""
    position_details = _extract_position_details(description)
    positions = [detail["name"] for detail in position_details]
    source_url = _extract_source_url(description)

    # กล่องสรุปข้อมูลสำคัญ: วิธีสมัคร, วันที่เปิดรับสมัคร, ประเภท, เงื่อนไข ฯลฯ
    info = {}
    for item in soup.select(".job-info-box .info-item"):
        label_el = item.select_one(".info-label")
        value_el = item.select_one(".info-value")
        if label_el and value_el:
            label = label_el.get_text(strip=True).rstrip(":")
            info[label] = value_el.get_text(strip=True)

    img_el = soup.select_one(".job-image-square img[src]")
    image_url = img_el["src"] if img_el and img_el.get("src") else None

    return {
        "url": job_url,
        "title": title,
        "badges": badges,
        "meta": meta_items,
        "description": description,
        "positions": positions,
        "position_details": position_details,
        "source_url": source_url,
        "info": info,
        "image_url": image_url,
        "close_date": close_date,
    }


def scrape_all_jobs(list_url: str = BASE_URL) -> list[dict]:
    """
    ฟังก์ชันหลัก: ดึงลิงก์ทั้งหมด → loop เข้าแต่ละอัน → คืนค่าเป็น list ของ dict
    """
    print(f"กำลังดึงรายการประกาศจาก {list_url} ...")
    jobs_meta = get_job_links(list_url)
    print(f"พบลิงก์ประกาศทั้งหมด {len(jobs_meta)} รายการ")

    jobs = []
    for i, job_meta in enumerate(jobs_meta, start=1):
        link = job_meta["url"]
        print(f"  [{i}/{len(jobs_meta)}] กำลังเข้า: {link}")
        try:
            job = get_job_detail(link)
            jobs.append(job)
        except Exception as e:
            print(f"  ⚠ ดึงข้อมูลไม่สำเร็จ ({link}): {e}")
        time.sleep(REQUEST_DELAY_SECONDS)  # หน่วงเวลาไม่ให้ยิงถี่เกินไป

    return jobs


if __name__ == "__main__":
    # รันทดสอบตรงๆ: python scraper.py
    jobs_meta = get_job_links(max_pages=1)
    print(f"\nพบประกาศ {len(jobs_meta)} รายการในหน้าแรก:")
    for j in jobs_meta[:5]:
        print(f"  - {j['title']} -> {j['url']}")

    if jobs_meta:
        print("\nทดสอบดึงรายละเอียดของประกาศแรก:")
        detail = get_job_detail(jobs_meta[0]["url"])
        for key, value in detail.items():
            print(f"  {key}: {value}")
