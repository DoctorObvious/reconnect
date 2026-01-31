import fitdecode
import zipfile
import os

# --- CONFIGURATION ---
# Path to your "UploadedFiles...Part1.zip"
ZIP_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1.zip" 

def hunt_for_hr():
    print(f"--- Hunting for Heart Rate in: {os.path.basename(ZIP_PATH)} ---")
    
    files_checked = 0
    
    try:
        with zipfile.ZipFile(ZIP_PATH) as zf:
            fit_files = [f for f in zf.namelist() if f.lower().endswith('.fit')]
            
            for filename in fit_files:
                # We only care about monitoring_b files
                # (Optimization: We read the file header first to check type)
                with zf.open(filename) as f:
                    file_bytes = f.read()
                    
                    # 1. Check File Type
                    is_monitoring = False
                    with fitdecode.FitReader(file_bytes) as fit:
                        for frame in fit:
                            if isinstance(frame, fitdecode.FitDataMessage):
                                if frame.name == 'file_id' and (frame.get_value('type') == 'monitoring_b' or frame.get_value('type') == 15):
                                    is_monitoring = True
                                    break
                    
                    if not is_monitoring:
                        continue # Skip non-monitoring files

                    files_checked += 1
                    if files_checked % 10 == 0:
                        print(f"Scanning file #{files_checked}...")

                    # 2. Deep Scan for 'heart_rate'
                    # We look through EVERY message in the file, not just the first 5
                    with fitdecode.FitReader(file_bytes) as fit:
                        msg_count = 0
                        found_hr = False
                        
                        for frame in fit:
                            if isinstance(frame, fitdecode.FitDataMessage):
                                if frame.name == 'monitoring':
                                    msg_count += 1
                                    
                                    # CHECK FOR HEART RATE
                                    if frame.has_field('heart_rate'):
                                        print(f"\n✅ SUCCESS! Found 'heart_rate' in file: {filename}")
                                        print(f"   -> Found at message #{msg_count}")
                                        print(f"   -> Timestamp: {frame.get_value('timestamp')}")
                                        print(f"   -> Heart Rate: {frame.get_value('heart_rate')}")
                                        return # WE WON! Exit script.
            
            print(f"\n❌ Scanned {files_checked} monitoring files and found NO 'heart_rate' field.")
            print("Possibilities:")
            print("1. Your device doesn't log 24/7 HR (unlikely).")
            print("2. HR is stored in a 'compressed' array (check for field 'heart_rate_array'?).")
            print("3. HR is stored in a weird 'Unknown' field.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    hunt_for_hr()