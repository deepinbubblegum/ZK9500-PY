import logging
import time
from zk9500 import ZK9500

# เปิดการแสดงข้อความ Log (เพื่อดูสถานะการทำงาน)
logging.basicConfig(level=logging.INFO)

def main():
    print("🚀 เริ่มต้นทดสอบ ZK9500 Library...")
    
    # 1. สร้าง Object เครื่องสแกน
    scanner = ZK9500()
    
    # 2. ทำการเชื่อมต่อ
    if scanner.connect():
        scanner.handshake()
        scanner.setup_normal_mode()
        
        print("\n👆 กรุณาวางนิ้วบนเครื่องสแกน...")
        
        # 3. วนลูปรอจนกว่าจะเจอนิ้ว
        capture_result = None
        while not capture_result:
            if scanner.detect_finger():
                capture_result = scanner.capture_image()
            time.sleep(0.02) # พักเบรกนิดนึงไม่ให้ CPU ทำงานหนักไป
        
        # 4. เมื่อถ่ายภาพสำเร็จ ให้นำมาแปลงเป็นรูปและเซฟ
        if capture_result:
            raw_data, width, height = capture_result
            print(f"📸 ได้รับข้อมูลภาพขนาด: {width}x{height}")
            
            # เรียกใช้ฟังก์ชัน decode ที่เราเพิ่งผูกไว้
            img = scanner.decode_from_bytes(raw_data)
            
            if img:
                img.save("my_test_finger.png")
                print("✅ บันทึกรูปลงไฟล์ 'my_test_finger.png' สำเร็จ!")
                img.show() # เปิดรูปขึ้นมาโชว์
                
        # 5. ตัดการเชื่อมต่อให้เรียบร้อย
        scanner.disconnect()
        print("👋 bye")

if __name__ == "__main__":
    main()