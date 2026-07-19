import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# This MUST be the first Streamlit command in your script
st.set_page_config(layout="wide")


st.title("My First Streamlit App 🎈")
st.write("Hello, world! I am running this locally on my computer.")

# # Let's add a simple interactive widget
# user_name = st.text_input("What is your name?")
# if user_name:
#    st.write(f"Nice to meet you, {user_name}!")

# Single value slider
temperature = st.slider("Set Temperature (°C)", min_value=0.0, max_value=100.0, value=25.0, step=0.5)

# Range slider
voltage_range = st.slider("Voltage Range (V)", min_value=0, max_value=240, value=(110, 220))

pressure = st.number_input("Pressure (PSI)", min_value=0.00, max_value=50.00, value=14.70)

water_level = 75 # percentage
st.write("Tank Water Level")
st.progress(water_level)

st.metric(label="Wind Speed", value="15.2 mph", delta="-1.5 mph")

# Create an analog gauge using Plotly
fig = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = 270,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Engine RPM"},
    gauge = {'axis': {'range': [None, 500]},
             'bar': {'color': "darkblue"},
             'steps': [
                 {'range': [0, 250], 'color': "lightgray"},
                 {'range': [250, 400], 'color': "gray"}],
             'threshold': {
                 'line': {'color': "red", 'width': 4},
                 'thickness': 0.75,
                 'value': 490}}
))

# Display the gauge in Streamlit
st.plotly_chart(fig)


# Simulate a continuous analog signal (e.g., sine wave)
chart_data = pd.DataFrame(
    np.sin(np.arange(100) / 10.0),
    columns=['Signal Amplitude']
)

st.line_chart(chart_data)

# Let's create some dummy data for our charts
data = pd.DataFrame({
    "Asset Category": ["Pumps", "Valves", "Compressors", "Motors"],
    "Downtime Hours": [120, 85, 45, 200]
})

st.title("Equipment Dashboard")

# --- CREATE COLUMNS ---
# This creates two equal-width columns
col1, col2 = st.columns(2)

# --- BAR GRAPH (COLUMN 1) ---
with col1:
    st.subheader("Downtime by Asset")
    bar_fig = px.bar(
        data, 
        x="Asset Category", 
        y="Downtime Hours", 
        color="Asset Category",
        title="Total Downtime"
    )
    # use_container_width=True ensures the chart scales to fit the column size
    st.plotly_chart(bar_fig, use_container_width=True)

# --- PIE CHART (COLUMN 2) ---
with col2:
    st.subheader("Downtime Distribution")
    pie_fig = px.pie(
        data, 
        names="Asset Category", 
        values="Downtime Hours", 
        hole=0.3, 
        title="Downtime Share"
    )
    st.plotly_chart(pie_fig, use_container_width=True)

    asset_list = ["Pumps", "Valves", "Compressors", "Motors"]

# Creates a dropdown menu
selected_asset = st.selectbox("Choose an asset to inspect:", asset_list)

st.write(f"You selected: **{selected_asset}**")

asset_list = ["Pumps", "Valves", "Compressors", "Motors"]

# Creates radio buttons
selected_asset = st.radio("Choose an asset to inspect:", asset_list)

st.write(f"You selected: **{selected_asset}**")

asset_list = ["Pumps", "Valves", "Compressors", "Motors"]

# Creates a multi-select box
# Note: This returns a Python list of the selected strings!
selected_assets = st.multiselect("Choose assets to compare:", asset_list)

st.write(f"You selected: {selected_assets}")

# 1. The data
data = pd.DataFrame({
    "Asset Category": ["Pumps", "Pumps", "Valves", "Valves"],
    "Status": ["Running", "Maintenance", "Running", "Failed"]
})

# 2. The selection widget
asset_list = ["Pumps", "Valves"]
chosen_asset = st.selectbox("Select Asset Category:", asset_list)

# 3. Filter the data based on the selection
filtered_data = data[data["Asset Category"] == chosen_asset]

# 4. Display the result
st.write(f"Showing status for {chosen_asset}:")
st.dataframe(filtered_data)