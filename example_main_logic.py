#!/usr/bin/env python3
"""
ZK9500 Example - ตาม logic ของ main.py ตรงๆ
"""

import usb.core
import usb.util
import time


class ZK9500:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x1b55, idProduct=0x0124)
        if self.dev is None:
            raise ValueError("Device not found!")

        print("Hard Resetting device...")
        self.dev.reset()
        time.sleep(0.2)

    def send_cmd(self, bmRequestType, bRequest, wValue=0, wIndex=0, payload_or_length=None):
        """ส่ง Control Transfer"""
        try:
            return self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload_or_length, timeout=1000)
        except usb.core.USBError as e:
            print(f"USB Error (Req {bRequest}): {e}")
            return None

    def Open(self):
        """เปิด device และ init"""
        print("Sending Open/Init Sequence...")

        # 1. Wake up
        self.send_cmd(0x40, 224, 0, 0)

        # 2. Clear Memory
        self.send_cmd(0x40, 128, 0, 0, bytes([0] * 16))

        # 3. Read Register 85
        response = self.send_cmd(0xC0, 226, 0, 85, 2)
        if response is not None and len(response) > 0:
            print(f"Register 85: {response.tolist()} [OK]")
        else:
            print("Failed to read Register 85")
            return False

        # Poll registers 0-255 (แบบ main.py)
        print("Polling registers 0-255...")
        for i in range(255):
            self.send_cmd(0xC0, 231, 0, i, 1)

        # Initial status check
        self.send_cmd(0xC0, 234, 0, 0, 1)
        return True

    def wait_for_finger(self):
        """รอจนกว่าจะวางนิ้ว"""
        print("Ready - Please place finger on sensor...")

        while True:
            res = self.send_cmd(0xC0, 234, 0, 0, 1)

            if res and len(res) > 0:
                status = res[0]
                if status != 0 and status != 8:
                    print(f"Finger detected! Status: {hex(status)}")
                    return True

            time.sleep(0.05)

    def ReciveImage(self):
        """
        รับภาพจาก Endpoint 0x82
        (ตาม logic ของ main.py - ไม่ได้ส่ง capture command ก่อน)
        """
        print("Reading image from Endpoint 0x82...")

        all_data = bytearray()
        prev_size = float('inf')

        while True:
            try:
                data = self.dev.read(0x82, 65536, timeout=10000)

                if len(data) == 0:
                    print("Empty data, ending")
                    break

                all_data.extend(data)
                curr_size = len(data)
                print(f"+{curr_size} bytes (total: {len(all_data)})")

                if curr_size < prev_size:
                    print("Last frame detected")
                    break

                prev_size = curr_size

            except usb.core.USBError as e:
                print(f"USB Error: {e}")
                break

        if len(all_data) > 1000:
            print(f"Success! Image size: {len(all_data)} bytes")
            with open("fingerprint.raw", "wb") as f:
                f.write(all_data)
            return True
        else:
            print(f"Warning: Only {len(all_data)} bytes received")
            return False


def main():
    try:
        zk = ZK9500()
        print("Device reset successfully.")

        zk.Open()

        if zk.wait_for_finger():
            zk.ReciveImage()

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'zk' in locals() and zk.dev is not None:
            usb.util.dispose_resources(zk.dev)


if __name__ == "__main__":
    main()