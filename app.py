import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Catalysis Data Dashboard",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 Catalysis Data Analysis Dashboard")
st.write("Upload your experiment data file (Excel or CSV) to visualize results.")

# --- FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        # Load Data
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.subheader("Raw Data Preview")

        # --- DATA CLEANING FOR PYARROW / STREAMLIT ---
        # 1. Drop completely unnamed/empty index columns
        df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed')]

        # 2. Convert non-standard datetimes/objects to clean strings to avoid PyArrow ArrowTypeError
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str)

        # Display Dataframe (using updated layout syntax)
        st.dataframe(df, width="stretch")

        # --- DATA SUMMARY & VISUALIZATION ---
        st.subheader("Data Visualization")

        # Filter numeric columns for plotting
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if len(numeric_cols) >= 2:
            col1, col2 = st.columns(2)
            with col1:
                x_axis = st.selectbox("Select X-axis", numeric_cols, index=0)
            with col2:
                y_axis = st.selectbox("Select Y-axis", numeric_cols, index=min(1, len(numeric_cols)-1))

            # Matplotlib Plot
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(df[x_axis], df[y_axis], marker='o', linestyle='-', color='#1f77b4')
            ax.set_xlabel(x_axis)
            ax.set_ylabel(y_axis)
            ax.set_title(f"{y_axis} vs {x_axis}")
            ax.grid(True, linestyle='--', alpha=0.6)

            st.pyplot(fig, width="stretch")
        else:
            st.info("Uploaded dataset needs at least two numerical columns for plotting.")

    except Exception as e:
        st.error(f"Error processing file: {e}")

else:
    st.info("Awaiting file upload. Please upload a dataset to begin.")
