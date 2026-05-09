import os
import logging
from PIL import Image
from typing import Optional

# ตั้งค่า Logger
logger = logging.getLogger(__name__)

def decode_from_bytes(raw_data: bytes) -> Optional[Image.Image]:
    """
    Convert raw byte data from the scanner into a PIL Image object
    """
    data_len = len(raw_data)
    logger.debug(f"📦 Received raw data of length: {data_len} bytes")

    # check data length to determine width and height automatically
    if data_len == 1920000:
        width, height = 1600, 1200
        logger.info("📐 Verified image format: Full Frame (1600x1200)")
    elif data_len == 112500:
        width, height = 300, 375
        logger.info("📐 Verified image format: mode (300x375)")
    else:
        logger.error(f"❌ Unknown image format for data length: {data_len}")
        return None

    try:
        # create image with mode 'L' (8-bit pixels, Grayscale)
        img = Image.frombytes('L', (width, height), raw_data)
        return img
    except Exception as e:
        logger.error(f"❌ Image Conversion Error: {e}")
        return None

def decode_from_file(filepath: str, save_output: bool = True) -> Optional[Image.Image]:
    """
         Read a .raw file from disk and convert it to an image
    """
    if not os.path.exists(filepath):
        logger.error(f"❌ File not found: {filepath}")
        return None

    try:
        with open(filepath, "rb") as f:
            raw_data = f.read()
        
        img = decode_from_bytes(raw_data)
        
        # if specified to auto-save, it will create a .png file in the same location
        if img and save_output:
            base_name = os.path.splitext(filepath)[0]
            output_filename = f"{base_name}_{img.width}x{img.height}.png"
            img.save(output_filename)
            logger.info(f"✅ saved decoded image as: {output_filename}")

        return img
    except Exception as e:
        logger.error(f"❌ error reading file: {e}")
        return None