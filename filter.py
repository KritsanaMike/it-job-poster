"""
filter.py
กรองประกาศงานเฉพาะสายคอมพิวเตอร์/IT จาก title (และ description เสริม)
"""

import re
from datetime import date

IT_KEYWORDS = [
    "developer", "programmer", "โปรแกรมเมอร์", "data", "ข้อมูล",
    "software", "ซอฟต์แวร์", "devops", "network", "เครือข่าย",
    "system", "ระบบคอมพิวเตอร์", "IT", "คอมพิวเตอร์", "cloud",
    "python", "java", "นักวิเคราะห์ระบบ", "เจ้าหน้าที่คอมพิวเตอร์",
    "นักวิชาการคอมพิวเตอร์", "cyber", "security",
]


def is_it_job(title: str, description: str = "") -> bool:
    """เช็คว่าชื่อตำแหน่ง (หรือเนื้อหาประกาศ) มีคำที่เกี่ยวกับสาย IT หรือไม่"""
    text = f"{title} {description}"
    text_lower = text.lower()

    for keyword in IT_KEYWORDS:
        keyword_lower = keyword.lower()
        if re.search(r"[a-z]", keyword_lower):
            # คำภาษาอังกฤษ: ใช้ word boundary กันจับพลาดจากคำที่บังเอิญมีตัวอักษรซ้อนกัน
            # (เช่น keyword "it" ไม่ควรจับคำว่า "credit")
            if re.search(rf"\b{re.escape(keyword_lower)}\b", text_lower):
                return True
        else:
            # คำภาษาไทย: จับแบบ substring ตรงๆ (ภาษาไทยไม่มีช่องว่างคั่นคำ)
            if keyword in text:
                return True

    return False


def is_it_job_detail(job: dict) -> bool:
    """
    เช็คว่าประกาศนี้ (dict จาก scraper.get_job_detail) เป็นสาย IT จริงหรือไม่
    ใช้ชื่อตำแหน่งที่ parse ได้ (job["positions"]) เป็นหลัก เพราะ description เต็มมักมีคำว่า
    "คอมพิวเตอร์" ปนอยู่ในคุณสมบัติทั่วไป (เช่น "ใช้คอมพิวเตอร์ได้") ซึ่งแทบทุกตำแหน่งมีเหมือนกัน
    ถ้าเอา keyword ไปเทียบกับ description ทั้งก้อนจะกรองผิด (false positive)
    ถ้า parse ตำแหน่งไม่ได้เลย (เว็บเปลี่ยนโครงสร้าง) จะ fallback ไปเช็คจาก title แทน
    """
    positions = job.get("positions") or []
    if positions:
        return any(is_it_job(position) for position in positions)
    return is_it_job(job.get("title", ""))


def is_open(close_date: date | None) -> bool:
    """
    เช็คว่ายังเปิดรับสมัครอยู่หรือไม่ โดยเทียบ close_date กับวันที่ปัจจุบัน ณ ตอนดึงข้อมูล
    (ไม่เชื่อ label สถานะบนเว็บเฉยๆ เพราะอาจอัปเดตช้า — เทียบวันที่เองเสมอ)
    ถ้า parse วันที่ไม่ได้ (None) ถือว่ายังเปิดอยู่ (safe default ไม่กรองทิ้งทั้งที่ไม่รู้แน่ชัด)
    """
    if close_date is None:
        return True
    return close_date >= date.today()


def filter_it_jobs(jobs: list[dict]) -> list[dict]:
    """กรอง list ของ job dict (จาก scraper.get_job_detail) ให้เหลือเฉพาะสาย IT"""
    return [job for job in jobs if is_it_job_detail(job)]
