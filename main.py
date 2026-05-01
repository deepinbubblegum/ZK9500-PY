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
                # ถามสถานะด้วย 234
                res = self.send_cmd(0xC0, 234, 0, 0, payload_or_length=1)
                
                if res and len(res) > 0:
                    status = res[0]
                    # ตรวจสอบว่าสถานะเปลี่ยนจาก "ว่างเปล่า" หรือยัง
                    if status != 0 and status != 8: 
                        print(f"☝️  Detected! (Status: {hex(status)})")
                        return True # เจอนิ้วแล้ว ออกจากลูป
                
                time.sleep(0.05) # พักเล็กน้อย ไม่ให้ CPU ทำงานหนักเกินไป
        except KeyboardInterrupt:
            print("\n🛑 หยุดการรอนิ้วโดยผู้ใช้")
            return False
        
    def ReciveImage(self):
        try:
            print("📸 กำลังร้องขอข้อมูลภาพจาก Endpoint 0x82...")
            time.sleep(0.1)

            all_data = bytearray()
            prev_size = float('inf')

            while True:
                data = self.dev.read(0x82, 65536, timeout=10000)

                if len(data) == 0:
                    print("   -> ได้ข้อมูลว่าง, จบการรับ")
                    break

                all_data.extend(data)
                curr_size = len(data)
                print(f"   +{curr_size} bytes (รวม: {len(all_data)})")

                if curr_size < prev_size:
                    print(f"   -> ตรวจพบ frame สุดท้าย ({curr_size} < {prev_size})")
                    break

                prev_size = curr_size

            if len(all_data) > 1000:
                print(f"✅ สำเร็จ! ได้รับข้อมูลภาพขนาด: {len(all_data)} ไบต์")
                with open("fingerprint.raw", "wb") as f:
                    f.write(all_data)
                return True
            else:
                print(f"⚠️ ได้รับข้อมูลเพียง {len(all_data)} ไบต์")
                return False

        except usb.core.USBError as e:
            print(f"❌ อ่านข้อมูลภาพล้มเหลว: {e}")
            return False

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