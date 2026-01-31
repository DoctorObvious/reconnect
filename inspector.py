import fitdecode
import sys

# --- CONFIGURATION ---
# Point this to the single extracted .fit file you want to test
TEST_FILE_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1/mark@markphillips.net_117889976276.fit"

def inspect_fit(file_path):
    print(f"--- INSPECTING: {file_path} ---")
    
    try:
        with fitdecode.FitReader(file_path) as fit:
            # 1. Check the File ID (What type of file is this?)
            # This is usually the first message and tells us if it's Activity, Monitoring, etc.
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'file_id':
                        print(f"FILE TYPE: {frame.get_value('type')}")
                        print(f"MANUFACTURER: {frame.get_value('manufacturer')}")
                        print(f"PRODUCT: {frame.get_value('product')}")
                        break
            
            # 2. Reset and scan for message types
            fit.close()
            
        # Re-open to scan content (naive re-open for simplicity)
        with fitdecode.FitReader(file_path) as fit:
            message_counts = {}
            sample_fields = {}

            print("\n--- SCANNING MESSAGES ---")
            for i, frame in enumerate(fit):
                if isinstance(frame, fitdecode.FitDataMessage):
                    # Count message types
                    if frame.name not in message_counts:
                        message_counts[frame.name] = 0
                        # Capture fields of the first occurrence of this message type
                        sample_fields[frame.name] = [f.name for f in frame.fields]
                    
                    message_counts[frame.name] += 1
                    
                    # Stop if we've seen too many to keep it fast
                    if i > 5000: 
                        print("... (Stopping scan after 5000 messages)")
                        break

            print("\n--- RESULTS ---")
            for msg_name, count in message_counts.items():
                print(f"Message '{msg_name}': {count} occurrences")
                if msg_name in ['record', 'monitoring']:
                    print(f"   -> Fields found: {sample_fields[msg_name]}")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_fit(TEST_FILE_PATH)