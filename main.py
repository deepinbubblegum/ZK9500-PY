import usb.core
import usb.util
import sys
import time

class ZK9500:
    def __init__(self):
        # ข้อมูลพื้นฐานของอุปกรณ์ที่ตรวจพบ
        self.idVendor = 0x1b55
        self.idProduct = 0x0124
        self.dev = None
        self.timeout = 5000
        
        # Endpoints สำหรับรับ-ส่งข้อมูล
        self.ep_status_in = 0x81  # เช็ค ACK เบื้องต้น
        self.ep_image_in = 0x82   # ช่องทางหลักสำหรับ Data/Image
        self.ep_out = 0x03        # ช่องทางส่งคำสั่งออก

    def connect(self):
        """ ค้นหา จองสิทธิ์ และ Reset ฮาร์ดแวร์เพื่อล้างสถานะค้างเก่า """
        self.dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        
        if self.dev is None:
            raise ValueError("ไม่พบอุปกรณ์ ZKTeco 9500 กรุณาตรวจสอบสายเชื่อมต่อ")

        # ปลดการจองของ Kernel (สำหรับ Linux)
        if self.dev.is_kernel_driver_active(0):
            try:
                self.dev.detach_kernel_driver(0)
                print("Detached kernel driver successfully.")
            except usb.core.USBError as e:
                sys.exit(f"Could not detach kernel driver: {e}")

        # --- ส่วนสำคัญ: ยาแรงแก้ปัญหาเครื่องค้าง ---
        try:
            print("🔄 Force Resetting Hardware...")
            self.dev.reset()  # บังคับ Reboot ให้อุปกรณ์กลับสู่สถานะเริ่มต้น
            time.sleep(0.5) 
            self.dev.set_configuration()
            usb.util.claim_interface(self.dev, 0) # จองสิทธิ์ Interface 0
            
            # ล้างท่อส่งข้อมูล (Flush Buffer) เพื่อป้องกันข้อมูลเก่าขวางทาง
            for ep in [self.ep_status_in, self.ep_image_in]:
                self.dev.clear_halt(ep)
                try:
                    self.dev.read(ep, 1024, timeout=100)
                except: pass
        except usb.core.USBError as e:
            sys.exit(f"Error during initialization: {e}")
            
        print("✅ เชื่อมต่อ ZK9500 สำเร็จ!")
        return True

    def control_transfer(self, bmRequestType, bRequest, wValue, wIndex, data_or_length):
        """ ส่งคำสั่งควบคุมไปยังอุปกรณ์ """
        if self.dev is None: return None
        try:
            return self.dev.ctrl_transfer(
                bmRequestType=bmRequestType,
                bRequest=bRequest,
                wValue=wValue,
                wIndex=wIndex,
                data_or_wLength=data_or_length,
                timeout=self.timeout
            )
        except usb.core.USBError as e:
            print(f"USB Control Error: {e}")
            return None

    def handshake(self):
        """ ส่งคำสั่งปลุกเครื่อง (0x80) และรอ ACK """
        print("⚙️  Sending Handshake (Wake Up)...")
        payload = bytearray([0x00] * 16)
        
        try:
            # ส่งคำสั่ง 0x80 ตามที่พบใน SDK
            self.control_transfer(0x40, 0x80, 0, 0, payload)
            time.sleep(0.1)
            
            # อ่านคำตอบจากช่องทาง Bulk (0x82)
            ack = self.dev.read(self.ep_image_in, 4, timeout=self.timeout)
            if ack[0] == 0x00:
                print("✅ Handshake Success! เครื่องพร้อมทำงาน")
                return True
        except Exception as e:
            print(f"❌ Handshake Failed: {e}")
        return False

    def close_sensor(self):
        """ ส่งคำสั่งปิดการทำงานเซ็นเซอร์ (0x81) เพื่อดับไฟและหยุดการแสกน """
        print("🌙 Sending Sleep Command (0x81)...")
        payload = bytearray([0x00] * 16)
        self.control_transfer(0x40, 0x81, 0, 0, payload)
        time.sleep(0.1)

    def detect_finger(self):
        """ ตรวจสอบสถานะว่ามีนิ้วสัมผัสหรือไม่ (0xEA) """
        try:
            # คำสั่ง 0xEA สำหรับ Check Touch
            response = self.control_transfer(0xc0, 0xea, 0, 0, 10)
            if response and response[0] != 0: # ถ้าสถานะไม่ใช่ 0 แปลว่ามีการวางนิ้ว
                return True
        except: pass
        return False
        
    def capture_image(self):
        """ ดึงข้อมูลขนาดภาพ (0xE5) และดูดข้อมูล Raw """
        print("📸 Capturing Image...")
        try:
            # ขอข้อมูลภาพ 5 bytes (W, H, Status)
            res = self.control_transfer(0xc0, 0xe5, 0, 0, 5)
            if res and len(res) >= 4:
                # คำนวณขนาดภาพ (Little Endian)
                width = res[0] | (res[1] << 8)
                height = res[2] | (res[3] << 8)
                print(f"   -> Image Size: {width}x{height} pixels") # ปกติจะเป็น 1600x1200
                
                # อ่านข้อมูลภาพก้อนใหญ่
                image_data = self.dev.read(self.ep_image_in, width * height, timeout=5000)
                return image_data, width, height
        except Exception as e:
            print(f"❌ Capture Error: {e}")
        return None
        
    def disconnect(self):
        """ ขั้นตอนการปิดระบบที่ถูกต้องและป้องกัน Error กวนใจ """
        if self.dev is not None:
            try:
                # 1. ให้เวลาเครื่อง "หายใจ" หลังส่งภาพเสร็จสักครู่ก่อนส่งคำสั่งปิด
                time.sleep(0.2) 
                
                # 2. ลองส่งคำสั่งปิดเซ็นเซอร์ (หุ้มด้วย try-except เพื่อไม่ให้โชว์ Error น่าเกลียด)
                try:
                    payload = bytearray([0x00] * 16)
                    self.dev.ctrl_transfer(0x40, 0x81, 0, 0, payload, timeout=1000)
                except usb.core.USBError:
                    # ถ้าเครื่องไม่ตอบรับ 0x81 ก็ไม่เป็นไร เพราะเราจะ Reset ต่อด้านล่าง
                    pass
                
                # 3. คืนสิทธิ์ interface
                usb.util.release_interface(self.dev, 0)
                
                # 4. รีเซ็ตฮาร์ดแวร์ (ตัวนี้จะทำให้ไฟดับและเครื่องพร้อมสำหรับการรันครั้งต่อไป)
                print("🔄 Resetting Hardware for clean exit...")
                self.dev.reset()
                
            except Exception as e:
                print(f"⚠️ Disconnect notice: {e}")
            finally:
                usb.util.dispose_resources(self.dev)
                self.dev = None
                print("🛑 Disconnected.")

# ==========================================
# ส่วนรันโปรแกรมหลัก
# ==========================================
if __name__ == "__main__":
    scanner = ZK9500()
    try:
        if scanner.connect() and scanner.handshake():
            print("\n=== 🟢 ระบบพร้อมทำงาน กรุณาวางนิ้วบนเครื่องสแกน ===")
            while True:
                if scanner.detect_finger():
                    print("\n👇 ตรวจพบการวางนิ้ว! กำลังประมวลผล...")
                    result = scanner.capture_image()
                    
                    if result:
                        img_data, w, h = result
                        # บันทึกเป็นไฟล์ Raw เพื่อรอนำไปแปลงเป็นรูปภาพ
                        with open("fingerprint.raw", "wb") as f:
                            f.write(img_data)
                        print(f"💾 บันทึกไฟล์ fingerprint.raw สำเร็จ! (ขนาด {w}x{h})")
                        break # สแกนสำเร็จแล้วจบการทำงาน
                time.sleep(0.1) # ป้องกัน CPU ทำงานหนักเกินไป
                
    except KeyboardInterrupt:
        print("\n👋 ยกเลิกโดยผู้ใช้งาน")
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาด: {e}")
    finally:
        scanner.disconnect()