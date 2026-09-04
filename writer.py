"""
writer.py
ใช้ Gemini API เขียนโพส Facebook (แคปชั่น + hashtag ภาษาไทย) จากข้อมูลประกาศงาน
"""

import os

from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.6-flash"

_client = None

PROMPT_TEMPLATE = """\
คุณคือแอดมินเพจ Facebook ที่รวบรวมประกาศรับสมัครงานสายไอที/คอมพิวเตอร์ในหน่วยงานราชการ
ช่วยเขียนโพสประกาศงานนี้ให้น่าสนใจ กระชับ อ่านง่าย เหมาะกับโพสลง Facebook

ข้อมูลประกาศ:
ชื่อเรื่อง: {title}
รายละเอียด: {description}
วันที่ปิดรับสมัคร: {close_date}
{link_instruction}

กติกาการเขียน:
- ใช้ภาษาไทย น้ำเสียงเป็นกันเอง กระตุ้นให้คนสนใจสมัคร
- สรุปตำแหน่ง คุณสมบัติ และวันปิดรับสมัครแบบย่อ ไม่ต้องคัดลอกทั้งหมด
- ปิดท้ายด้วย hashtag ภาษาไทย/อังกฤษ 4-6 อัน ที่เกี่ยวกับงานราชการสายไอที (เช่น #งานราชการ #สายไอที)
- ความยาวรวมไม่เกิน 600 ตัวอักษร
- ตอบกลับเฉพาะข้อความโพส ห้ามใส่คำอธิบายอื่น
"""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("ต้องตั้งค่า environment variable GEMINI_API_KEY")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def write_post(job: dict) -> str:
    """
    สร้างข้อความโพส Facebook จากข้อมูลประกาศงาน (dict จาก scraper.get_job_detail)

    ใช้ job["source_url"] (ลิงก์ต้นทางของหน่วยงานจริง) เท่านั้น ห้ามใช้ job["url"] ซึ่งเป็น
    ลิงก์ของเว็บรวมประกาศเอง — ถ้าประกาศนั้นไม่มีลิงก์สมัครออนไลน์เลย (เช่น ต้องสมัครด้วย
    ตนเอง) จะไม่ใส่ลิงก์ใดๆ ในโพส แทน
    """
    client = _get_client()

    source_url = job.get("source_url")
    if source_url:
        link_instruction = (
            f"ลิงก์สมัคร/ดูรายละเอียดเพิ่มเติม: {source_url}\n"
            "- ใส่ลิงก์นี้ไว้ท้ายโพส (ห้ามใช้หรือแต่งลิงก์อื่นขึ้นมาเอง)"
        )
    else:
        link_instruction = (
            "ไม่มีลิงก์สมัครออนไลน์ (ต้องสมัครด้วยตนเองหรือช่องทางอื่นตามที่ระบุในรายละเอียด)\n"
            "- ห้ามใส่ลิงก์ใดๆ ในโพส ให้สรุปวิธี/สถานที่สมัครจากเนื้อหาแทน"
        )

    prompt = PROMPT_TEMPLATE.format(
        title=job.get("title", ""),
        description=job.get("description", "")[:1500],
        close_date=job.get("close_date") or "ไม่ระบุ",
        link_instruction=link_instruction,
    )

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text.strip()
