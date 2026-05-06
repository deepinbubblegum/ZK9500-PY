from PIL import Image

# กำหนดขนาดภาพตามที่ Log รายงาน
width = 1600
height = 1200

try:
    # 1. อ่านไฟล์ Raw
    with open("fingerprint.raw", "rb") as f:
        raw_data = f.read()
        
    print(f"อ่านข้อมูลได้ {len(raw_data)} bytes")

    # 2. สร้างภาพโหมด 'L' (8-bit pixels, black and white)
    img = Image.frombytes('L', (width, height), raw_data)

    # 3. บันทึกเป็น PNG ให้เปิดดูง่ายๆ
    img.save("fingerprint_output.png")
    print("✅ แปลงไฟล์สำเร็จ! เปิดดูไฟล์ fingerprint_output.png ได้เลย")
    
    # ถ้าเครื่อง Linux ของคุณมี GUI มันจะเปิดภาพขึ้นมาให้ดูทันที
    img.show() 

except FileNotFoundError:
    print("❌ ไม่พบไฟล์ fingerprint.raw")
except ValueError as e:
    print(f"❌ ขนาดข้อมูลไม่ตรงกัน: {e}")