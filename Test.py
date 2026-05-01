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
            self.dev.reset()
        time.sleep(0.2)

    def send_cmd(self, bmRequestType, bRequest, wValue=0, wIndex=0, payload_or_length=None):
        try:
            return self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload_or_length, timeout=1000)
        except usb.core.USBError as e:
            print(f"⚠️ USB Error (Request {bRequest}): {e}")
            return None

    def Open(self):
        print("⚙️  Sending Open/Init Sequence...")

        print("   -> Sending Wake Up command (Req: 224)")
        self.send_cmd(0x40, 224, 0, 0)

        print("   -> Sending Clear Memory command (Req: 128)")
        zero_payload = bytes([0] * 16)
        self.send_cmd(0x40, 128, 0, 0, payload_or_length=zero_payload)

        response = self.send_cmd(0xC0, 226, 0, 85, payload_or_length=2)
        if response is not None and len(response) > 0:
            data = response.tolist()
            print(f"   -> Register 85 Check: {data} (Hex: {[hex(x) for x in data]}) [OK]")
        else:
            print("   -> Failed to read Register 85 (Req: 226)")
            return False

        print("   -> Starting polling loop (Press Ctrl+C to stop)...")
        device_info = {
            "DeviceModel": usb.util.get_string(self.dev, self.dev.iProduct),
            "SerialNumber": usb.util.get_string(self.dev, self.dev.iSerialNumber),
            "DeviceAddress": self.dev.address,
            "BusNumber": self.dev.bus
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
                        return True

                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n🛑 หยุดการรอนิ้วโดยผู้ใช้")
            return False

    def ReciveImage(self):
        try:
            print("📸 กำลังร้องขอข้อมูลภาพจาก Endpoint 0x82...")

            # รอให้เซนเซอร์ประมวลผลภาพ
            time.sleep(0.3)

            # ถาม status ก่อนว่าพร้อมส่งภาพหรือยัง
            print("   -> Checking device status...")
            for attempt in range(5):
                res = self.send_cmd(0xC0, 234, 0, 0, payload_or_length=1)
                if res and len(res) > 0:
                    status = res[0]
                    print(f"   Status check #{attempt+1}: {hex(status)}")
                    # ถ้า status เป็น 0x10 หรือ 0x11 อาจหมายถึงพร้อมส่งภาพ
                    if status == 0x10 or status == 0x11:
                        print("   -> Device ready to send image")
                        break
                time.sleep(0.1)

            # ลองส่ง BULK OUT ไปก่อน (trigger) - ตาม pattern ใน pcapng
            print("   -> Sending BULK OUT trigger to 0x82...")
            try:
                # ส่ง zero-length BULK OUT ไปที่ endpoint 0x02 (OUT counterpart ของ 0x82)
                self.dev.write(0x02, bytes(), timeout=1000)
                print("   -> BULK OUT sent")
            except Exception as e:
                print(f"   -> BULK OUT error: {e}")

            time.sleep(0.1)

            all_data = bytearray()
            prev_size = float('inf')
            chunk_num = 0
            max_attempts = 50

            while chunk_num < max_attempts:
                chunk_num += 1
                data = self.dev.read(0x82, 65536, timeout=15000)

                raw = data.tolist()
                print(f"   Chunk {chunk_num}: {len(data)} bytes -> {raw[:10] if len(raw) > 0 else 'empty'}")

                if len(data) == 0:
                    # ถ้าได้ข้อมูลว่าง 3 ครั้งติด = จบ
                    print("   -> ได้ข้อมูลว่าง, จบการรับ")
                    break

                # ถ้าได้แค่ 4 bytes และเป็น [0,0,0,0] หรือ [1,0,0,0] แปลว่าเป็น status ไม่ใช่ภาพ
                if len(data) <= 4 and all(b == 0 for b in raw):
                    print("   -> ได้ status [0,0,0,0] -> ข้ามไปรอต่อ")
                    time.sleep(0.2)
                    continue

                all_data.extend(data)
                curr_size = len(data)

                # ถ้าได้ขนาดเล็กกว่า max ที่เป็นไปได้ = frame สุดท้าย
                if curr_size < prev_size and curr_size < 65536:
                    print(f"   -> ตรวจพบ frame สุดท้าย ({curr_size} < {prev_size})")
                    break

                prev_size = curr_size

            if len(all_data) > 1000:
                print(f"✅ สำเร็จ! ได้รับข้อมูลภาพขนาด: {len(all_data)} ไบต์")
                with open("fingerprint.raw", "wb") as f:
                    f.write(all_data)
                return True
            else:
                print(f"⚠️ ได้รับข้อมูลเพียง {len(all_data)} ไบต์: {all_data.hex() if all_data else 'empty'}")
                print(f"   ลองอ่านไป {chunk_num} ครั้งแล้วไม่ได้ภาพจริง")
                return False

        except usb.core.USBError as e:
            print(f"❌ อ่านข้อมูลภาพล้มเหลว: {e}")
            return False

if __name__ == "__main__":
    try:
        zk = ZK9500()
        print("Device reset successfully.")

        zk.Open()
        if zk.wait_for_finger():
            zk.ReciveImage()

    except ValueError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")
    finally:
        if 'zk' in locals() and zk.dev is not None:
            usb.util.dispose_resources(zk.dev)