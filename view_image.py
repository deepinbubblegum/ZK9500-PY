from PIL import Image
import os

def convert_bin_to_png(bin_file, output_png):
    # ขนาดภาพมาตรฐานของ ZK9500 คือ 300 x 375 พิกเซล
    width = 300
    height = 375
    expected_image_size = width * height  # 112,500 ไบต์

    print(f"กำลังเปิดไฟล์: {bin_file}")
    with open(bin_file, "rb") as f:
        raw_data = f.read()

    print(f"ขนาดไฟล์ Raw: {len(raw_data)} ไบต์")

    # ตัดเอาเฉพาะข้อมูลภาพ 112,500 ไบต์แรก (ทิ้ง Padding 140 ไบต์ท้ายไป)
    if len(raw_data) >= expected_image_size:
        image_bytes = raw_data[:expected_image_size]
        
        # 'L' mode หมายถึงภาพ 8-bit Grayscale (ขาวดำ)
        img = Image.frombytes('L', (width, height), image_bytes)
        
        # เซฟเป็น PNG
        img.save(output_png)
        print(f"✅ บันทึกภาพสำเร็จ! ตรวจสอบไฟล์: {output_png}")
        
        # สั่งเปิดภาพขึ้นมาดูทันที
        img.show()
    else:
        print("❌ ขนาดไฟล์เล็กเกินไป ไม่ใช่ภาพลายนิ้วมือที่สมบูรณ์")

if __name__ == "__main__":
    if os.path.exists("fingerprint_raw.bin"):
        convert_bin_to_png("fingerprint_raw.bin", "fingerprint_result.png")
    else:
        print("หาไฟล์ fingerprint_raw.bin ไม่เจอครับ!")