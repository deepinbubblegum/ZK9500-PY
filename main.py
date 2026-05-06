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
        
        # Endpoints ที่เราหาเจอจาก lsusb
        self.ep_status_in = 0x81  # สำหรับอ่าน ACK
        self.ep_image_in = 0x82   # สำหรับอ่านรูปภาพ
        self.ep_out = 0x03        # สำหรับส่งข้อมูล

    def connect(self):
        """
        ค้นหาอุปกรณ์ จองสิทธิ์ และตั้งค่าเริ่มต้น
        """
        self.dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        
        if self.dev is None:
            raise ValueError("ไม่พบอุปกรณ์ ZKTeco 9500 (ตรวจสอบว่าเสียบสายและตั้งค่า udev rules แล้วหรือยัง)")

        # ปลด Kernel Driver ของระบบ OS ออก
        if self.dev.is_kernel_driver_active(0):
            try:
                self.dev.detach_kernel_driver(0)
                print("Detached kernel driver successfully.")
            except usb.core.USBError as e:
                sys.exit(f"Could not detach kernel driver: {e}")

        # รีเซ็ตอุปกรณ์เพื่อเคลียร์สถานะที่อาจจะค้างอยู่
        try:
            self.dev.reset()
        except usb.core.USBError:
            pass

        # ตั้งค่า Configuration และจอง Interface
        try:
            self.dev.set_configuration()
            # จองสิทธิ์การใช้ Interface (แก้ปัญหา Errno 5)
            usb.util.claim_interface(self.dev, 0)
        except usb.core.USBError as e:
            sys.exit(f"Error setting configuration or claiming interface: {e}")
            
        print("เชื่อมต่อ ZK9500 สำเร็จ!")
        return True

    def disconnect(self):
        """
        คืนสิทธิ์และคืนทรัพยากรให้ระบบเมื่อใช้งานเสร็จ
        """
        if self.dev is not None:
            try:
                # คืนสิทธิ์ Interface ให้ระบบ
                usb.util.release_interface(self.dev, 0)
            except usb.core.USBError:
                pass
                
            usb.util.dispose_resources(self.dev)
            self.dev = None
            print("ยกเลิกการเชื่อมต่ออุปกรณ์แล้ว")

    def control_transfer(self, bmRequestType, bRequest, wValue, wIndex, data_or_length):
        """
        ใช้สำหรับส่งคำสั่งควบคุม (Control Transfer)
        """
        if self.dev is None:
            raise Exception("อุปกรณ์ยังไม่ได้เชื่อมต่อ กรุณาเรียกใช้ connect() ก่อน")
            
        try:
            response = self.dev.ctrl_transfer(
                bmRequestType=bmRequestType,
                bRequest=bRequest,
                wValue=wValue,
                wIndex=wIndex,
                data_or_wLength=data_or_length,
                timeout=self.timeout
            )
            return response
        except usb.core.USBError as e:
            print(f"USB Control Transfer Error: {e}")
            return None

    def handshake(self):
        """
        ส่งคำสั่งปลุกเครื่องและรอรับ ACK
        """
        print("⚙️  Sending Handshake (Wake Up)...")
        
        payload = bytearray([0x00] * 16)
        
        try:
            # 1. ส่งคำสั่งปลุก
            self.control_transfer(
                bmRequestType=0x40,
                bRequest=0x80,      
                wValue=0x0000,
                wIndex=0x0000,
                data_or_length=payload
            )
            print("   -> Control Command Sent")
            
            # --- จุดที่แก้ไข: หน่วงเวลาให้อุปกรณ์หายใจแป๊บนึง ---
            time.sleep(0.1) 
            
            # 2. รอรับคำตอบ (ACK) 4 bytes
            try:
                # ลองช่องทางที่ 1 (EP 0x81)
                ack = self.dev.read(self.ep_status_in, 4, timeout=self.timeout)
                print(f"   <- ACK Received on EP 0x81: {[hex(x) for x in ack]}")
            except usb.core.USBError as e_ep1:
                print(f"   -> [EP 0x81 ว่างเปล่า] กำลังลองช่องทางที่ 2 (EP 0x82)...")
                # เคลียร์สถานะ Halt เผื่อมันค้าง
                self.dev.clear_halt(self.ep_image_in)
                
                # ลองช่องทางที่ 2 (EP 0x82)
                ack = self.dev.read(self.ep_image_in, 4, timeout=self.timeout)
                print(f"   <- ACK Received on EP 0x82: {[hex(x) for x in ack]}")
            
            # เช็คคำตอบ
            if ack[0] == 0x00:
                print("✅ Handshake Success! เครื่องตื่นแล้วพร้อมทำงาน")
            else:
                print("❌ Handshake Failed (Non-zero ACK)")
                
        except usb.core.USBError as e:
            print(f"❌ Error during Handshake: {e}")

    def detect_finger(self):
        """
        ส่งคำสั่ง 0xEA เพื่อเช็คว่ามีนิ้วสัมผัสที่หน้ากระจกเซ็นเซอร์หรือไม่
        """
        try:
            response = self.dev.ctrl_transfer(
                bmRequestType=0xc0,
                bRequest=0xea,
                wValue=0x0000,
                wIndex=0x0000,
                data_or_wLength=10,
                timeout=self.timeout
            )
            
            status = response[0]
            
            # --- [เพิ่มส่วน Debug] ---
            # เช็คว่าสถานะมีการเปลี่ยนแปลงหรือไม่ (จะได้ไม่ปริ้นรัวๆ จนตาลาย)
            if not hasattr(self, 'last_status') or self.last_status != status:
                print(f"👀 [Debug] สถานะเซ็นเซอร์: {hex(status)} | Data: {[hex(x) for x in response]}")
                self.last_status = status
            # ------------------------
            
            # ปรับให้จับค่าทุกอย่างที่ไม่ใช่ 0 ชั่วคราว เพื่อดูว่ามันจะไปต่อได้ไหม
            # หรือถ้าเรารู้เลขที่แน่นอนแล้ว ค่อยกลับมาแก้ตรงนี้ครับ
            if status != 0x00: 
                return True
            else:
                return False
                
        except usb.core.USBError as e:
            return False
        
    def capture_image(self):
        """
        ส่งคำสั่งถ่ายภาพ ดึงขนาดภาพ และดึงข้อมูลลายนิ้วมือ (Raw Data)
        """
        print("📸 Sending Capture Command...")
        
        try:
            # 1. ส่งคำสั่ง 0xE5 (ขอถ่ายภาพ) และอ่านค่ากลับมา 5 bytes
            # การใช้ ctrl_transfer แบบอ่านข้อมูล (0xC0) PyUSB จะ Return ค่ากลับมาเป็น Array
            response = self.dev.ctrl_transfer(
                bmRequestType=0xc0,
                bRequest=0xe5,
                wValue=0x0000,
                wIndex=0x0000,
                data_or_wLength=5,  # ขอข้อมูล 5 bytes
                timeout=self.timeout
            )
            
            print(f"   -> Image Info Received: {[hex(x) for x in response]}")
            
            # ตรวจสอบว่าได้ข้อมูลมาครบหรือไม่
            if len(response) >= 4:
                # คำนวณความกว้างและความสูง (Little Endian: เอา byte หลังคูณ 256 แล้วบวก byte แรก)
                width = response[0] | (response[1] << 8)
                height = response[2] | (response[3] << 8)
                
                print(f"   -> Image Size: {width} x {height} pixels")
                
                # คำนวณขนาดไฟล์ภาพ (Raw 8-bit Grayscale = 1 pixel / 1 byte)
                expected_size = width * height
                
                if expected_size == 0:
                    print("❌ Error: ขนาดภาพเป็น 0 เครื่องอาจจะยังไม่ได้สแกน")
                    return None
                    
                # 2. ดูดข้อมูลภาพผ่านช่องทาง Bulk (EP 0x82)
                print(f"   -> Reading {expected_size} bytes of image data...")
                
                # ให้เวลาเซ็นเซอร์ถ่ายรูปนิดนึง (ปรับลด/เพิ่มได้)
                time.sleep(0.1) 
                
                image_data = self.dev.read(self.ep_image_in, expected_size, timeout=2000) # เผื่อเวลาให้โอนไฟล์
                
                print(f"✅ Capture Success! ดึงข้อมูลสำเร็จ: {len(image_data)} bytes.")
                return image_data, width, height
                
            else:
                print("❌ ไม่สามารถดึงข้อมูลขนาดภาพได้")
                return None
                
        except usb.core.USBError as e:
            print(f"❌ Error during Image Capture: {e}")
            return None

if __name__ == "__main__":
    import time # อย่าลืม import time ไว้ด้านบนสุดของไฟล์ด้วยนะครับ
    scanner = ZK9500()
    
    try:
        scanner.connect()
        scanner.handshake()
        
        print("\n=== 🟢 ระบบพร้อมทำงาน กรุณาวางนิ้วบนเครื่องสแกน ===")
        
        # วนลูปเพื่อรอจนกว่าจะตรวจพบนิ้วมือ
        while True:
            # เช็คว่ามีนิ้วแตะเซ็นเซอร์หรือไม่
            if scanner.detect_finger():
                print("\n👇 ตรวจพบการวางนิ้ว! กำลังสแกนภาพ...")
                
                # พอนิ้ววางแล้ว ค่อยส่งคำสั่งถ่ายภาพ (0xE5) ที่เราเขียนไว้
                result = scanner.capture_image()
                
                if result is not None:
                    img_data, w, h = result
                    
                    # บันทึกเป็นไฟล์ Raw
                    with open("fingerprint.raw", "wb") as f:
                        f.write(img_data)
                        
                    print(f"💾 บันทึกไฟล์ fingerprint.raw สำเร็จ! (ขนาด {w}x{h})")
                    break # ถ่ายเสร็จแล้วออกจากลูปเลย
                else:
                    print("⚠️ ถ่ายภาพไม่สำเร็จ กำลังรอสแกนใหม่...")
                    time.sleep(1)
            
            # หน่วงเวลาลูปนิดนึงเพื่อไม่ให้ CPU กิน 100%
            time.sleep(0.1) 
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
    except KeyboardInterrupt:
        print("\nผู้ใช้ยกเลิกการทำงาน")
    finally:
        scanner.disconnect()