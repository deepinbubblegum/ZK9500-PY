import usb.core
import usb.util
import sys
import time
import logging
from typing import Optional, Tuple, Any

from .decoder import decode_from_bytes, decode_from_file
from .matcher import FingerprintMatcher

# ตั้งค่า Logger เฉพาะสำหรับไลบรารีตัวนี้
logger = logging.getLogger(__name__)

class ZK9500:
    def __init__(self, id_vendor: int = 0x1b55, id_product: int = 0x0124, db_name=None):
        self.idVendor = id_vendor
        self.idProduct = id_product
        self.dev = None
        
        if db_name is not None:
            self.matcher = FingerprintMatcher(db_name=db_name)
        
        self.timeout = 5000
        self.ep_status_in = 0x81
        self.ep_image_in = 0x82

    def enroll(self, user_id: int, list_of_image_bytes: list):
        return self.matcher.enroll(user_id, list_of_image_bytes)

    def verify(self, image_bytes: bytes, threshold=35):
        return self.matcher.verify(image_bytes, threshold=threshold)

    def connect(self) -> bool:
        """ Connect and initialize the ZKTeco 9500 device """
        self.dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.dev is None:
            raise ValueError(f"ZKTeco 9500 device not found (VID: {hex(self.idVendor)}, PID: {hex(self.idProduct)})")

        if self.dev.is_kernel_driver_active(0):
            try:
                self.dev.detach_kernel_driver(0)
            except usb.core.USBError as e:
                logger.error(f"Could not detach kernel driver: {e}")
                sys.exit(1)

        try:
            # clear any stale status by sending a Reset and Reboot sequence
            self.dev.reset()
            time.sleep(0.5) 
            self.dev.set_configuration()
            usb.util.claim_interface(self.dev, 0)
            
            # เคลียร์ท่อข้อมูลขยะ
            for ep in [self.ep_status_in, self.ep_image_in]:
                self.dev.clear_halt(ep)
                try:
                    self.dev.read(ep, 1024, timeout=100)
                except usb.core.USBError:
                    pass
        except usb.core.USBError as e:
            logger.error(f"Error during initialization: {e}")
            sys.exit(1)
            
        logger.info("✅ ZK9500 Connected Successfully!")
        return True

    def control_transfer(self, bmRequestType: int, bRequest: int, wValue: int, wIndex: int, data_or_length: Any) -> Optional[Any]:
        if self.dev is None: 
            return None
        try:
            return self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_length, self.timeout)
        except usb.core.USBError:
            return None

    def handshake(self) -> bool:
        logger.debug("⚙️ Sending Handshake (0x80)...")
        payload = bytearray([0x00] * 16)
        self.control_transfer(0x40, 0x80, 0, 0, payload)
        time.sleep(0.1)
        try:
            ack = self.dev.read(self.ep_image_in, 4, timeout=self.timeout)
            if ack[0] == 0x00:
                logger.info("✅ Handshake Success!")
                return True
        except usb.core.USBError:
            pass
        return False

    def reboot_hardware(self):
        """ send 0xF0 (wIndex=0x30) to force Reboot and power off completely """
        logger.debug("🚀 Sending Hardware Reboot (0xF0)...")
        self.control_transfer(0x40, 0xf0, 0, 0x30, None)
        time.sleep(0.2)

    def detect_finger(self) -> bool:
        try:
            response = self.control_transfer(0xc0, 0xea, 0, 0, 10)
            if response and response[0] != 0:
                return True
        except usb.core.USBError:
            pass
        return False
        
    def capture_image(self) -> Optional[Tuple[Any, int, int]]:
        logger.info("📸 Capturing Image...")
        try:
            res = self.control_transfer(0xc0, 0xe5, 0, 0, 5)
            if res and len(res) >= 4:
                width = res[0] | (res[1] << 8)
                height = res[2] | (res[3] << 8)
                image_data = self.dev.read(self.ep_image_in, width * height, timeout=self.timeout)
                return image_data, width, height
        except Exception as e:
            logger.error(f"❌ Capture Error: {e}")
        return None
        
    def disconnect(self):
        """ Gracefully disconnect and reset the device """
        if self.dev is not None:
            try:
                # 1. send Reboot to kill Auto-Detect mode immediately
                self.reboot_hardware()
                
                # 2. release interface
                try:
                    usb.util.release_interface(self.dev, 0)
                except usb.core.USBError: 
                    pass
                
                # 3. send Reset to USB bus as final step
                logger.debug("🔄 Finalizing Hardware Reset...")
                self.dev.reset()
            except Exception:
                pass
            usb.util.dispose_resources(self.dev)
            self.dev = None
            logger.info("🛑 Uninitialized and Disconnected.")

    def setup_normal_mode(self):
        """ Sending Magic Sequence for Normal Mode 112.5K """
        logger.debug("⚙️ Sending Magic Sequence for Normal Mode...")
        
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
            time.sleep(0.01)
            
        logger.info("✅ Normal Mode Configured!")

    @staticmethod
    def decode_from_bytes(raw_data: bytes):
        """
        Convert raw byte data to an image object (call via scanner.decode_from_bytes)
        """
        return decode_from_bytes(raw_data)

    @staticmethod
    def decode_from_file(filepath: str, save_output: bool = True):
        """
        Read a .raw file and convert it to an image
        """
        return decode_from_file(filepath, save_output)