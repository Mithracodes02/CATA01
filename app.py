import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

def analyze_fastgc_excel(
    file_path,
    blank_sheet_name="Blank",
    response_factors=None,
    inlet_flows=None,
    cat_mass_g=0.1,
    output_report_path="Catalyst_Activity_Report.xlsx"
):
    """
    Analyzes multi-sheet Excel files containing GC peak area data from Fast GC experiments.
    
    Parameters:
    -----------
    file_path : str
        Path to the Excel file containing experiment sheets.
    blank_sheet_name : str
        Name of the sheet containing blank baseline / response factor data.
    response_factors : dict
        Response factors relative to reference (e.g., N2 = 1.0).
        Example: {'H2': 1.0, 'N2': 1.0, 'CO': 0.85, 'CO2': 0.92, 'CH4': 0.78, 'CH3OH': 0.65, 'DME': 0.55}
    inlet_flows : dict
        Inlet molar/volumetric flows (Nml/min) for each gas component.
        Example: {'H2': 23.25, 'CO2': 4.65, 'CO': 4.65, 'N2': 2.45}
    cat_mass_g : float
        Catalyst mass loaded in grams (default 0.1 g).
    output_report_path : str
        Filename for the generated downloadable Excel activity report.
    """
    
    # 1. Default Configurations if not provided
    if response_factors is None:
        response_factors = {
            'H2': 1.00, 'N2': 1.00, 'CO': 0.85,
            'CO2': 0.92, 'CH4': 0.78, 'CH3OH': 0.65, 'DME': 0.55
        }
        
    if inlet_flows is None:
        inlet_flows = {
            'H2': 23.25, 'CO2': 4.65, 'CO': 4.65, 'N2': 2.45
        }

    xls = pd.ExcelFile(file_path)
    all_sheets = xls.sheet_names
    
    # Exclude non-test sheets
    ignore_sheets = [blank_sheet_name, 'Graphs', 'Feuil1', 'Feuil3', 'Summary']
    test_sheets = [s for s in all_sheets if s not in ignore_sheets]

    summary_records = []
    processed_dfs = {}

    print(f"Found {len(test_sheets)} test sheet(s) to process: {test_sheets}\n")

    # 2. Process each test sheet
    for sheet in test_sheets:
        df_raw = pd.read_excel(file_path, sheet_name=sheet)
        
        # Identify peak area columns
        # (Assumes columns in sheet contain Peak Areas for H2, N2, CO, CO2, CH4, CH3OH, DME)
        results = pd.DataFrame()
        
        # Copy original raw peak areas present in the sheet
        for comp in response_factors.keys():
            matching_cols = [c for c in df_raw.columns if comp.lower() in str(c).lower() and 'area' in str(c).lower()]
            if matching_cols:
                results[f'Area_{comp}'] = pd.to_numeric(df_raw[matching_cols[0]], errors='coerce')
            elif comp in df_raw.columns:
                results[f'Area_{comp}'] = pd.to_numeric(df_raw[comp], errors='coerce')

        if results.empty:
            print(f"Skipping sheet '{sheet}': No matching peak area columns found.")
            continue

        # Calculate Corrected Areas (Area / Response Factor)
        for comp, rf in response_factors.items():
            if f'Area_{comp}' in results.columns:
                results[f'CorrArea_{comp}'] = results[f'Area_{comp}'] / rf

        # Calculate Outlet Flows using N2 as Internal Standard
        # F_i_out = (CorrArea_i / CorrArea_N2) * F_N2_in
        if 'CorrArea_N2' in results.columns and 'N2' in inlet_flows:
            corr_n2 = results['CorrArea_N2']
            f_n2_in = inlet_flows['N2']
            
            for comp in response_factors.keys():
                if comp != 'N2' and f'CorrArea_{comp}' in results.columns:
                    results[f'F_{comp}_out'] = (results[f'CorrArea_{comp}'] / corr_n2) * f_n2_in

        # Reaction Metrics Calculation
        f_co_in = inlet_flows.get('CO', 0)
        f_co2_in = inlet_flows.get('CO2', 0)
        f_h2_in = inlet_flows.get('H2', 0)
        f_cox_in = f_co_in + f_co2_in

        f_co_out = results.get('F_CO_out', 0)
        f_co2_out = results.get('F_CO2_out', 0)
        f_h2_out = results.get('F_H2_out', 0)
        f_meoh_out = results.get('F_CH3OH_out', 0)
        f_dme_out = results.get('F_DME_out', 0)
        f_ch4_out = results.get('F_CH4_out', 0)

        # Conversions (%)
        if f_cox_in > 0:
            results['X_COx (%)'] = 100 * (f_cox_in - (f_co_out + f_co2_out)) / f_cox_in
        if f_co_in > 0:
            results['X_CO_app (%)'] = 100 * (f_co_in - f_co_out) / f_co_in
        if f_co2_in > 0:
            results['X_CO2_app (%)'] = 100 * (f_co2_in - f_co2_out) / f_co2_in
        if f_h2_in > 0:
            results['X_H2 (%)'] = 100 * (f_h2_in - f_h2_out) / f_h2_in

        # Yields & Selectivities (%)
        if f_cox_in > 0:
            results['Y_MeOH (%)'] = 100 * f_meoh_out / f_cox_in
            results['Y_DME (%)'] = 100 * (2 * f_dme_out) / f_cox_in
            results['Y_CH4 (%)'] = 100 * f_ch4_out / f_cox_in

            # Selectivities relative to reacted COx
            converted_cox = f_cox_in - (f_co_out + f_co2_out)
            results['S_MeOH (%)'] = np.where(converted_cox > 0, 100 * f_meoh_out / converted_cox, 0)
            results['S_DME (%)'] = np.where(converted_cox > 0, 100 * (2 * f_dme_out) / converted_cox, 0)
            results['S_CH4 (%)'] = np.where(converted_cox > 0, 100 * f_ch4_out / converted_cox, 0)

        # Methanol Productivity (g_MeOH * kg_cat^-1 * h^-1)
        # F_CH3OH_out (Nml/min) -> mmol/min using molar volume (~22.414 Nml/mmol) or directly via molar mass
        mw_meoh = 32.042  # g/mol
        results['MeOH_Productivity'] = (60 * 1000 * f_meoh_out * mw_meoh) / (22414 * cat_mass_g)

        # Elemental Balances (%)
        if f_cox_in > 0:
            results['Delta_C (%)'] = 100 * (f_cox_in - (f_ch4_out + f_co_out + f_co2_out + f_meoh_out + 2 * f_dme_out)) / f_cox_in

        processed_dfs[sheet] = results

        # Compute Steady-State Averages for Summary Report
        avg_row = {
            'Test_Condition_Sheet': sheet,
            'X_COx (%)': results['X_COx (%)'].mean() if 'X_COx (%)' in results else np.nan,
            'X_H2 (%)': results['X_H2 (%)'].mean() if 'X_H2 (%)' in results else np.nan,
            'Y_MeOH (%)': results['Y_MeOH (%)'].mean() if 'Y_MeOH (%)' in results else np.nan,
            'Y_DME (%)': results['Y_DME (%)'].mean() if 'Y_DME (%)' in results else np.nan,
            'S_MeOH (%)': results['S_MeOH (%)'].mean() if 'S_MeOH (%)' in results else np.nan,
            'MeOH_Productivity (g/kg_cat/h)': results['MeOH_Productivity'].mean() if 'MeOH_Productivity' in results else np.nan,
            'Delta_C_Balance (%)': results['Delta_C (%)'].mean() if 'Delta_C (%)' in results else np.nan
        }
        summary_records.append(avg_row)

    df_summary = pd.DataFrame(summary_records)

    # 3. Generate Analysis Plot Across Conditions / Temperature
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Conversion & Selectivity
    if 'X_COx (%)' in df_summary.columns:
        axes[0].bar(df_summary['Test_Condition_Sheet'], df_summary['X_COx (%)'], color='skyblue', label='X_COx (%)')
        axes[0].set_ylabel('Conversion (%)')
        axes[0].set_title('COx Conversion across Conditions')
        axes[0].tick_params(axis='x', rotation=30)
        axes[0].grid(True, linestyle='--', alpha=0.5)

    # Plot 2: Methanol Productivity
    if 'MeOH_Productivity (g/kg_cat/h)' in df_summary.columns:
        axes[1].plot(df_summary['Test_Condition_Sheet'], df_summary['MeOH_Productivity (g/kg_cat/h)'], marker='o', color='green', linewidth=2, label='MeOH Productivity')
        axes[1].set_ylabel('Productivity (g_MeOH kg_cat⁻¹ h⁻¹)')
        axes[1].set_title('Methanol Productivity across Conditions')
        axes[1].tick_params(axis='x', rotation=30)
        axes[1].grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('catalyst_activity_summary.png', dpi=300)
    plt.close()
    print("Summary plot saved as 'catalyst_activity_summary.png'.")

    # 4. Export Downloadable Excel Activity Report
    with pd.ExcelWriter(output_report_path, engine='openpyxl') as writer:
        # Write Overview / Summary Sheet
        df_summary.to_excel(writer, sheet_name='Activity Summary', index=False)
        
        # Write Calibration & Input Parameters
        df_inputs = pd.DataFrame([
            {'Parameter': 'Catalyst Mass (g)', 'Value': cat_mass_g},
            {'Parameter': 'Inlet H2 (Nml/min)', 'Value': inlet_flows.get('H2', 0)},
            {'Parameter': 'Inlet CO2 (Nml/min)', 'Value': inlet_flows.get('CO2', 0)},
            {'Parameter': 'Inlet CO (Nml/min)', 'Value': inlet_flows.get('CO', 0)},
            {'Parameter': 'Inlet N2 (Nml/min)', 'Value': inlet_flows.get('N2', 0)},
        ] + [{'Parameter': f'RF_{k}', 'Value': v} for k, v in response_factors.items()])
        df_inputs.to_excel(writer, sheet_name='Parameters & RFs', index=False)

        # Write detailed computed calculations for each test sheet
        for sheet, df_res in processed_dfs.items():
            clean_sheet_name = sheet[:31]  # Excel max sheet name limit
            df_res.to_excel(writer, sheet_name=clean_sheet_name, index=False)

    print(f"\nDownloadable Catalyst Activity Report created successfully at: '{output_report_path}'")
    return df_summary, processed_dfs


# ==========================================
# EXECUTION EXAMPLE
# ==========================================
if __name__ == '__main__':
    # Customizable Response Factors (RFs)
    user_response_factors = {
        'H2': 1.00,
        'N2': 1.00,
        'CO': 0.85,
        'CO2': 0.92,
        'CH4': 0.78,
        'CH3OH': 0.65,
        'DME': 0.55
    }

    # Customizable Gas Molar Inlet Composition / Flow Rates (Nml/min)
    user_inlet_flows = {
        'H2': 23.25,
        'CO2': 4.65,
        'CO': 4.65,
        'N2': 2.45
    }

    # Execute analysis on your workbook
    # analyze_fastgc_excel(
    #     file_path='your_catalyst_data.xlsx',
    #     blank_sheet_name='Blank',
    #     response_factors=user_response_factors,
    #     inlet_flows=user_inlet_flows,
    #     cat_mass_g=0.10,
    #     output_report_path='Catalyst_Activity_Report.xlsx'
    # )
