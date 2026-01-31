import streamlit as st
import pandas as pd
import plotly.express as px
import fitdecode
import zipfile
import io

st.set_page_config(page_title="Garmin Deep Dive", layout="wide")
st.title("❤️ Garmin Heart Rate Explorer (Full History)")

# --- Helper: Parse FIT file ---
def parse_fit_file(file_bytes, file_name):
    data = []
    try:
        with fitdecode.FitReader(file_bytes) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    # We strictly look for 'monitoring' (Daily HR)
                    # We ignore 'record' (Activity GPS/HR) to speed things up
                    if frame.name == 'monitoring' and frame.has_field('heart_rate'):
                        timestamp = frame.get_value('timestamp')
                        hr = frame.get_value('heart_rate')
                        if timestamp and hr:
                            data.append({
                                'timestamp': timestamp,
                                'heart_rate': hr,
                                'source_file': file_name
                            })
    except Exception:
        pass # Skip corrupted files
    return data

# --- Main App ---
uploaded_zip = st.file_uploader("Upload Master Garmin Export (ZIP)", type="zip")

if uploaded_zip:
    all_hr_data = []
    
    with st.spinner("Scanning ZIP structure..."):
        try:
            main_zip = zipfile.ZipFile(uploaded_zip)
            all_files = main_zip.namelist()
            
            # Find ALL "UploadedFiles" zips
            part_files = [f for f in all_files if "UploadedFiles" in f and f.endswith(".zip")]
            
            if not part_files:
                st.error("Could not find any 'UploadedFiles' parts.")
            else:
                st.info(f"Found {len(part_files)} data parts. Merging them into one dataset...")
                
                # --- Progress Bar for PARTS ---
                part_progress = st.progress(0)
                
                # Loop through Part 1, Part 2, Part 3...
                for i, part_name in enumerate(part_files):
                    
                    # Open the inner zip
                    inner_zip_bytes = main_zip.read(part_name)
                    inner_zip = zipfile.ZipFile(io.BytesIO(inner_zip_bytes))
                    
                    # Find FIT files inside this part
                    fit_files = [f for f in inner_zip.namelist() if f.lower().endswith('.fit')]
                    
                    # --- Progress Bar for FILES inside the part ---
                    # We'll just show a status text update to avoid double-progress-bar confusion
                    status_text = st.empty()
                    
                    # OPTIONAL: Still limit files per part for testing? 
                    # Set to 1000 or len(fit_files) for "Full Mode"
                    files_to_process = fit_files # [:50] # Uncomment [:50] to test quickly
                    
                    for j, fit_file in enumerate(files_to_process):
                        status_text.text(f"Processing {part_name} | File {j+1}/{len(files_to_process)}")
                        
                        with inner_zip.open(fit_file) as f:
                            # Parse
                            file_data = parse_fit_file(f.read(), fit_file)
                            all_hr_data.extend(file_data)
                    
                    # Update Part Progress
                    part_progress.progress((i + 1) / len(part_files))
                
                st.success("Processing Complete!")

                # --- Visualization ---
                if all_hr_data:
                    df = pd.DataFrame(all_hr_data)
                    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                    df['date'] = df['timestamp'].dt.date
                    
                    # Sort by date just in case Parts were out of order
                    df = df.sort_values('timestamp')
                    
                    st.metric("Total Heart Rate Samples", f"{len(df):,}")
                    
                    # Group by Day
                    daily_stats = df.groupby('date')['heart_rate'].mean().reset_index()
                    
                    fig = px.scatter(daily_stats, x='date', y='heart_rate', 
                                     title="Daily Average Heart Rate (All Time)",
                                     labels={'heart_rate': 'Avg HR (bpm)'})
                    
                    fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="date"))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No monitoring data found. These parts might contain only Activity data.")

        except Exception as e:
            st.error(f"Error: {e}")