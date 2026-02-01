import streamlit as st
import pandas as pd
import plotly.express as px
import fitdecode
import zipfile
import io
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Re-Connect: Garmin Health Explorer", layout="wide")

# --- CORE PARSER (The Timekeeper) ---
def parse_fit_file(file_bytes, source_name):
    data = []
    current_time = None
    
    try:
        # Fast Peek for File Type
        with fitdecode.FitReader(file_bytes) as fit:
            is_monitoring = False
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'file_id':
                        type_val = frame.get_value('type')
                        if type_val == 'monitoring_b' or type_val == 15:
                            is_monitoring = True
                        break
            if not is_monitoring:
                return []

        # Deep Parse
        with fitdecode.FitReader(file_bytes) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    if frame.name == 'monitoring':
                        record_time = None
                        
                        # Timestamp Logic
                        if frame.has_field('timestamp'):
                            raw_ts = frame.get_value('timestamp')
                            if raw_ts:
                                current_time = raw_ts
                                record_time = current_time
                        elif frame.has_field('timestamp_16') and current_time:
                            ts_16 = frame.get_value('timestamp_16')
                            curr_ts_int = int(current_time.timestamp())
                            delta = (ts_16 - curr_ts_int) & 0xFFFF
                            current_time = current_time + timedelta(seconds=delta)
                            record_time = current_time
                            
                        if record_time and frame.has_field('heart_rate'):
                            data.append({
                                'timestamp': record_time,
                                'heart_rate': frame.get_value('heart_rate'),
                                'source': source_name
                            })
    except Exception:
        return []
    return data

# --- MAIN PROCESSOR (Cached) ---
@st.cache_data(show_spinner=False)
def process_garmin_data(zip_source, limit=None, is_local=False):
    """
    1. Scans ALL zip parts to build a master file list.
    2. Sorts chronological.
    3. Applies 'Newest First' limit (takes the last N files).
    4. Processes data.
    """
    all_hr_data = []
    logs = []
    
    # Progress placeholders (we must create them here, but they won't update if cached)
    # Note: Streamlit widgets in cached functions are tricky. We use a simple approach.
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. Open Source
        if is_local:
            zf = zipfile.ZipFile(zip_source)
        else:
            zf = zipfile.ZipFile(zip_source)

        # 2. Discovery Phase (Scan Structure)
        status_text.text("🔍 Discovery Phase: Scanning all zip parts...")
        part_files = [f for f in zf.namelist() if "UploadedFiles" in f and f.endswith(".zip")]
        part_files.sort()
        
        # Build Master List of (PartName, FitFileName)
        master_file_list = []
        
        # We need to open every part briefly to get its file list. 
        # This is fast (just reading directory headers).
        for i, part in enumerate(part_files):
            inner_bytes = zf.read(part)
            inner_zf = zipfile.ZipFile(io.BytesIO(inner_bytes))
            fits = [f for f in inner_zf.namelist() if f.lower().endswith('.fit')]
            fits.sort()
            
            for f in fits:
                master_file_list.append( (part, f) )
        
        total_found = len(master_file_list)
        logs.append(f"Found {total_found} total FIT files across {len(part_files)} archives.")
        
        # 3. Apply Limit (Newest Data Priority)
        if limit is not None and limit < total_found:
            # Slice the END of the list (The most recent files)
            files_to_process = master_file_list[-limit:]
            logs.append(f"⚠️ Limit applied. Processing newest {limit} files only.")
        else:
            files_to_process = master_file_list
            logs.append("Processing ALL files.")

        # 4. Processing Phase
        status_text.text(f"🚀 Processing {len(files_to_process)} files...")
        
        # Optimization: Group by Part to avoid re-opening zips constantly
        # We reorganize our flat list back into a structure {PartName: [Files...]}
        grouped_tasks = {}
        for part, fname in files_to_process:
            if part not in grouped_tasks:
                grouped_tasks[part] = []
            grouped_tasks[part].append(fname)
            
        # Iterate
        processed_count = 0
        total_tasks = len(files_to_process)
        
        for part_name, fit_files in grouped_tasks.items():
            # Open Part Once
            inner_bytes = zf.read(part_name)
            inner_zf = zipfile.ZipFile(io.BytesIO(inner_bytes))
            
            for fit_name in fit_files:
                # Update Progress
                progress = processed_count / total_tasks
                progress_bar.progress(progress)
                
                # Parse
                with inner_zf.open(fit_name) as f:
                    file_data = parse_fit_file(f.read(), fit_name)
                    if file_data:
                        all_hr_data.extend(file_data)
                
                processed_count += 1

        progress_bar.empty()
        status_text.empty()
        
        if all_hr_data:
            df = pd.DataFrame(all_hr_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df['date'] = df['timestamp'].dt.date
            return df, logs
        else:
            return pd.DataFrame(), logs + ["No data extracted."]

    except Exception as e:
        return None, logs + [f"Error: {e}"]


# --- UI LAYOUT ---
st.title("❤️ Re-Connect: Garmin Health Explorer")

# Initialize Session State for persistence
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    # 1. Debug Toggle
    debug_mode = st.checkbox("🛠️ Debug Mode", value=False)
    
    st.divider()
    
    # 2. Input Logic
    if debug_mode:
        st.subheader("Debug Inputs")
        input_method = st.radio("Source", ["Upload", "Local Path"], index=1)
        
        zip_source = None
        is_local = False
        
        if input_method == "Upload":
            zip_source = st.file_uploader("Upload Zip", type="zip")
        else:
            # Default to your dev path
            default_path = "/Users/mphillips/Downloads/4bdb4ebf-8e55-497d-863f-6200bff583f6_1/DI_CONNECT/DI-Connect-Uploaded-Files"
            local_path = st.text_input("UploadedFiles Folder Path", default_path)
            
            if os.path.exists(local_path):
                # Find the Part1 zip
                zips = [f for f in os.listdir(local_path) if f.endswith(".zip") and "UploadedFiles" in f]
                zips.sort()
                if zips:
                    zip_source = os.path.join(local_path, zips[0])
                    is_local = True
                    st.success(f"Found {len(zips)} parts local.")
    else:
        # Family Mode (Upload Only)
        st.subheader("1. Upload Data")
        zip_source = st.file_uploader("Upload Garmin Export (Zip)", type="zip")
        is_local = False

    # Reset state if the source changes (e.g. user removes the file)
    if not zip_source:
        st.session_state['analysis_active'] = False

    # 3. Processing Limits
    limit = 4000 # Default = No Limit
    
    if zip_source:
        st.subheader("Processing Limits")
        slider_val = st.slider("Max Files (Newest First)", 100, 10000, 4000, step=100)
        
        if slider_val < 10000:
            limit = slider_val
        else:
            st.caption("Limit: None (All Files)")
            limit = None
    
    # 4. Action Button
    # We use a callback logic here: If clicked, update the session state
    if st.button("Analyze Heart Rate", type="primary", disabled=not zip_source):
        st.session_state['analysis_active'] = True


# --- MAIN DASHBOARD ---
# Now we check the SESSION STATE, not just the button click
if st.session_state['analysis_active'] and zip_source:
    
    # Run Processor (Cached)
    df, logs = process_garmin_data(zip_source, limit, is_local)
    
    if df is not None and not df.empty:
        
        # --- TOP METRICS ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Samples", f"{len(df):,}")
        c2.metric("Date Range", f"{df['date'].min()} to {df['date'].max()}")
        if limit:
            c3.metric("Limit Applied", f"Last {limit} files")
        else:
            c3.metric("Processing", "Full History")

        st.divider()
        
        # --- VISUALIZATION CONTROLS ---
        st.subheader("⚙️ Plot Settings")
        
        # Row 1: Percentile Controls
        col_p1, col_p2, col_win = st.columns(3)
        
        with col_p1:
            show_p1 = st.checkbox("Show Low Percentile Line", value=True)
            p1_val = st.number_input("Low Percentile (%)", min_value=1, max_value=49, value=10, step=1)
            
        with col_p2:
            show_p2 = st.checkbox("Show High Percentile Line", value=True)
            p2_val = st.number_input("High Percentile (%)", min_value=51, max_value=99, value=90, step=1)
            
        with col_win:
            window_days = st.slider("Rolling Average Window (Days)", 1, 60, 7)

        # Row 2: Time of Day Filter
        st.caption("Time of Day Filter (e.g., Isolate sleep hours or workout windows)")
        col_t1, col_t2 = st.columns(2)
        start_time = col_t1.time_input("Start Time", value=datetime.strptime("00:00", "%H:%M").time())
        end_time = col_t2.time_input("End Time", value=datetime.strptime("23:59", "%H:%M").time())

        # --- DATA FILTERING ---
        # Filter by Time of Day
        time_mask = (df['timestamp'].dt.time >= start_time) & (df['timestamp'].dt.time <= end_time)
        filtered_df = df[time_mask]
        
        if not filtered_df.empty:
            
            # --- AGGREGATION ---
            # 1. Standard Stats
            daily = filtered_df.groupby('date')['heart_rate'].agg(['mean', 'min', 'max', 'count'])
            
            # 2. Custom Percentiles & Tooltip Setup
            # We build a dictionary for hover_data to dynamically include the chosen percentiles
            hover_cols = {'min': True, 'max': True, 'count': False, 'coverage': ':.1f'} 

            if show_p1:
                p1_col = f'p{p1_val}'
                daily[p1_col] = filtered_df.groupby('date')['heart_rate'].quantile(p1_val/100).round(1)
                hover_cols[p1_col] = ':.1f' # Add to tooltip with 1 decimal formatting

            if show_p2:
                p2_col = f'p{p2_val}'
                daily[p2_col] = filtered_df.groupby('date')['heart_rate'].quantile(p2_val/100).round(1)
                hover_cols[p2_col] = ':.1f' # Add to tooltip with 1 decimal formatting

            daily = daily.reset_index()
            daily['mean'] = daily['mean'].round(1)
            
            # Coverage Calculation
            mins_in_window = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).seconds / 60
            if mins_in_window == 0: mins_in_window = 1440
            
            daily['coverage'] = (daily['count'] / mins_in_window * 100).clip(upper=100).round(1)
            
            # --- PLOTTING ---
            st.subheader("📈 Heart Rate Trends")
            
            fig = px.scatter(daily, x='date', y='mean',
                             color='coverage',
                             color_continuous_scale='Blues',
                             hover_data=hover_cols, # <--- Updated to use dynamic dictionary
                             labels={'mean': 'Daily Mean HR', 'coverage': '% Coverage'},
                             title=f"Heart Rate ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})")
            
            fig.update_traces(marker=dict(size=6, opacity=0.8))
            
            # 1. Main Mean Trendline
            fig.add_scatter(x=daily['date'], y=daily['mean'].rolling(window_days).mean(), 
                           mode='lines', name=f'Mean ({window_days}d Avg)', 
                           line=dict(color='black', width=3))
            
            # 2. Low Percentile Line
            if show_p1:
                col_name = f'p{p1_val}'
                fig.add_scatter(x=daily['date'], y=daily[col_name].rolling(window_days).mean(),
                                mode='lines', name=f'{p1_val}th % ({window_days}d Avg)',
                                line=dict(color='cyan', width=2, dash='solid'))

            # 3. High Percentile Line
            if show_p2:
                col_name = f'p{p2_val}'
                fig.add_scatter(x=daily['date'], y=daily[col_name].rolling(window_days).mean(),
                                mode='lines', name=f'{p2_val}th % ({window_days}d Avg)',
                                line=dict(color='orangered', width=2, dash='solid'))
            
            fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="date"))
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning(f"No data found in the time window {start_time} - {end_time}.")
        
        # --- DEBUG LOGS ---
        if debug_mode:
            with st.expander("🛠️ Debug Logs"):
                for log in logs:
                    st.write(log)
                st.write("Raw Data Sample:")
                st.dataframe(df.head())
                
    elif df is not None and df.empty:
        st.warning("Processed files but found no valid Heart Rate data.")
        if debug_mode:
             with st.expander("Logs"):
                for log in logs:
                    st.write(log)