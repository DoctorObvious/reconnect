import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import fitdecode
import zipfile
import io

# --- Page Config ---
st.set_page_config(page_title="Garmin Deep Dive", layout="wide")

st.title("❤️ Garmin Heart Rate Explorer")
st.markdown("""
    **Instructions:**
    1. Request your data from Garmin (Account Settings -> Export Your Data).
    2. Upload the `.zip` file here.
    3. The app will extract your daily heart rate monitoring files and calculate custom stats.
""")

# --- Helper: Parse a single FIT file for HR data ---
def parse_monitoring_file(file_bytes):
    """
    Extracts heart rate timestamps and values from a binary FIT file.
    Returns a list of dictionaries: {'timestamp': ..., 'heart_rate': ...}
    """
    data = []
    with fitdecode.FitReader(file_bytes) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage):
                if frame.name == 'monitoring':
                    # Garmin Monitoring messages often contain heart_rate
                    # Sometimes it's in a different field depending on device generation
                    if frame.has_field('heart_rate'):
                        data.append({
                            'timestamp': frame.get_value('timestamp'),
                            'heart_rate': frame.get_value('heart_rate')
                        })
    return data

# --- Main App Logic ---
uploaded_zip = st.file_uploader("Upload Garmin Export (ZIP)", type="zip")

if uploaded_zip:
    with st.spinner("Reading ZIP file structure..."):
        try:
            # Load zip into memory
            zf = zipfile.ZipFile(uploaded_zip)
            all_files = zf.namelist()
        
            # --- DEBUG SECTION: Show user what is inside ---
            with st.expander("📂 Debug: View ZIP Contents"):
                st.write(f"Total files found: {len(all_files)}")
                st.write("First 10 files:", all_files[:10])
                
                # Filter for ANY .fit files to see if they exist at all
                fit_files = [f for f in all_files if f.lower().endswith('.fit')]
                st.write(f"Total .fit files found: {len(fit_files)}")
                if fit_files:
                    st.write("Sample .fit files:", fit_files[:5])

            # Find wellness/monitoring files. 
            # Structure is typically: DI_CONNECT/DI-Connect-Wellness/
            # Filenames often look like: ..._Monitoring_... .fit
            # --- SEARCH LOGIC: Case-Insensitive Search ---
            # We look for files that have 'monitoring' in the name AND end in '.fit'
            # regardless of which folder they are in.
            monitoring_files = [f for f in all_files if 'monitoring' in f.lower() and f.lower().endswith('.fit')]        
            
            if not monitoring_files:
                st.error("❌ No files matching 'Monitoring' and '.fit' were found.")
                st.info("Check the 'Debug' section above. If your files are named differently (e.g., 'Wellness'), you may need to adjust the search logic.")
            else:
                st.success(f"✅ Found {len(monitoring_files)} monitoring files!")

                # --- Processing Limit ---
                limit_files = st.slider("Number of days to process", 1, min(len(monitoring_files), 1000), 5)
                files_to_process = monitoring_files[:limit_files]

                all_hr_data = []
                progress_bar = st.progress(0)

                # --- Processing ---
                all_hr_data = []
                progress_bar = st.progress(0)
                
                for i, filename in enumerate(files_to_process):
                    # Update progress bar
                    progress_bar.progress((i + 1) / len(files_to_process))
                    
                    try:
                        with zf.open(filename) as f:
                            file_bytes = f.read()
                            daily_data = parse_monitoring_file(file_bytes)
                            all_hr_data.extend(daily_data)
                    except Exception as e:
                        st.warning(f"Skipped file {filename} due to error: {e}")
                
                # Convert to DataFrame
                if all_hr_data:
                    df = pd.DataFrame(all_hr_data)
                    
                    # Basic cleanup
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                        df['date'] = df['timestamp'].dt.date
                        
                        st.metric("Total HR Samples", f"{len(df):,}")
                        
                        # --- Visualization ---
                        st.subheader("Raw Data Preview")
                        st.dataframe(df.head())
                        
                        st.subheader("Simple Plot")
                        fig = px.scatter(df, x='timestamp', y='heart_rate', title="Raw Heart Rate Data")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("Data extracted but no timestamp found. Check FIT file format.")
                else:
                    st.warning("Processed files but found no heart rate data points. The files might be empty or formatted differently.")

        except zipfile.BadZipFile:
            st.error("The uploaded file is not a valid ZIP file.")