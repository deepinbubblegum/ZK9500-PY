import os
import logging
from PIL import Image
from typing import Optional

# ตั้งค่า Logger
logger = logging.getLogger(__name__)

def decode_from_bytes(raw_data: bytes) -> Optional[Image.Image]:
    """
    แปลงข้อมูล bytes ที่ได้จากเครื่องสแกน ให้เป็นรูปภาพ (PIL Image) ทันที
    """
    data_len = len(raw_data)
    logger.debug(f"📦 ข้อมูลภาพขนาด {data_len} bytes")

    # เช็คขนาดไฟล์เพื่อกำหนด Width และ Height อัตโนมัติ
    if data_len == 1920000:
        width, height = 1600, 1200
        logger.info("📐 ตรวจพบรูปแบบภาพ: Full Frame (1600x1200)")
    elif data_len == 112500:
        width, height = 300, 375
        logger.info("📐 ตรวจพบรูปแบบภาพ: Cropped (300x375)")
    else:
        logger.error(f"❌ ไม่รู้จักรูปแบบภาพที่มีขนาด {data_len} bytes")
        return None

    try:
        # สร้างภาพโหมด 'L' (8-bit pixels, Grayscale)
        img = Image.frombytes('L', (width, height), raw_data)
        return img
    except Exception as e:
        logger.error(f"❌ แปลงภาพล้มเหลว: {e}")
        return None

def decode_from_file(filepath: str, save_output: bool = True) -> Optional[Image.Image]:
    """
    อ่านไฟล์ .raw จากคอมพิวเตอร์ และแปลงเป็นรูปภาพ
    """
    if not os.path.exists(filepath):
        logger.error(f"❌ ไม่พบไฟล์ {filepath}")
        return None

    try:
        with open(filepath, "rb") as f:
            raw_data = f.read()
        
        img = decode_from_bytes(raw_data)
        
        # ถ้าระบุให้เซฟอัตโนมัติ จะสร้างไฟล์ .png ไว้ที่เดียวกัน
        if img and save_output:
            base_name = os.path.splitext(filepath)[0] # ตัดนามสกุล .raw ออก
            output_filename = f"{base_name}_{img.width}x{img.height}.png"
            img.save(output_filename)
            logger.info(f"✅ บันทึกไฟล์รูปภาพสำเร็จ: {output_filename}")
            
        return img
    except Exception as e:
        logger.error(f"❌ ข้อผิดพลาดในการอ่านไฟล์: {e}")
        return None