"""
publisher.py
โพสรูปภาพ + ข้อความ ลง Facebook Page ผ่าน Graph API
"""

import os

import requests

FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_TOKEN = os.environ.get("FB_TOKEN")

GRAPH_API_VERSION = "v26.0"


def _get_page_access_token() -> str:
    """
    FB_TOKEN อาจเป็น User Access Token (ที่ user เป็นแอดมินของเพจ) หรือ Page Access Token ก็ได้
    Facebook Graph API ต้องใช้ Page Access Token ในการโพสลงเพจเสมอ — ฟังก์ชันนี้แลก
    FB_TOKEN เป็น page token ให้อัตโนมัติ (ถ้า FB_TOKEN เป็น page token อยู่แล้ว จะได้ค่าเดิมกลับมา)
    """
    resp = requests.get(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{FB_PAGE_ID}",
        params={"fields": "access_token", "access_token": FB_TOKEN},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_to_facebook(message: str, image_bytes: bytes) -> dict:
    """
    โพสรูปพร้อมข้อความลง Facebook Page ในคำขอเดียว
    endpoint: POST /{page-id}/photos (แนบไฟล์ผ่าน multipart + caption)
    """
    if not FB_PAGE_ID or not FB_TOKEN:
        raise RuntimeError("ต้องตั้งค่า environment variable FB_PAGE_ID และ FB_TOKEN")

    page_token = _get_page_access_token()
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{FB_PAGE_ID}/photos"

    resp = requests.post(
        url,
        params={"access_token": page_token},
        data={"caption": message},
        files={"source": ("job.png", image_bytes, "image/png")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
