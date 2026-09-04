"""
database.py
เช็คว่าเคยโพสประกาศนี้ไปแล้วหรือยัง (กันโพสซ้ำ) + บันทึกประกาศที่โพสแล้วลง Supabase

ตาราง `jobs` (ดู PROJECT_BRIEF.md สำหรับ SQL schema):
    id serial PRIMARY KEY,
    url text UNIQUE,
    hash text UNIQUE,
    title text,
    posted_at timestamptz DEFAULT now()
"""

import hashlib
import os

from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

TABLE_NAME = "jobs"


def get_client() -> Client:
    """สร้าง Supabase client จาก environment variable"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("ต้องตั้งค่า environment variable SUPABASE_URL และ SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def make_hash(url: str) -> str:
    """สร้าง hash จาก URL ประกาศ ใช้เป็น key กันซ้ำสำรอง (เผื่อ URL เปลี่ยนรูปแบบภายหลัง)"""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def is_already_posted(client: Client, job_url: str) -> bool:
    """เช็คว่า URL นี้เคยถูกบันทึก (โพสไปแล้ว) หรือยัง"""
    result = client.table(TABLE_NAME).select("id").eq("url", job_url).limit(1).execute()
    return len(result.data) > 0


def mark_as_posted(client: Client, job_url: str, title: str) -> None:
    """บันทึกว่าประกาศนี้โพสไปแล้ว กันไม่ให้โพสซ้ำในรอบถัดไป"""
    client.table(TABLE_NAME).insert({
        "url": job_url,
        "hash": make_hash(job_url),
        "title": title,
    }).execute()
