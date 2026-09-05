"""
test_font.py
สคริปต์ทดสอบเฉพาะขั้นตอนสร้างภาพ (image_gen.py) แยกออกจาก pipeline หลัก
ใช้ debug ปัญหาภาษาไทยเพี้ยนบน GitHub Actions โดยไม่ต้องพึ่ง Gemini/Discord/Facebook
(ซึ่งติด quota/ต้องรอ confirm) — รันแล้วเซฟภาพเป็น font_test_output.png ให้ดาวน์โหลดมาดูตรงๆ
"""

from image_gen import generate_job_image

dummy_job = {
    "title": "หน่วยงานทดสอบ เปิดรับสมัครพนักงานราชการทั่วไป 5 อัตรา",
    "positions": ["นักวิชาการคอมพิวเตอร์", "เจ้าหน้าที่ระบบเครือข่าย"],
    "description": "ทดสอบภาษาไทย เงินเดือน 15,000 บาท คุณสมบัติ ปริญญาตรี สาขาคอมพิวเตอร์",
    "close_date": "30/09/2026",
    "info": {
        "วันที่เปิดรับสมัคร": "01/09/2026 - 30/09/2026",
        "วิธีการสมัคร": "สมัครออนไลน์ผ่านเว็บไซต์หน่วยงาน",
    },
}

image_bytes = generate_job_image(dummy_job)
with open("font_test_output.png", "wb") as f:
    f.write(image_bytes)
print(f"บันทึกภาพทดสอบไว้ที่ font_test_output.png ({len(image_bytes)} bytes)")
