from PIL import Image
import os

def analyze_raw_file(filename):
    with open(filename, "rb") as f:
        data = f.read()

    print(f"📦 โหลดไฟล์ {filename} ขนาด {len(data)} ไบต์")

    # 1. เช็คว่าฮาร์ดแวร์แอบส่งไฟล์สำเร็จรูปมาให้หรือเปล่า (เช่น BMP)
    header = data[:2]
    if header == b'BM':
        print("⚠️ ข้อมูลนี้ไม่ใช่ Raw Bytes ดิบๆ แต่มันคือไฟล์ภาพ BMP สำเร็จรูป!")
        with open("fingerprint_auto.bmp", "wb") as f:
            f.write(data)
        print("💾 เซฟไฟล์ fingerprint_auto.bmp ให้แล้ว ลองเปิดดูได้เลย")
        return

    # 2. ลองเดาขนาด Grayscale แบบต่างๆ
    resolutions = [
        (256, 440, "gray_256x440.png"),  # ทฤษฎีใหม่ที่หารลงตัวเป๊ะ
        (300, 375, "gray_300x375.png"),  # ทฤษฎีเดิม
        (288, 391, "gray_288x391.png")   # อีกหนึ่งขนาดมาตรฐาน
    ]

    for width, height, out_name in resolutions:
        expected_size = width * height
        if len(data) >= expected_size:
            img_data = data[:expected_size]
            img = Image.frombytes('L', (width, height), img_data)
            img.save(out_name)
            print(f"✅ สร้างภาพ Grayscale: {out_name}")

    # 3. ลองทดสอบทฤษฎี RGB ตามที่คุณชัยวิทย์คาดการณ์
    # ถ้าเป็น RGB 1 พิกเซลใช้ 3 ไบต์ -> 112,640 / 3 = 37,546 พิกเซล
    # ลองสุ่มขนาดที่ใกล้เคียง เช่น 150 x 250 = 37,500 พิกเซล
    rgb_size = 150 * 250 * 3
    if len(data) >= rgb_size:
        img_data_rgb = data[:rgb_size]
        img_rgb = Image.frombytes('RGB', (150, 250), img_data_rgb)
        img_rgb.save("test_rgb_150x250.png")
        print("🎨 สร้างภาพจำลองแบบ RGB: test_rgb_150x250.png")

if __name__ == "__main__":
    if os.path.exists("fingerprint_raw.bin"):
        analyze_raw_file("fingerprint_raw.bin")
    else:
        print("หาไฟล์ไม่เจอครับ!")