"""
notifier.py
ส่งข้อความ+ภาพที่จะโพสไปแจ้งเตือนใน Discord ก่อน แล้วรอให้มีคนกด reaction ✅/❌ ยืนยัน
ก่อนจะโพสจริงลง Facebook

สถาปัตยกรรม: ระบบรันบน GitHub Actions (job ชั่วคราว ไม่มี public URL รับ webhook callback ได้)
จึงใช้วิธี Discord Bot ส่งข้อความ + ติด reaction ✅/❌ ไว้เอง แล้ว poll เช็คเป็นระยะว่ามีคนกด
หรือยัง แทนที่จะใช้ interactive button ซึ่งต้องมี server แยกต่างหากรับ callback
"""

import os
import time
from urllib.parse import quote

import requests

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID")

API_BASE = "https://discord.com/api/v10"
CONFIRM_EMOJI = "✅"
CANCEL_EMOJI = "❌"
POLL_INTERVAL_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 900  # 15 นาที — ถ้าไม่มีใคร react ทัน จะยกเลิกโพสนั้นอัตโนมัติ (ปลอดภัยไว้ก่อน)


DISCORD_MAX_RETRIES = 3


def _headers() -> dict:
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("ต้องตั้งค่า environment variable DISCORD_BOT_TOKEN")
    return {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}


def _discord_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    เรียก Discord API พร้อม retry อัตโนมัติเมื่อโดน rate limit (429)

    Discord ส่ง "retry_after" (วินาที) มาใน response body บอกว่าต้องรอนานแค่ไหนก่อนลองใหม่
    ถ้าไม่ retry ตรงนี้ การเรียกครั้งเดียว (เช่น ติด reaction) ที่โดน 429 จะ raise แล้วทำให้
    request_confirmation() ทั้งฟังก์ชัน crash และข้าม candidate นั้นไปทั้งที่ยังไม่ได้ถามเลย
    (เจอจริงใน GitHub Actions log: 429 ตอนติด reaction ❌)
    """
    resp = None
    for attempt in range(1, DISCORD_MAX_RETRIES + 1):
        resp = requests.request(method, url, headers=_headers(), **kwargs)
        if resp.status_code == 429 and attempt < DISCORD_MAX_RETRIES:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(float(retry_after) + 0.5)
            continue
        break
    resp.raise_for_status()
    return resp


def _send_message(content: str, image_bytes: bytes) -> str:
    """ส่งข้อความ+ภาพไปที่ Discord channel คืนค่า message_id"""
    if not DISCORD_CHANNEL_ID:
        raise RuntimeError("ต้องตั้งค่า environment variable DISCORD_CHANNEL_ID")

    resp = _discord_request(
        "post",
        f"{API_BASE}/channels/{DISCORD_CHANNEL_ID}/messages",
        data={"content": content},
        files={"files[0]": ("infographic.png", image_bytes, "image/png")},
        timeout=30,
    )
    return resp.json()["id"]


def _add_reaction(message_id: str, emoji: str) -> None:
    encoded = quote(emoji)
    _discord_request(
        "put",
        f"{API_BASE}/channels/{DISCORD_CHANNEL_ID}/messages/{message_id}/reactions/{encoded}/@me",
        timeout=15,
    )


def _has_human_reaction(message_id: str, emoji: str) -> bool:
    """เช็คว่า reaction นี้มีคน (ไม่ใช่บอทตัวเอง) กดหรือยัง"""
    encoded = quote(emoji)
    resp = _discord_request(
        "get",
        f"{API_BASE}/channels/{DISCORD_CHANNEL_ID}/messages/{message_id}/reactions/{encoded}",
        timeout=15,
    )
    users = resp.json()
    return any(not user.get("bot", False) for user in users)


def request_confirmation(
    job: dict,
    message: str,
    image_bytes: bytes,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """
    ส่งโพสที่จะขึ้น Facebook ไปให้ดูใน Discord ก่อน แล้วรอ react ✅/❌
    คืนค่า True = ยืนยันให้โพส, False = ยกเลิก (กด ❌ หรือหมดเวลาไม่มีใครตอบ)
    """
    notice = (
        f"**รอการยืนยันก่อนโพส** — {job.get('title', '')}\n\n"
        f"{message}\n\n"
        f"---\n"
        f"กด {CONFIRM_EMOJI} เพื่อยืนยันโพสนี้ลง Facebook หรือ {CANCEL_EMOJI} เพื่อยกเลิก "
        f"(ถ้าไม่มีใครตอบภายใน {timeout_seconds // 60} นาที จะยกเลิกอัตโนมัติ)"
    )

    message_id = _send_message(notice, image_bytes)
    _add_reaction(message_id, CONFIRM_EMOJI)
    _add_reaction(message_id, CANCEL_EMOJI)

    elapsed = 0
    while elapsed < timeout_seconds:
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

        if _has_human_reaction(message_id, CANCEL_EMOJI):
            return False
        if _has_human_reaction(message_id, CONFIRM_EMOJI):
            return True

    return False
