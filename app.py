import streamlit as st
import psycopg2
import pandas as pd
import os
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# 1. Load Environment Variables (Crucial for Cloud DB)
load_dotenv()

# 2. UI Configuration
st.set_page_config(page_title="Agentic OS", page_icon="🛡️", layout="wide")

st_autorefresh(interval=5000, limit=None, key="dashboard_refresh")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    img {
        border: 2px solid #333;
        border-radius: 5px;
        filter: contrast(1.1) grayscale(0.2); 
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Agentic Command Center")
st.markdown("Powered by LangGraph, MCP, and Groq open-weight models.")

# 3. Cloud Database Connection Helper
def fetch_logs():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error("⚠️ DATABASE_URL is missing from your .env file!")
        return pd.DataFrame()
    
    try:
        # Connect to Supabase PostgreSQL instead of local SQLite
        conn = psycopg2.connect(db_url)
        query = "SELECT * FROM security_events ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Failed to connect to Cloud DB: {e}")
        return pd.DataFrame()

# 4. Data Fetching
logs_df = fetch_logs()

def delete_log(event_id):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            # Delete the specific row using its unique ID
            cursor.execute("DELETE FROM security_events WHERE id = %s", (event_id,))
        conn.commit()
        conn.close()
        st.toast(f"🗑️ Event #{event_id} deleted successfully!")
        st.rerun()  # Instantly refresh the UI to remove the item
    except Exception as e:
        st.error(f"Failed to delete event: {e}")

# 5. Top-Level Metrics Dashboard
col1, col2, col3 = st.columns(3)
with col1:
    total_events = len(logs_df)
    st.metric("Total Logged Events", total_events)
with col2:
    high_sev = len(logs_df[logs_df['severity_score'] >= 4]) if total_events > 0 else 0
    st.metric("High Severity Threats", high_sev, delta_color="inverse")
with col3:
    last_event = logs_df.iloc[0]['timestamp'] if total_events > 0 else "No events yet"
    st.metric("Last Detection Time", last_event)

st.divider()

# 6. Interactive Event Log Gallery
st.subheader("Recent Security Incidents")

if logs_df.empty:
    st.info("No security events logged yet. Waiting for Planner Agent to trigger the Database MCP Tool...")
else:
    for index, row in logs_df.head(5).iterrows():
        with st.expander(f"⚠️ Event [{row['severity_score']}/5] at {row['timestamp']}", expanded=(index==0)):
            img_col, text_col = st.columns([1, 2])
            
            with img_col:
                try:
                    # Note: This still relies on the local temp_frames folder for the image file
                    img = Image.open(row['image_path'])
                    st.image(img, caption=f"Source: {row['image_path']}", use_container_width=True)
                except FileNotFoundError:
                    st.error("Image file purged or missing.")
            
            with text_col:
                st.markdown("### Agent Rationale")
                st.write(row['agent_rationale'])
                
                st.markdown("### Vision Model Raw Output")
                st.caption(row['vlm_description'])
                
                st.markdown("### Actions Taken via MCP")
                st.success(row['action_taken'])

