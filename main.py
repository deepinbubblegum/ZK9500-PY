import usb.core
import usb.util
import sys
import time

class ZK9500:
    def __init__(self):
        self.idVendor = 0x1b55
        self.idProduct = 0x0124
        self.dev = None
        self.timeout = 5000
        self.ep_status_in = 0x81
        self.ep_image_in = 0x82
        self.ep_out = 0x03

    def connect(self):
        """ ค้นหาและเตรียมความพร้อมอุปกรณ์ """
        self.dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.dev is None:
            raise ValueError("ไม่พบอุปกรณ์ ZKTeco 9500")

        if self.dev.is_kernel_driver_active(0):
            try:
                self.dev.detach_kernel_driver(0)
            except usb.core.USBError as e:
                sys.exit(f"Could not detach kernel driver: {e}")

        try:
            # ล้างสถานะเก่าก่อนเริ่มงาน
            self.dev.reset()
            time.sleep(0.5) 
            self.dev.set_configuration()
            usb.util.claim_interface(self.dev, 0)
            
            # เคลียร์ท่อข้อมูลขยะ
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
        if self.dev is None: return None
        try:
            return self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_length, self.timeout)
        except usb.core.USBError as e:
            # ไม่ต้องปริ้น Error ถ้าเป็นจังหวะ Reboot เพราะท่อจะถูกตัดทันที
            return None

    def handshake(self):
        print("⚙️  Sending Handshake (0x80)...")
        payload = bytearray([0x00] * 16)
        self.control_transfer(0x40, 0x80, 0, 0, payload)
        time.sleep(0.1)
        try:
            ack = self.dev.read(self.ep_image_in, 4, timeout=self.timeout)
            if ack[0] == 0x00:
                print("✅ Handshake Success!")
                return True
        except: pass
        return False

    def reboot_hardware(self):
        """ ส่งคำสั่ง 0xF0 (wIndex=0x30) เพื่อบังคับ Reboot และดับไฟสนิท """
        print("🚀 Sending Hardware Reboot (0xF0)...")
        # ส่งตามค่าที่แกะได้จาก FUN_0011b134
        self.control_transfer(0x40, 0xf0, 0, 0x30, None)
        time.sleep(0.2)

    def detect_finger(self):
        try:
            response = self.control_transfer(0xc0, 0xea, 0, 0, 10)
            if response and response[0] != 0:
                return True
        except: pass
        return False
        
    def capture_image(self):
        print("📸 Capturing Image...")
        try:
            res = self.control_transfer(0xc0, 0xe5, 0, 0, 5)
            if res and len(res) >= 4:
                width = res[0] | (res[1] << 8)
                height = res[2] | (res[3] << 8)
                image_data = self.dev.read(self.ep_image_in, width * height, timeout=5000)
                return image_data, width, height
        except Exception as e:
            print(f"❌ Capture Error: {e}")
        return None
        
    def disconnect(self):
        """ ปิดเครื่องแบบ Uninit สนิทที่สุด """
        if self.dev is not None:
            try:
                # 1. สั่ง Reboot ทันทีเพื่อฆ่าโหมด Auto-Detect
                self.reboot_hardware()
                
                # 2. คืนสิทธิ์ interface
                try:
                    usb.util.release_interface(self.dev, 0)
                except: pass
                
                # 3. สั่ง Reset บัส USB เป็นการปิดท้าย
                print("🔄 Finalizing Hardware Reset...")
                self.dev.reset()
            except:
                pass
            usb.util.dispose_resources(self.dev)
            self.dev = None
            print("🛑 Uninitialized and Disconnected.")

    def setup_sensor_crop_mode(self):
        """ ส่งชุดคำสั่ง Magic Sequence เพื่อตั้งค่า Sensor ให้ดึงภาพ 112.5K """
        print("⚙️  Sending Magic Sequence for Sensor Crop Mode...")
        
        # bRequest = 225 (0xE1)
        magic_sequence = [
            (0x8001, 0x0006),
            (0x8001, 0x0007),
            (0x8001, 0x0008),
            (0x0001, 0x0053),
            (0x0000, 0x0032),
            (0x0001, 0x0031),
            (0x0003, 0x0030)
        ]
        
        for wVal, wIdx in magic_sequence:
            # 0x40 = Host-to-Device Vendor request
            # 0xe1 = 225 (bRequest)
            self.control_transfer(0x40, 0xe1, wVal, wIdx, None)
            time.sleep(0.01) # พักหน่วงเวลาเล็กน้อยให้ Hardware ประมวลผลทัน
            
        print("✅ Sensor Cropping Configured!")

if __name__ == "__main__":
    scanner = ZK9500()
    try:
        if scanner.connect() and scanner.handshake():
            # scanner.setup_sensor_crop_mode()
            print("\n=== 🟢 ระบบพร้อมทำงาน (วางนิ้วเพื่อแสกน) ===")
            while True:
                if scanner.detect_finger():
                    print("👇 ตรวจพบการวางนิ้ว!")
                    result = scanner.capture_image()
                    if result:
                        img_data, w, h = result
                        with open("fingerprint.raw", "wb") as f:
                            f.write(img_data)
                        print(f"💾 บันทึกภาพสำเร็จ ({w}x{h})")
                        break
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n👋 ผู้ใช้งานยกเลิก")
    finally:
        scanner.disconnect()