import os
from PIL import Image, ImageOps

def smart_decode(bin_file):
    print(f"🔍 กำลังวิเคราะห์ไฟล์: {bin_file}")
    with open(bin_file, "rb") as f:
        data = f.read()
    
    # ---------------------------------------------------------
    # 1. พิสูจน์ความจริง: ดูค่าสถิติของข้อมูล (Truth Test)
    # ---------------------------------------------------------
    values = list(data)
    min_val = min(values)
    max_val = max(values)
    avg_val = sum(values) / len(values)
    
    print("\n📊 สถิติข้อมูล Raw Bytes (0 = ดำ, 255 = ขาว):")
    print(f"   -> ค่าความสว่างต่ำสุด (Min): {min_val}")
    print(f"   -> ค่าความสว่างสูงสุด (Max): {max_val}")
    print(f"   -> ค่าความสว่างเฉลี่ย (Avg): {avg_val:.2f}")
    
    # วิเคราะห์ผลลัพธ์
    if max_val < 20:
        print("\n🚨 ฟันธง: นี่คือ Dark Frame (ไฟสแกนไม่ติดแน่นอนครับ!)")
        print("   เหตุผล: ไม่มีพิกเซลไหนเลยที่สว่างพอจะเป็นสีขาว แสดงว่าเซนเซอร์ทำงานในที่มืดสนิท")
        return # ถ้ามืดสนิท ไม่ต้องเสียเวลา Decode ต่อครับ
    elif min_val > 230:
        print("\n🚨 ฟันธง: ภาพสว่างจ้า (Overexposed) หรือไม่มีนิ้ววาง")
    else:
        print("\n💡 ฟันธง: ข้อมูลมีทั้งมืดและสว่าง แสดงว่าไฟติดแล้ว! ปัญหาอยู่ที่การ Decode จริงๆ!")

    # ---------------------------------------------------------
    # 2. ลอง Decode ภาพด้วยการเลื่อน Offset (ข้าม Header)
    # ---------------------------------------------------------
    print("\n🛠️ กำลังลอง Decode ด้วยขนาด 300x375 แบบข้ามส่วนเกิน...")
    width, height = 300, 375
    expected_size = width * height # 112,500 ไบต์
    
    # ลองข้ามไบต์แรกๆ เผื่อมันเป็น Header (140 คือส่วนต่างของ 112,640 - 112,500)
    offsets_to_try = [0, 64, 140] 
    
    for offset in offsets_to_try:
        if len(data) >= offset + expected_size:
            # ตัดเอาเฉพาะส่วนที่เป็นภาพจริงๆ
            img_data = data[offset : offset + expected_size]
            
            # สร้างภาพขาวดำปกติ
            img = Image.frombytes('L', (width, height), img_data)
            out_name = f"result_offset_{offset}.png"
            img.save(out_name)
            
            # สร้างภาพแบบกลับสี (Inverted) เผื่อเซนเซอร์ส่งค่ากลับทาง
            img_inv = ImageOps.invert(img)
            out_inv_name = f"result_offset_{offset}_inverted.png"
            img_inv.save(out_inv_name)
            
            print(f"✅ สร้างภาพสำเร็จ: {out_name} และ {out_inv_name}")

if __name__ == "__main__":
    if os.path.exists("fingerprint_raw.bin"):
        smart_decode("fingerprint_raw.bin")
    else:
        print("หาไฟล์ fingerprint_raw.bin ไม่เจอครับ!")