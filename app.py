import streamlit as st
import pandas as pd
import plotly.express as px
import fitdecode
import zipfile
import io
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="Garmin Health Explorer", layout="wide")
st.title("❤️ Garmin Heart Rate Explorer (Compressed Time Support)")

# --- CONFIGURATION ---
# UPDATE THIS PATH to your local Unzipped Part 1 folder
LOCAL_ZIP_PATH = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files" 

# --- Helper: The Timekeeper Parser ---
def process_fit_file(file_bytes, source_name):
    data = []
    
    # We need a running "current time" to handle the compressed timestamp_16 fields
    current_time = None
    
    try:
        with fitdecode.FitReader(file_bytes) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'monitoring':
                        
                        # --- TIME DECODING LOGIC ---
                        record_time = None
                        
                        # Case A: Full Timestamp (The Reference)
                        if frame.has_field('timestamp'):
                            raw_ts = frame.get_value('timestamp')
                            if raw_ts:
                                current_time = raw_ts
                                record_time = current_time
                        
                        # Case B: Compressed Timestamp_16 (The Update)
                        elif frame.has_field('timestamp_16') and current_time:
                            ts_16 = frame.get_value('timestamp_16')
                            
                            # Calculate the delta from the previous known time
                            # We need the integer timestamp of the current_time to do bitwise math
                            # (Garmin timestamps are seconds since Dec 31, 1989, but standard UNIX math works for delta)
                            curr_ts_int = int(current_time.timestamp())
                            
                            # The Formula: Add the difference, handling the 16-bit rollover
                            delta = (ts_16 - curr_ts_int) & 0xFFFF
                            
                            # Update our running clock
                            current_time = current_time + timedelta(seconds=delta)
                            record_time = current_time
                            
                        # --- DATA EXTRACTION ---
                        if record_time and frame.has_field('heart_rate'):
                            hr = frame.get_value('heart_rate')
                            data.append({
                                'timestamp': record_time,
                                'heart_rate': hr,
                                'source': source_name
                            })
                            
    except Exception:
        pass
    return data

# --- Helper: Fast File Type Check ---
def is_monitoring_file(file_bytes):
    try:
        with fitdecode.FitReader(file_bytes) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'file_id':
                        type_val = frame.get_value('type')
                        # Check for string 'monitoring_b' OR int 15
                        return type_val == 'monitoring_b' or type_val == 15
    except:
        return False
    return False

# --- Main App Logic ---
if os.path.exists(LOCAL_ZIP_PATH):
    uploaded_zips = [os.path.join(LOCAL_ZIP_PATH, f) for f in os.listdir(LOCAL_ZIP_PATH) if f.endswith('.zip') and "UploadedFiles" in f]
    # Sort the Zips themselves (Part1, Part2, Part3)
    uploaded_zips.sort() 
    
    st.info(f"📂 Scanning folder: `{LOCAL_ZIP_PATH}`")
    st.write(f"Found {len(uploaded_zips)} zip archives.")
else:
    st.error(f"Path not found: {LOCAL_ZIP_PATH}")
    uploaded_zips = []

if uploaded_zips:
    if st.button("Generate Heart Rate Plot"):
        
        # Increased default limit to ensure we cover full days
        max_files = st.slider("Max Files to Process", 100, 15000, 2000)
        
        all_hr_data = []
        files_processed = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for zip_path in uploaded_zips:
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    fit_files = [f for f in zf.namelist() if f.lower().endswith('.fit')]
                    
                    # --- CRITICAL FIX: SORT FILES ---
                    # This ensures we process Morning -> Afternoon -> Night in order
                    fit_files.sort()
                    
                    for i, fit_filename in enumerate(fit_files):
                        if files_processed >= max_files:
                            break
                        
                        # Update Visuals
                        progress_bar.progress(min(files_processed / max_files, 1.0))
                        status_text.text(f"Parsing File #{files_processed+1}: {fit_filename}")
                        
                        with zf.open(fit_filename) as f:
                            file_bytes = f.read()
                            
                            # 1. Filter Type
                            if is_monitoring_file(file_bytes):
                                # 2. Process with Timekeeper Logic
                                file_data = process_fit_file(file_bytes, fit_filename)
                                
                                if file_data:
                                    all_hr_data.extend(file_data)
                                    files_processed += 1
                                    
                if files_processed >= max_files:
                    break
                    
            except Exception as e:
                st.error(f"Error reading zip: {e}")

        st.success(f"✅ Processing Complete! Extracted {len(all_hr_data):,} data points from {files_processed} files.")
        
        if all_hr_data:
            df = pd.DataFrame(all_hr_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df['date'] = df['timestamp'].dt.date
            
            # --- Visualization ---
            st.subheader("📈 Daily Average Heart Rate")
            
            # Calculate coverage (how many minutes of data do we have per day?)
            daily_stats = df.groupby('date')['heart_rate'].agg(['mean', 'count']).reset_index()
            
            # A full day of monitoring (1 per min) should be ~1440 samples.
            # Let's flag days that have low coverage.
            daily_stats['coverage_percent'] = (daily_stats['count'] / 1440) * 100
            
            fig = px.scatter(daily_stats, x='date', y='mean', 
                             title="Daily Mean HR",
                             hover_data=['count', 'coverage_percent'],
                             color='coverage_percent', # Color dot by how "complete" the day is
                             labels={'mean': 'Avg HR', 'coverage_percent': '% of Day Recorded'})
            
            fig.add_scatter(x=daily_stats['date'], y=daily_stats['mean'].rolling(7).mean(), mode='lines', name='7-Day Avg', line=dict(color='red'))
            
            fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="date"))
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("View Raw Data Sample"):
                st.dataframe(df.head(1000))
        else:
            st.warning("No data found.")