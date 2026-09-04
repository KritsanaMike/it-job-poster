# Project brief: ระบบ auto-post ประกาศงาน (สาย IT) ลง Facebook

## เป้าหมาย
สร้างระบบอัตโนมัติที่รันทุกวัน 08:00 น. (เวลาไทย) บน **GitHub Actions** (ฟรี 100%) เพื่อ:
1. ดึงประกาศงานจากเว็บเป้าหมาย (ดูด้านล่าง)
2. กรองเฉพาะตำแหน่งงานสายคอมพิวเตอร์/IT เท่านั้น
3. เช็คว่าเคยโพสไปแล้วหรือยัง (กันโพสซ้ำ)
4. เขียนโพส + สร้างภาพประกาศงานด้วย AI
5. โพสลง Facebook Page อัตโนมัติ

**ข้อกำหนดสำคัญ: ทุกเครื่องมือต้องฟรี (free tier) ทั้งหมด**

---

## เว็บเป้าหมาย (ใช้เว็บนี้เท่านั้น)

```
https://www.xn--12c4cbf7aots1ayx.com/all-cate-prd.php?cate_id=3
```

เป็นเว็บประกาศงานราชการ/หน่วยงานทั่วไป (ไม่ได้แยกหมวด IT) ต้องกรองด้วย keyword เอง
มี pagination 50 หน้า (~500 รายการ) ต้อง loop ทุกหน้าและคลิกเข้าไปดูรายละเอียด
แต่ละประกาศด้วย (auto-click)

### โครงสร้าง HTML หน้า List (ยืนยันแล้วจาก HTML จริง)
```html
<article class="listing-card">
    <h3 class="listing-card-title">
        <a href="/prd-detail.php?prd_id=623">ชื่อตำแหน่งงาน...</a>
    </h3>
    <p class="listing-card-summary">...</p>
    <div class="listing-chip-row">
        <span class="job-tag type">...</span>
        <span class="job-tag exam-req">...</span>
        <span class="job-tag education">...</span>
    </div>
    <div class="listing-card-footer">...</div>
</article>
```

Pagination: `<div class="pagination-meta">หน้า 1 จาก 50 | รวม 500 รายการ</div>`
ลิงก์หน้าถัดไป: `?cate_id=3&page=2`, `?cate_id=3&page=3` ฯลฯ

### โครงสร้างหน้า Detail
**ยังไม่ได้ inspect — ต้องดึง HTML จริงมาดูก่อนเขียน parser ของหน้านี้**
(URL pattern: `/prd-detail.php?prd_id={id}`)

---

## สถาปัตยกรรมที่ตกลงกันไว้

| Layer | เครื่องมือ | หน้าที่ | Free tier |
|---|---|---|---|
| Trigger | GitHub Actions Cron | รันทุก 08:00 น. ไทย (`0 1 * * *` UTC) | 2,000 นาที/เดือน |
| Scraper | Python `requests` + `BeautifulSoup4` | ดึงรายการ + loop เข้าแต่ละประกาศ | ฟรี |
| Filter | Python keyword matching | กรองเฉพาะ title ที่มีคำสาย IT | ฟรี |
| Database | Supabase (PostgreSQL) | เก็บ URL/hash กันโพสซ้ำ | ฟรี 500MB |
| เขียนโพส | **Gemini API** (`gemini-2.0-flash`) | เขียน caption + hashtag ภาษาไทย | ฟรี 1,500 req/วัน |
| สร้างภาพ | **Gemini API** (Imagen 3) หรือ Python `Pillow` (fallback ฟรี 100%) | สร้างภาพประกาศงาน | ฟรี |
| โพส | Facebook Graph API | โพสรูป + ข้อความลง Page | ฟรี |

**หมายเหตุ:** เดิมวางแผนใช้ Claude API + Placid.app แต่เปลี่ยนมาใช้ **Gemini API แทนทั้งสองจุด**
(เขียนโพส และสร้างภาพ) เพราะมี free tier ที่กว้างกว่า

---

## โครงสร้างไฟล์ที่ต้องการ

```
it-job-poster/
├── .github/workflows/
│   └── job_poster.yml       ← cron trigger + secrets + run steps
├── scraper.py                ← มีแล้ว (ดูด้านล่าง) - ดึง list + loop detail
├── filter.py                 ← ยังไม่มี - กรอง keyword สาย IT
├── database.py                ← ยังไม่มี - Supabase เช็คซ้ำ + insert
├── writer.py                  ← ยังไม่มี - Gemini เขียนโพส
├── image_gen.py                ← ยังไม่มี - Gemini/Pillow สร้างภาพ
├── publisher.py                ← ยังไม่มี - Facebook Graph API โพส
├── main.py                      ← ยังไม่มี - ประกอบทุก step
└── requirements.txt
```

### requirements.txt
```
requests
beautifulsoup4
supabase
google-generativeai
Pillow
```

### GitHub Secrets ที่ต้องตั้งไว้
```
SUPABASE_URL
SUPABASE_KEY
GEMINI_API_KEY
FB_PAGE_ID
FB_TOKEN
```

### Supabase table schema
```sql
CREATE TABLE jobs (
    id serial PRIMARY KEY,
    url text UNIQUE,
    hash text UNIQUE,
    title text,
    posted_at timestamptz DEFAULT now()
);
```

---

## Keyword filter สำหรับสาย IT (ตัวอย่างเบื้องต้น ปรับได้)
```python
IT_KEYWORDS = [
    "developer", "programmer", "โปรแกรมเมอร์", "data", "ข้อมูล",
    "software", "ซอฟต์แวร์", "devops", "network", "เครือข่าย",
    "system", "ระบบคอมพิวเตอร์", "IT", "คอมพิวเตอร์", "cloud",
    "python", "java", "นักวิเคราะห์ระบบ", "เจ้าหน้าที่คอมพิวเตอร์",
    "นักวิชาการคอมพิวเตอร์", "cyber", "security"
]
```

---

## สิ่งที่ทำไปแล้ว — `scraper.py` (แนบไฟล์นี้ในโปรเจกต์)

ไฟล์นี้มี:
- `fetch_html()` — ดึง HTML พร้อม User-Agent + encoding แก้ภาษาไทยเพี้ยน
- `get_total_pages()` — อ่านจำนวนหน้าทั้งหมดจาก `.pagination-meta`
- `get_job_links_on_page()` — ดึงลิงก์ประกาศจากหน้าเดียว (selector ยืนยันแล้ว)
- `get_job_links()` — loop ทุกหน้า, dedup ลิงก์ซ้ำ
- `get_job_detail()` — **ยังใช้ selector เดา (placeholder) ต้องแก้เมื่อมี HTML หน้า detail จริง**
- `scrape_all_jobs()` — ฟังก์ชันหลักรวมทุกอย่าง

**สิ่งที่ยังไม่เสร็จ / ต้องทำต่อ:**
1. Inspect HTML หน้า detail จริง (`/prd-detail.php?prd_id=xxx`) แล้วแก้ `get_job_detail()`
2. เขียน `filter.py`, `database.py`, `writer.py`, `image_gen.py`, `publisher.py`, `main.py`
3. เขียน `.github/workflows/job_poster.yml`
4. ทดสอบ end-to-end

---

## ข้อควรระวัง
- เว็บเป้าหมายอาจ block ถ้ายิง request ถี่เกินไป → มี `time.sleep(1.5)` ระหว่าง request แล้ว
- ต้องใส่ `User-Agent` header เสมอ (ใส่แล้วใน scraper.py)
- Facebook Page Access Token หมดอายุ 60 วัน (long-lived) → ควรใช้ System User Token ถ้ามี Business Manager
- Gemini Imagen 3 free tier อาจไม่รองรับบาง region → มี Pillow เป็น fallback
