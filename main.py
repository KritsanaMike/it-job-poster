"""
main.py
ประกอบทุก step: scrape -> กรองสาย IT -> กันโพสซ้ำ -> เขียนโพส -> สร้างภาพ -> โพส Facebook
รันทุกวัน 08:00 น. (เวลาไทย) ผ่าน GitHub Actions cron (ดู .github/workflows/job_poster.yml)

ตอนรันในเครื่อง: อ่านค่า secrets จากไฟล์ .env (ดู .env.example) ผ่าน python-dotenv
ตอนรันบน GitHub Actions: .env จะไม่มีไฟล์ — load_dotenv() จะไม่ทำอะไร (no-op) แล้วใช้
env var ที่ workflow set มาจาก GitHub Secrets แทนโดยอัตโนมัติ
"""

import time

from dotenv import load_dotenv

load_dotenv()

# import โมดูลที่อ่าน os.environ ตอน import (database/writer/image_gen/publisher)
# ต้องมาหลัง load_dotenv() เสมอ ไม่งั้นค่าจาก .env จะยังไม่ถูกอ่าน
from database import get_client, is_already_posted, mark_as_posted
from filter import is_it_job_detail, is_open
from image_gen import generate_job_image
from notifier import request_confirmation
from publisher import post_to_facebook
from scraper import REQUEST_DELAY_SECONDS, get_job_detail, get_job_links
from writer import write_post

MAX_POSTS_PER_RUN = 5  # กันโพสรัวเกินไปในรอบเดียว เผื่อมีประกาศ IT ใหม่เข้ามาพร้อมกันหลายอัน


def main() -> None:
    db = get_client()

    print("STEP 1: ดึงลิงก์ประกาศทั้งหมด (พร้อมวันปิดรับสมัครจากหน้า list) ...")
    all_jobs = get_job_links()
    print(f"  พบประกาศทั้งหมด {len(all_jobs)} รายการ")

    print("STEP 2: กรองประกาศที่ปิดรับสมัครไปแล้วออกก่อน (เช็คจากหน้า list โดยตรง เร็วสุด ไม่มี request เพิ่ม)")
    open_jobs = [job for job in all_jobs if is_open(job.get("close_date"))]
    print(f"  เหลือประกาศที่ยังเปิดรับสมัคร {len(open_jobs)} รายการ")

    print("STEP 3: กรองประกาศที่เคยโพสไปแล้วออก (เช็คจาก DB ประหยัด request เข้า detail page)")
    new_candidates = [job for job in open_jobs if not is_already_posted(db, job["url"])]
    print(f"  เหลือประกาศใหม่ {len(new_candidates)} รายการ")

    # หมายเหตุ: ชื่อเรื่องในหน้า list เป็นแค่หัวข้อประกาศ (เช่น "[หน่วยงาน] เปิดรับสมัคร
    # พนักงานราชการทั่วไป X อัตรา") ไม่ได้มีชื่อตำแหน่งงานจริง (เช่น "นักวิชาการคอมพิวเตอร์")
    # ชื่อตำแหน่งจะอยู่ในเนื้อหาของหน้า detail เท่านั้น จึงต้องเข้าไปดึงรายละเอียดทุกอันมา
    # เช็ค is_it_job() จริงๆ ก่อน จะกรองจาก title ในหน้า list เฉยๆ ไม่ได้
    posted_count = 0
    for candidate in new_candidates:
        if posted_count >= MAX_POSTS_PER_RUN:
            print(f"ครบโควตา {MAX_POSTS_PER_RUN} โพส/รอบแล้ว หยุดที่นี่ก่อน (ที่เหลือจะโพสรอบถัดไป)")
            break

        link = candidate["url"]
        try:
            job = get_job_detail(link)
        except Exception as e:
            print(f"  ⚠ ดึงรายละเอียดไม่สำเร็จ ({link}): {e}")
            continue
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)  # หน่วงเวลาไม่ให้ยิงถี่เกินไป (เหมือน scraper.py)

        if "ปิดรับสมัครแล้ว" in job.get("badges", []):
            # เผื่อประกาศปิดรับสมัครไปพอดีระหว่างที่ run อยู่ (เช็คซ้ำแบบไม่มีต้นทุนเพิ่ม
            # เพราะข้อมูลนี้ดึงมาพร้อม get_job_detail() อยู่แล้ว)
            continue

        if not is_it_job_detail(job):
            continue

        print(f"พบประกาศสาย IT: {job['title']}")
        try:
            message = write_post(job)
            image_bytes = generate_job_image(job)

            print("  ⏳ ส่งไปรอยืนยันใน Discord ...")
            if not request_confirmation(job, message, image_bytes):
                print(f"  ⏭ ยกเลิกโพสนี้ (ไม่ได้รับการยืนยันใน Discord): {job['title']}")
                continue

            post_to_facebook(message, image_bytes)
            mark_as_posted(db, link, job["title"])
            posted_count += 1
            print(f"  ✅ โพสสำเร็จ: {job['title']}")
        except Exception as e:
            print(f"  ⚠ โพสไม่สำเร็จ ({link}): {e}")

    print(f"\nเสร็จสิ้น: โพสไปทั้งหมด {posted_count} รายการ")


if __name__ == "__main__":
    main()
