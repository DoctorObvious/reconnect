import fitdecode
import zipfile
import os

# --- CONFIGURATION ---
# Path to your "UploadedFiles...Part1.zip"
ZIP_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1.zip" 

def inspect_message_6():
    print(f"--- Drilling into Message #6 in: {os.path.basename(ZIP_PATH)} ---")
    
    with zipfile.ZipFile(ZIP_PATH) as zf:
        fit_files = [f for f in zf.namelist() if f.lower().endswith('.fit')]
        
        # Find the first 'monitoring_b' file again
        for filename in fit_files:
            with zf.open(filename) as f:
                file_bytes = f.read()
                
                # Check Type
                is_monitoring = False
                with fitdecode.FitReader(file_bytes) as fit:
                    for frame in fit:
                        if isinstance(frame, fitdecode.FitDataMessage):
                            if frame.name == 'file_id' and (frame.get_value('type') == 'monitoring_b' or frame.get_value('type') == 15):
                                is_monitoring = True
                                break
                
                if is_monitoring:
                    print(f"Target File: {filename}")
                    
                    # Re-read and stop at Message #6
                    with fitdecode.FitReader(file_bytes) as fit:
                        msg_count = 0
                        for frame in fit:
                            if isinstance(frame, fitdecode.FitDataMessage):
                                if frame.name == 'monitoring':
                                    msg_count += 1
                                    
                                    if msg_count == 6:
                                        print("\n--- MESSAGE #6 FIELDS ---")
                                        # Print ALL available fields
                                        for field in frame.fields:
                                            print(f"Key: '{field.name}' | Value: {field.value} | Units: {field.units}")
                                        
                                        # Also check for 'timestamp_16' explicitly just in case
                                        if frame.has_field('timestamp_16'):
                                            print("\n✅ Found 'timestamp_16'!")
                                        return
    print("Could not find a monitoring file to inspect.")

if __name__ == "__main__":
    inspect_message_6()