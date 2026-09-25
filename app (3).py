import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="GC Data Processing Tool",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 LabSolutions GC Data Analysis & Kinetics Tool")
st.markdown("Upload your raw Shimadzu LabSolutions Excel export file to process peak areas, apply response factors, and compute reaction parameters.")

# --- SIDEBAR: PARAMETERS & INPUTS ---
st.sidebar.header("1. Experimental Parameters")

# Catalyst Mass
cat_mass = st.sidebar.number_input("Catalyst Mass (g)", min_value=0.001, value=0.100, step=0.010, format="%.3f")

# Feed Gas Composition
st.sidebar.subheader("Feed Gas Composition (vol% / mol%)")
col_f1, col_f2 = st.sidebar.columns(2)
feed_h2 = col_f1.number_input("H₂ (%)", min_value=0.0, value=65.0, step=0.5)
feed_co2 = col_f2.number_input("CO₂ (%)", min_value=0.0, value=22.0, step=0.5)
feed_co = col_f1.number_input("CO (%)", min_value=0.0, value=3.0, step=0.5)
feed_n2 = col_f2.number_input("N₂ (%)", min_value=0.0, value=10.0, step=0.5)

# Calculate Stoichiometric Number (SN)
# SN = (H2 - CO2) / (CO + CO2)
if (feed_co + feed_co2) > 0:
    sn_val = (feed_h2 - feed_co2) / (feed_co + feed_co2)
else:
    sn_val = 0.0

st.sidebar.metric("Stoichiometric Number (SN)", f"{sn_val:.2f}")

# --- SIDEBAR: RESPONSE FACTORS ---
st.sidebar.subheader("2. Response Factors (RF)")
st.sidebar.caption("Corrected Area = Raw Area × RF")

# Default relative response factors
default_rf = {
    "H2": 1.000,
    "N2": 1.000,      # Reference Internal Standard
    "CH4": 1.120,
    "CO": 1.050,
    "CO2": 1.250,
    "H2O": 1.000,
    "CH3OH": 1.450,
    "DME": 1.820
}

rf_dict = {}
cols_rf = st.sidebar.columns(2)
for i, (k, v) in enumerate(default_rf.items()):
    c = cols_rf[i % 2]
    rf_dict[k] = c.number_input(f"RF {k}", min_value=0.001, value=float(v), step=0.01, format="%.3f")


# --- HELPER FUNCTION TO PARSE LABSOLUTIONS EXCEL SHEETS ---
def parse_labsolutions_sheet(df):
    """
    Parses dual TCD/FID multi-column layout from Shimadzu LabSolutions export.
    Combines TCD (H2, N2, CH4, CO) and FID/TCD2 (Composite, CO2, H2O, CH3OH, DME).
    """
    # Clean whitespace in column headers
    df.columns = [str(c).strip() for c in df.columns]
    
    # Identify compound columns present in the sheet
    compounds = ["H2", "N2", "CH4", "CO", "CO2", "H2O", "CH3OH", "DME"]
    found_cols = [c for c in compounds if c in df.columns]
    
    # Extract peak area columns and clean numeric data
    for col in found_cols:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(" ", "").str.replace("----", "0"), errors='coerce').fillna(0)
    
    # Extract metadata if present
    meta_cols = [c for c in ["Data Filename", "Sample Name", "Sample ID"] if c in df.columns]
    
    # Filter to non-empty records
    data = df[found_cols].copy()
    if meta_cols:
        data = pd.concat([df[meta_cols], data], axis=1)
        
    return data


# --- MAIN FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    # Read all sheet names
    excel_file = pd.ExcelFile(uploaded_file)
    sheet_names = excel_file.sheet_names
    
    st.success(f"File loaded successfully! Found {len(sheet_names)} sheet(s).")
    
    # Sheet Selection
    selected_sheet = st.selectbox("Select Sheet / Condition to Analyze:", sheet_names)
    
    # Read raw sheet
    raw_df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
    
    st.subheader(f"Raw Data Preview: `{selected_sheet}`")
    st.dataframe(raw_df.head(10), use_container_width=True)
    
    # Process sheet
    parsed_df = parse_labsolutions_sheet(raw_df)
    
    if not parsed_df.empty:
        # Step 1: Calculate Corrected Peak Areas
        corr_df = parsed_df.copy()
        for comp, rf in rf_dict.items():
            if comp in corr_df.columns:
                corr_df[f"{comp}_CorrArea"] = corr_df[comp] * rf
        
        # Step 2: Sum of Corrected Areas & Mole Fractions
        corr_cols = [f"{c}_CorrArea" for c in rf_dict.keys() if f"{c}_CorrArea" in corr_df.columns]
        corr_df["Total_CorrArea"] = corr_df[corr_cols].sum(axis=1)
        
        # Mole fractions (molar concentration %)
        for comp in rf_dict.keys():
            if f"{comp}_CorrArea" in corr_df.columns:
                corr_df[f"{comp}_mol%"] = np.where(
                    corr_df["Total_CorrArea"] > 0,
                    (corr_df[f"{comp}_CorrArea"] / corr_df["Total_CorrArea"]) * 100,
                    0
                )
        
        # Step 3: Performance Calculations (CO2 Conversion & Product Selectivity)
        # Using N2 internal standard normalization
        if "N2_mol%" in corr_df.columns and "CO2_mol%" in corr_df.columns:
            # CO2 conversion based on N2 balance
            n2_in = feed_n2
            co2_in = feed_co2
            
            # (CO2/N2)in vs (CO2/N2)out
            ratio_in = co2_in / n2_in if n2_in > 0 else 1.0
            ratio_out = np.where(corr_df["N2_mol%"] > 0, corr_df["CO2_mol%"] / corr_df["N2_mol%"], 0)
            
            corr_df["CO2_Conv_%"] = np.maximum(0, (1 - (ratio_out / ratio_in)) * 100)
            
            # Carbon-based selectivities
            carbon_products = ["CH3OH", "DME", "CO", "CH4"]
            total_carbon_prod = sum([corr_df[f"{p}_mol%"] * (2 if p == "DME" else 1) for p in carbon_products if f"{p}_mol%" in corr_df.columns])
            
            for p in carbon_products:
                if f"{p}_mol%" in corr_df.columns:
                    factor = 2 if p == "DME" else 1
                    corr_df[f"{p}_Selectivity_%"] = np.where(
                        total_carbon_prod > 0,
                        (corr_df[f"{p}_mol%"] * factor / total_carbon_prod) * 100,
                        0
                    )
        
        # --- TABS FOR ORGANIZED OUTPUT ---
        tab1, tab2, tab3 = st.tabs(["📊 Calculated Results", "📈 Time-on-Stream Plots", "📥 Export Processed Data"])
        
        with tab1:
            st.subheader("Processed Molar Concentrations & Conversions")
            
            # Filter output columns for clean presentation
            display_cols = [c for c in corr_df.columns if "mol%" in c or "Conv_%" in c or "Selectivity_%" in c]
            st.dataframe(corr_df[display_cols].round(2), use_container_width=True)
            
        with tab2:
            st.subheader("Performance Trends Across Injections / TOS")
            
            if "CO2_Conv_%" in corr_df.columns:
                corr_df["Injection"] = corr_df.index + 1
                
                # Conversion plot
                fig_conv = px.line(
                    corr_df, x="Injection", y="CO2_Conv_%", 
                    title=f"CO₂ Conversion vs Injection Sequence ({selected_sheet})",
                    markers=True, labels={"CO2_Conv_%": "CO₂ Conversion (%)"}
                )
                st.plotly_chart(fig_conv, use_container_width=True)
                
                # Selectivity plot
                sel_cols = [c for c in corr_df.columns if "Selectivity_%" in c]
                if sel_cols:
                    fig_sel = px.line(
                        corr_df, x="Injection", y=sel_cols,
                        title=f"Product Selectivity vs Injection Sequence ({selected_sheet})",
                        markers=True, labels={"value": "Selectivity (%)", "variable": "Product"}
                    )
                    st.plotly_chart(fig_sel, use_container_width=True)
            else:
                st.info("Insufficient compound columns found to plot conversion trends.")

        with tab3:
            st.subheader("Download Complete Processed Dataset")
            csv_data = corr_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Processed CSV",
                data=csv_data,
                file_name=f"Processed_{selected_sheet}.csv",
                mime="text/csv"
            )

else:
    st.info("👆 Please upload a Shimadzu LabSolutions `.xlsx` data file to begin processing.")