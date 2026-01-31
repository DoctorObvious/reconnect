import fitdecode
import zipfile
import io
import os
from collections import defaultdict

# --- CONFIGURATION ---
# Path to your main unzipped folder (or the specific Part zip if you prefer)
# If you point this to the folder containing "UploadedFiles_0-_Part1.zip", it will scan the zips inside.
SEARCH_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files"

def get_fit_type(file_bytes):
    """Reads the first few messages to find the File ID."""
    try:
        with fitdecode.FitReader(file_bytes) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'file_id':
                        # type is an integer (e.g., 4=Activity, 15=Monitoring, 41=Settings)
                        return frame.get_value('type')
    except Exception:
        return "corrupted"
    return "unknown"

def scan_folder(folder_path):
    print(f"--- Scanning folder: {folder_path} ---")
    
    # Dictionary to count file types: { 4: 150, 15: 300, ... }
    type_counts = defaultdict(int)
    # Dictionary to keep a sample filename for each type
    type_samples = {}
    
    # 1. Look for Zip files (the "Parts")
    zip_files = [f for f in os.listdir(folder_path) if f.endswith(".zip")]
    
    for zip_name in zip_files:
        full_path = os.path.join(folder_path, zip_name)
        print(f"\nOpening archive: {zip_name}...")
        
        try:
            with zipfile.ZipFile(full_path, 'r') as zf:
                file_list = zf.namelist()
                fit_files = [f for f in file_list if f.lower().endswith('.fit')]
                print(f" -> Found {len(fit_files)} FIT files. Checking types (this may take a moment)...")
                
                for i, fit_file in enumerate(fit_files):
                    # Progress indicator every 100 files
                    if i > 0 and i % 100 == 0:
                        print(f"    ...checked {i} files")
                        
                    with zf.open(fit_file) as f:
                        ftype = get_fit_type(f.read())
                        type_counts[ftype] += 1
                        if ftype not in type_samples:
                            type_samples[ftype] = f"{zip_name} :: {fit_file}"
                            
        except Exception as e:
            print(f"Error reading {zip_name}: {e}")

    print("\n" + "="*40)
    print("FINAL REPORT: FILE TYPES FOUND")
    print("="*40)
    
    # Map of known Garmin types for readability
    known_types = {
        4: "Activity (Runs/Rides)",
        9: "Weight",
        15: "Monitoring_B (Detailed Wellness - THE TARGET)",
        32: "Monitoring_A (Daily Summary)",
        41: "Settings / Device Config",
        20: "Blood Pressure"
    }
    
    for ftype, count in sorted(type_counts.items(), key=lambda x: str(x[0])):
        readable = known_types.get(ftype, "Unknown/Other")
        print(f"Type {ftype} ({readable}): {count} files")
        print(f"   Sample: {type_samples.get(ftype)}")
        print("-" * 20)

if __name__ == "__main__":
    scan_folder(SEARCH_PATH)