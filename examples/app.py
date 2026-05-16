import time
import io
import threading
import logging

# Import the ZK9500 library directly
from zk9500 import ZK9500

# Suppress verbose USB logs to keep the console clean
logging.basicConfig(level=logging.WARNING)

# ==========================================
# Global State Variables
# ==========================================
app_state = "VERIFY"  # Default mode: Always standby for verification
enroll_id = None
enroll_target_count = 3

def hardware_task(scanner):
    """
    [Hardware Thread] 
    Runs continuously in the background, monitoring the scanner for fingerprints.
    """
    global app_state, enroll_id, enroll_target_count
    
    while app_state != "EXIT":
        if app_state == "VERIFY":
            # ----------------------------------------
            # 1. VERIFY MODE (Continuous Standby)
            # ----------------------------------------
            if scanner.detect_finger():
                capture_result = scanner.capture_image()
                if capture_result:
                    raw_data, w, h = capture_result
                    img = scanner.decode_from_bytes(raw_data)
                    
                    if img:
                        # Convert PIL Image to Bytes in memory
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        
                        # Verify the captured fingerprint against the database
                        is_match, matched_id, score = scanner.verify(img_byte_arr.getvalue(), threshold=35)
                        
                        print("\n" + "="*45)
                        if is_match:
                            print(f"✅ Access Granted! Welcome Employee ID: {matched_id}")
                            print(f"   (Match Score: {score})")
                        else:
                            print(f"❌ Access Denied: Fingerprint not found. (Score: {score})")
                        print("="*45)
                        
                        # Reprint the prompt to keep the UI clear
                        print("\n[STANDBY] Place finger to verify, or type '1' and press Enter to enroll: ", end="", flush=True)
                        
                # Delay to prevent rapid re-scanning of the same finger
                time.sleep(1.5) 
            else:
                # Brief pause to reduce CPU usage when no finger is detected
                time.sleep(0.1)
                
        elif app_state == "ENROLL":
            # ----------------------------------------
            # 2. ENROLL MODE (Triggered via keyboard input)
            # ----------------------------------------
            images_bytes = []
            print(f"\n\n[Hardware] Starting {enroll_target_count}-step enrollment for ID {enroll_id}")
            
            for i in range(enroll_target_count):
                print(f"--- Scan {i+1}/{enroll_target_count} ---")
                print(">> Please place your finger on the scanner <<")
                
                captured = False
                while not captured and app_state == "ENROLL":
                    if scanner.detect_finger():
                        capture_result = scanner.capture_image()
                        if capture_result:
                            raw_data, w, h = capture_result
                            img = scanner.decode_from_bytes(raw_data)
                            if img:
                                img_byte_arr = io.BytesIO()
                                img.save(img_byte_arr, format='PNG')
                                images_bytes.append(img_byte_arr.getvalue())
                                print("✅ Image captured successfully.")
                                captured = True
                    time.sleep(0.1)
                    
                if i < (enroll_target_count - 1):
                    print(">> Please lift your finger... shift or tilt it slightly (Waiting 2s)")
                    time.sleep(2)
                    
            # Save the enrolled templates to the database
            if len(images_bytes) == enroll_target_count:
                scanner.enroll(enroll_id, images_bytes)
                print(f"\n🎉 Enrollment completed! Saved {enroll_target_count} templates for ID {enroll_id}.")
                
            # Restore the state back to VERIFY mode
            app_state = "VERIFY"
            print("\n[STANDBY] Place finger to verify, or type '1' and press Enter to enroll: ", end="", flush=True)

def main():
    global app_state, enroll_id, enroll_target_count
    
    print("="*55)
    print(" ZK9500 Fingerprint Scanner (Continuous Standby Mode)")
    print("="*55)
    
    # Initialize the scanner (which now handles both hardware and DB internally)
    scanner = ZK9500(db_name="fingerprints.sqlite")
    
    if not scanner.connect():
        print("❌ Failed to connect to the scanner.")
        return
        
    scanner.handshake()
    scanner.setup_normal_mode()
    
    # Start the background hardware thread
    hw_thread = threading.Thread(target=hardware_task, args=(scanner,), daemon=True)
    hw_thread.start()
    
    time.sleep(0.5) # Wait briefly for the thread to initialize
    
    try:
        while True:
            if app_state == "VERIFY":
                # Main thread handles keyboard input
                choice = input("\n[STANDBY] Place finger to verify, or type '1' and press Enter to enroll: ")
                
                if choice == '1':
                    user_id_str = input("Enter Employee ID (Numbers only): ")
                    if user_id_str.isdigit():
                        enroll_id = int(user_id_str)
                        count_str = input("How many scans for enrollment? (Recommended: 3): ")
                        enroll_target_count = int(count_str) if count_str.isdigit() else 3
                        
                        # Signal the background thread to switch to ENROLL mode
                        app_state = "ENROLL"
                        
                        # Block the main thread until the background thread finishes enrolling
                        while app_state == "ENROLL":
                            time.sleep(0.5)
                    else:
                        print("❌ Invalid input! Employee ID must be a number.")
                        
                elif choice.lower() in ['exit', 'quit', '0', '3']:
                    app_state = "EXIT"
                    break
            else:
                # Sleep while the background thread is busy enrolling
                time.sleep(0.5)
                
    except KeyboardInterrupt:
        app_state = "EXIT"
        print("\nOperation cancelled by user.")
    finally:
        print("\nDisconnecting device...")
        scanner.disconnect()

if __name__ == "__main__":
    main()