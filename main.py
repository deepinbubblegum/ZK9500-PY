import usb.core
import usb.util
import time

class ZK9500:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x1b55, idProduct=0x0124)
        if self.dev is None:
            raise ValueError("Device not found!")

        print("Hard Resetting device...")
        if self.dev is not None:
            self.dev.reset() # type: ignore
        time.sleep(0.2)

    def send_cmd(self, bmRequestType, bRequest, wValue=0, wIndex=0, payload_or_length=None):
        """ 
        ฟังก์ชันพื้นฐานสำหรับส่ง Control Transfer (อ้างอิงจาก Logic Wireshark)
        - ถ้าส่งข้อมูล (OUT 0x40): payload_or_length คือ bytes ของข้อมูล
        - ถ้ารับข้อมูล (IN 0xC0): payload_or_length คือ จำนวนไบต์ที่ต้องการรับ
        """
        try:
            return self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload_or_length, timeout=1000) # type: ignore
        except usb.core.USBError as e:
            print(f"⚠️ USB Error (Request {bRequest}): {e}")
            return None
        
    def Open(self):
        """
        ฟังก์ชันเปิดการเชื่อมต่อและเตรียมความพร้อมเซนเซอร์
        Logic ถอดรหัสมาจากโปรแกรม ZKTeco Official Demo (จังหวะกดปุ่ม 'Open')
        """
        print("⚙️  Sending Open/Init Sequence...")
        
        # 1. ปลุกเครื่อง (Wake Up)
        # อ้างอิง: Wireshark Frame 461 (bmRequestType: 0x40, bRequest: 224)
        print("   -> Sending Wake Up command (Req: 224)")
        self.send_cmd(0x40, 224, 0, 0)
        
        # 2. ล้าง Memory / ตั้งค่าเริ่มต้น
        # อ้างอิง: Wireshark Frame 463 (bmRequestType: 0x40, bRequest: 128, Payload: \x00 * 16)
        print("   -> Sending Clear Memory command (Req: 128)")
        zero_payload = bytes([0] * 16) 
        self.send_cmd(0x40, 128, 0, 0, payload_or_length=zero_payload)

        self.send_cmd(0x40, 225, 0xC801, 0)
        self.send_cmd(0x40, 225, 0xC801, 1)
        self.send_cmd(0x40, 225, 0xAF01, 2)
        self.send_cmd(0x40, 225, 0xAF01, 3)
        self.send_cmd(0x40, 225, 0x7801, 4)
        self.send_cmd(0x40, 225, 0x7801, 5)
        self.send_cmd(0x40, 227, 0x00C8, 165)
        self.send_cmd(0x40, 227, 0x00C8, 166)
        self.send_cmd(0x40, 227, 0x00C8, 163)
        self.send_cmd(0x40, 227, 0x00C8, 164)
        self.send_cmd(0x40, 227, 0x00BC, 169)
        self.send_cmd(0x40, 227, 0x00BC, 170)
        self.send_cmd(0x40, 227, 0x00C8, 167)
        self.send_cmd(0x40, 227, 0x00C8, 168)
        self.send_cmd(0x40, 227, 0x0002, 3)
        self.send_cmd(0x40, 227, 0x00d8, 4)
        self.send_cmd(0x40, 225, 0x8001, 6)
        self.send_cmd(0x40, 225, 0x8001, 7)
        self.send_cmd(0x40, 225, 0x8001, 8)
        self.send_cmd(0x40, 225, 0x0001, 83)
        self.send_cmd(0x40, 225, 0x0000, 50)
        self.send_cmd(0x40, 225, 0x0001, 49)
        self.send_cmd(0x40, 225, 0x0003, 48)
        # self.send_cmd(0x40, 225, 0x0000, 21)
        # self.send_cmd(0x40, 225, 0x0000, 48)
        # self.send_cmd(0x40, 225, 0x0000, 49)
        
        # 3. ไม่รู้ว่าคืออะไร 226
        response = self.send_cmd(0xC0, 226, 0, 85, payload_or_length=2)
        if response is not None and len(response) > 0:
            # แปลงเป็น list เพื่อให้ดูง่ายและเปรียบเทียบค่าสะดวก
            data = response.tolist() 
            print(f"   -> Register 85 Check: {data} (Hex: {[hex(x) for x in data]}) [OK]")
        else:
            print("   -> Failed to read Register 85 (Req: 226)")
            print("   -> Response was None or empty, cannot verify device state.")
            return False

        # polling
        print("   -> Starting polling loop (Press Ctrl+C to stop)...")
        counter = 0
        # 231 cmd polling register 0-255 recive 1 byte response (0-255)
        device_info = {
            "DeviceModel": usb.util.get_string(self.dev, self.dev.iProduct), # type: ignore
            "SerialNumber": usb.util.get_string(self.dev, self.dev.iSerialNumber) # type: ignore
        }
        print(f"   -> Device Info: {device_info}")
        for i in range(255):
            self.send_cmd(0xC0, 231, 0, i, payload_or_length=1)

        self.send_cmd(0xC0, 234, 0, 0, payload_or_length=1)
        return True
    
    def wait_for_finger(self):
        print("⏳ [Ready] กรุณาวางนิ้วบนเซนเซอร์...")
        try:
            while True:
                res = self.send_cmd(0xC0, 234, 0, 0, payload_or_length=1)
                
                if res and len(res) > 0:
                    status = res[0]
                    if status != 0 and status != 8: 
                        print(f"☝️  Detected! (Status: {hex(status)})")
                        
                        # 🚀 [เพิ่มตรงนี้] หน่วงเวลาให้เซนเซอร์สร้างภาพให้เสร็จก่อน!
                        print("⏳ รอให้เซนเซอร์ถ่ายภาพให้สมบูรณ์...")
                        time.sleep(0.5) # ลองปรับเป็น 0.5 ถึง 1.0 วินาทีดูครับ
                        
                        return True 
                
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n🛑 หยุดการรอนิ้วโดยผู้ใช้")
            return False
        
    def ReciveImage(self):
        print("📸 กำลังเปิดท่อดูดภาพ...")

        try:
            expected_size = 112640 
            
            # --- รอบที่ 1: ดูด Header หรือ ออเดิร์ฟ ---
            print("   -> ดึงข้อมูลรอบที่ 1...")
            chunk1 = self.dev.read(0x82, expected_size, timeout=5000)
            print(f"📦 รอบแรกได้มา: {len(chunk1)} ไบต์ -> Hex: {[hex(x) for x in chunk1]}")

            image_data = chunk1

            # ถ้าข้อมูลรอบแรกน้อยผิดปกติ (เช่นได้แค่ 4 ไบต์) 
            # แสดงว่าเป็นแค่ Header ให้ทำการดูดจานหลักต่อทันที!
            if len(chunk1) < 100:
                print("   -> ⚠️ นี่มันแค่ Header! กำลังสูบภาพของจริงที่รออยู่คิวถัดไป...")
                chunk2 = self.dev.read(0x82, expected_size, timeout=5000)
                print(f"✅ รอบสองได้มา: {len(chunk2)} ไบต์")
                image_data = chunk2 # เอาภาพของจริงมาใช้
            
            print(f"🎉 สำเร็จ! ได้รับภาพมาทั้งหมด: {len(image_data)} ไบต์")
            
            # บันทึกไฟล์ภาพดิบ
            if len(image_data) > 1000: # เซฟเฉพาะตอนที่ได้ภาพจริงๆ
                with open("fingerprint_raw.bin", "wb") as f:
                    f.write(image_data)
                print("💾 บันทึกไฟล์ fingerprint_raw.bin เรียบร้อยแล้ว!")
            
            return image_data

        except usb.core.USBError as e:
            print(f"❌ Error ตอนดูดข้อมูลภาพ: {e}")
            return None
        
if __name__ == "__main__":
    try:
        zk = ZK9500()
        print("Device reset successfully.")
        
        # ทดสอบเรียกใช้งานปุ่ม Open
        zk.Open()
        if zk.wait_for_finger():
            zk.ReciveImage()
        
    except ValueError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")
    finally:
        # คืนทรัพยากรให้ OS เสมอเพื่อป้องกันพอร์ตค้าง
        if 'zk' in locals() and zk.dev is not None:
            usb.util.dispose_resources(zk.dev)