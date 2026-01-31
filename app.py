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
        # Load zip into memory
        zf = zipfile.ZipFile(uploaded_zip)
        
        # Find wellness/monitoring files. 
        # Structure is typically: DI_CONNECT/DI-Connect-Wellness/
        # Filenames often look like: ..._Monitoring_... .fit
        monitoring_files = [f for f in zf.namelist() if "Monitoring" in f and f.endswith(".fit")]
        
        if not monitoring_files:
            st.warning("No 'Monitoring' files found. Please check if this is a complete Garmin export.")
        else:
            st.success(f"Found {len(monitoring_files)} daily monitoring files.")

            # --- User Controls: Sampling ---
            # Parsing ALL files might be slow. Let's offer a limiter for the prototype.
            limit_files = st.slider("Number of days to process (for speed)", 1, 100, 10)
            files_to_process = monitoring_files[:limit_files]

            # --- Processing ---
            all_hr_data = []
            progress_bar = st.progress(0)
            
            for i, filename in enumerate(files_to_process):
                with zf.open(filename) as f:
                    file_bytes = f.read()
                    daily_data = parse_monitoring_file(file_bytes)
                    all_hr_data.extend(daily_data)
                progress_bar.progress((i + 1) / len(files_to_process))
            
            # Convert to DataFrame
            if all_hr_data:
                df = pd.DataFrame(all_hr_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                # Convert to roughly local time? (Simplification: Just -7 for Mountain Time or keep UTC)
                # For a family app, you might add a timezone selector.
                
                df['date'] = df['timestamp'].dt.date
                st.write(f"Processed {len(df):,} heart rate samples.")

                # --- The "Smarts": Custom Aggregation ---
                st.divider()
                st.subheader("📊 Custom Daily Aggregation")
                
                col1, col2 = st.columns(2)
                with col1:
                    agg_method = st.selectbox(
                        "Choose aggregation method for daily dot:",
                        ["Mean", "Median", "Max", "Min", "95th Percentile", "5th Percentile"]
                    )
                with col2:
                    exclude_outliers = st.checkbox("Exclude outliers (Top/Bottom 5% of day's data)?")

                # Function to aggregate a single day's group
                def aggregate_day(group):
                    series = group['heart_rate'].dropna()
                    
                    if exclude_outliers:
                        lower = series.quantile(0.05)
                        upper = series.quantile(0.95)
                        series = series[(series >= lower) & (series <= upper)]
                    
                    if agg_method == "Mean":
                        return series.mean()
                    elif agg_method == "Median":
                        return series.median()
                    elif agg_method == "Max":
                        return series.max()
                    elif agg_method == "Min":
                        return series.min()
                    elif agg_method == "95th Percentile":
                        return series.quantile(0.95)
                    elif agg_method == "5th Percentile":
                        return series.quantile(0.05)
                    return 0

                # Group by date and apply aggregation
                daily_stats = df.groupby('date').apply(aggregate_day).reset_index(name='hr_stat')
                
                # --- Plotting with Plotly ---
                fig = px.scatter(
                    daily_stats, 
                    x='date', 
                    y='hr_stat',
                    title=f"Daily Heart Rate ({agg_method})",
                    labels={'hr_stat': 'Heart Rate (BPM)', 'date': 'Date'}
                )
                
                # Add a rolling average line for trends
                daily_stats['rolling_7d'] = daily_stats['hr_stat'].rolling(7).mean()
                fig.add_trace(go.Scatter(
                    x=daily_stats['date'], 
                    y=daily_stats['rolling_7d'], 
                    mode='lines', 
                    name='7-Day Avg',
                    line=dict(color='orange', width=3)
                ))

                # Enable Range Slider
                fig.update_layout(
                    xaxis=dict(
                        rangeslider=dict(visible=True),
                        type="date"
                    )
                )

                st.plotly_chart(fig, use_container_width=True)
                
                # Show raw data table option
                with st.expander("See processed daily data"):
                    st.dataframe(daily_stats)

            else:
                st.error("Could not extract heart rate data from the selected files.")