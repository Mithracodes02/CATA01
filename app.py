def parse_labsolutions_excel(file):
    # Read raw dataframe without interpreting row 0 as header
    df_raw = pd.read_excel(file, header=None)
    
    # Replace missing value placeholders ('-----') with NaN
    df_raw = df_raw.replace('-----', np.nan)

    # Locate row containing peak area headers (Data Filename / H2 / CO2)
    header_row_idx = None
    for idx, row in df_raw.iterrows():
        row_str = row.astype(str).tolist()
        if any('H2' in cell for cell in row_str) and any('CO2' in cell for cell in row_str):
            header_row_idx = idx
            break

    # Fallback to row 0 if keyword match is not found
    if header_row_idx is None:
        header_row_idx = 0

    # Separate headers from data rows
    data_df = df_raw.iloc[header_row_idx + 1:].reset_index(drop=True)

    # Slice Left Block (Data Filename, Sample Name, Sample ID, H2, N2, CH4, CO)
    left_block = data_df.iloc[:, :7].copy()
    left_block.columns = ['Data Filename', 'Sample Name', 'Sample ID', 'H2', 'N2', 'CH4', 'CO']

    # Slice Right Block (Data Filename, Sample Name, Sample ID, Composite, CO2, H2O, CH3OH, DME)
    right_block = data_df.iloc[:, 9:17].copy()
    right_block.columns = ['Data Filename', 'Sample Name', 'Sample ID', 'Composite', 'CO2', 'H2O', 'CH3OH', 'DME']

    # Drop completely empty rows where Data Filename is NaN or missing
    left_block = left_block.dropna(subset=['Data Filename'])
    right_block = right_block.dropna(subset=['Data Filename'])

    # Combine into single dataframe
    gas_cols = ['H2', 'N2', 'CH4', 'CO']
    right_cols = ['Composite', 'CO2', 'H2O', 'CH3OH', 'DME']
    
    clean_df = pd.concat([
        left_block[['Data Filename', 'Sample Name', 'Sample ID'] + gas_cols].reset_index(drop=True),
        right_block[right_cols].reset_index(drop=True)
    ], axis=1)

    # Convert peak area columns to float
    numeric_cols = gas_cols + right_cols
    for col in numeric_cols:
        clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')

    # Convert metadata to strings
    meta_cols = ['Data Filename', 'Sample Name', 'Sample ID']
    for col in meta_cols:
        clean_df[col] = clean_df[col].astype(str)

    # Insert Run # index column
    clean_df.insert(0, 'Run #', np.arange(1, len(clean_df) + 1))

    return clean_df, numeric_cols
