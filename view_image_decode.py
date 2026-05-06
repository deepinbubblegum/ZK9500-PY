from PIL import Image

filename = "fingerprint.raw" # เปลี่ยนชื่อไฟล์ตรงนี้ได้ถ้าคุณเซฟชื่ออื่น

try:
    # 1. อ่านไฟล์ Raw
    with open(filename, "rb") as f:
        raw_data = f.read()
        
    data_len = len(raw_data)
    print(f"📦 อ่านข้อมูลได้ {data_len} bytes")

    # 2. เช็คขนาดไฟล์เพื่อกำหนด Width และ Height อัตโนมัติ
    if data_len == 1920000:
        width, height = 1600, 1200
        print("📐 ตรวจพบรูปแบบภาพ: Full Frame เซนเซอร์เต็ม (1600x1200)")
    elif data_len == 112500:
        width, height = 300, 375
        print("📐 ตรวจพบรูปแบบภาพ: Cropped ตัดขอบแล้ว (300x375)")
    else:
        # เผื่อกรณีที่เซนเซอร์ส่งขนาดแปลกๆ มา
        raise ValueError(f"ไม่รู้จักรูปแบบภาพที่มีขนาด {data_len} bytes")

    # 3. สร้างภาพโหมด 'L' (8-bit pixels, Grayscale)
    img = Image.frombytes('L', (width, height), raw_data)

    # 4. บันทึกเป็น PNG (ตั้งชื่อไฟล์ตามขนาดเพื่อไม่ให้เซฟทับกัน)
    output_filename = f"fingerprint_output_{width}x{height}.png"
    img.save(output_filename)
    print(f"✅ แปลงไฟล์สำเร็จ! เปิดดูไฟล์ '{output_filename}' ได้เลย")
    
    # 5. เปิดภาพขึ้นมาดู
    img.show() 

except FileNotFoundError:
    print(f"❌ ไม่พบไฟล์ {filename}")
except ValueError as e:
    print(f"❌ ข้อผิดพลาด: {e}")