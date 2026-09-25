import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="LabSolutions GC Peak Area Dashboard",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 LabSolutions Gas Analysis Dashboard")
st.write("Upload raw Excel export files directly from LabSolutions to clean, visualize, and export peak area datasets.")


# --- 2. DATA CLEANING & PARSING FUNCTION ---
def parse_labsolutions_excel(file):
    # Read raw dataframe without headers to inspect raw structure
    df_raw = pd.read_excel(file)
    
    # Replace missing value placeholders ('-----') with NaN
    df_raw = df_raw.replace('-----', np.nan)

    # Extract Left Block (Columns A to G: H2, N2, CH4, CO)
    left_block = df_raw.iloc[:, :7].copy()
    left_block.columns = ['Data Filename', 'Sample Name', 'Sample ID', 'H2', 'N2', 'CH4', 'CO']

    # Extract Right Block (Columns J to Q: Composite, CO2, H2O, CH3OH, DME)
    right_block = df_raw.iloc[:, 9:17].copy()
    right_block.columns = ['Data Filename', 'Sample Name', 'Sample ID', 'Composite', 'CO2', 'H2O', 'CH3OH', 'DME']

    # Combine gas components into a single clean DataFrame
    gas_cols = ['H2', 'N2', 'CH4', 'CO']
    right_cols = ['Composite', 'CO2', 'H2O', 'CH3OH', 'DME']
    
    clean_df = pd.concat([
        left_block[['Data Filename', 'Sample Name', 'Sample ID'] + gas_cols], 
        right_block[right_cols]
    ], axis=1)

    # Coerce numeric columns to explicit floats
    numeric_cols = gas_cols + right_cols
    for col in numeric_cols:
        clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')

    # Convert metadata to strings to prevent PyArrow serialization errors
    meta_cols = ['Data Filename', 'Sample Name', 'Sample ID']
    for col in meta_cols:
        clean_df[col] = clean_df[col].astype(str)

    # Add run index for plotting time-on-stream trends
    clean_df.insert(0, 'Run #', np.arange(1, len(clean_df) + 1))

    return clean_df, numeric_cols


# --- 3. MAIN APP LOGIC ---
uploaded_file = st.file_uploader("Upload LabSolutions File (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df, numeric_cols = parse_labsolutions_excel(uploaded_file)

        # Tabbed Layout
        tab1, tab2, tab3 = st.tabs(["📊 Peak Area Data", "📈 Trend Plotting", "📥 Export Clean Data"])

        # TAB 1: DATA DISPLAY
        with tab1:
            st.subheader("Cleaned Dataset")
            st.dataframe(df, width="stretch")

            # Basic Statistics Summary
            with st.expander("Show Descriptive Statistics"):
                st.dataframe(df[numeric_cols].describe().T, width="stretch")

        # TAB 2: VISUALIZATIONS
        with tab2:
            st.subheader("Peak Area Trends")
            
            selected_components = st.multiselect(
                "Select Components to Plot", 
                options=numeric_cols, 
                default=['H2', 'CO', 'CO2', 'CH3OH']
            )

            if selected_components:
                fig, ax = plt.subplots(figsize=(10, 4.5))
                
                for comp in selected_components:
                    ax.plot(df['Run #'], df[comp], marker='o', label=comp)

                ax.set_xlabel("Injection Run #")
                ax.set_ylabel("Peak Area")
                ax.set_title("Peak Area Variation across Injections")
                ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
                ax.grid(True, linestyle='--', alpha=0.5)
                
                plt.tight_layout()
                st.pyplot(fig, width="stretch")
            else:
                st.info("Select at least one component above to display the trend plot.")

        # TAB 3: DOWNLOAD CLEANED FILE
        with tab3:
            st.subheader("Download Formatted Dataset")
            st.write("Download the parsed dataset as a cleaned CSV for downstream calculations or graphing in Origin.")

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Cleaned CSV",
                data=csv,
                file_name="cleaned_labsolutions_data.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error parsing file structure: {e}")

else:
    st.info("Please upload a raw Excel export from LabSolutions to view results.")
