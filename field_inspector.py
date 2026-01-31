import fitdecode
import zipfile
import os

# --- CONFIGURATION ---
# Path to your "UploadedFiles...Part1.zip"
ZIP_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1.zip" 

def inspect_fields():
    print(f"--- Inspecting fields in: {os.path.basename(ZIP_PATH)} ---")
    
    try:
        with zipfile.ZipFile(ZIP_PATH) as zf:
            fit_files = [f for f in zf.namelist() if f.lower().endswith('.fit')]
            
            # loop through files until we find a 'monitoring_b' one
            for filename in fit_files:
                with zf.open(filename) as f:
                    file_bytes = f.read()
                    
                    # 1. Check if it's the right type
                    is_target = False
                    with fitdecode.FitReader(file_bytes) as fit:
                        for frame in fit:
                            if isinstance(frame, fitdecode.FitDataMessage):
                                if frame.name == 'file_id' and (frame.get_value('type') == 'monitoring_b' or frame.get_value('type') == 15):
                                    is_target = True
                                    break
                    
                    if is_target:
                        print(f"\nFOUND TARGET FILE: {filename}")
                        print("Dumping first 5 'monitoring' messages...")
                        
                        # 2. Re-read and dump 'monitoring' fields
                        count = 0
                        with fitdecode.FitReader(file_bytes) as fit:
                            for frame in fit:
                                if isinstance(frame, fitdecode.FitDataMessage):
                                    if frame.name == 'monitoring':
                                        count += 1
                                        print(f"\n--- Monitoring Msg #{count} ---")
                                        
                                        # Print every field and its value
                                        for field in frame.fields:
                                            if field.value is not None:
                                                print(f"  [{field.name}]: {field.value} (Units: {field.units})")
                                        
                                        if count >= 5:
                                            return # Found what we needed, exit completely
            
            print("No monitoring_b files found in this zip.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_fields()