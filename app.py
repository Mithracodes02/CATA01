import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Catalysis Data Analysis", page_icon="🧪", layout="wide"
)

st.title("🧪 Catalysis Performance Dashboard")


def prepare_dataframe_for_arrow(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans up DataFrame column types to ensure PyArrow compatibility.

    - Converts datetime columns to ISO string format or standardized datetimes.
    - Handles unnamed index columns.
    """
    df = df.copy()

    # Drop or rename unnamed empty index columns if present
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    for col in df.columns:
        # Convert datetime objects to string to avoid PyArrow ArrowTypeError
        if (
            pd.api.types.is_datetime64_any_dtype(df[col])
            or df[col]
            .apply(lambda x: type(x).__name__ == "datetime")
            .any()
        ):
            df[col] = df[col].astype(str)
        elif df[col].dtype == "object":
            # Sanitize mixed object types
            df[col] = df[col].apply(
                lambda x: str(x) if pd.notnull(x) else ""
            )

    return df


# --- SAMPLE DATASET GENERATION ---
@st.cache_data
def load_data():
    data = {
        "Time_on_Stream_h": np.linspace(0, 24, 10),
        "Temperature_C": np.linspace(220, 260, 10),
        "CO2_Conversion_%": np.array(
            [12.1, 14.3, 16.5, 18.2, 19.0, 18.8, 18.5, 18.2, 18.0, 17.9]
        ),
        "MeOH_Selectivity_%": np.array(
            [65.0, 63.2, 61.5, 60.1, 58.4, 58.0, 57.8, 57.5, 57.2, 57.0]
        ),
        "Timestamp": pd.date_range(
            start="2026-09-25 14:00", periods=10, freq="h"
        ),
    }
    df = pd.DataFrame(data)
    return prepare_dataframe_for_arrow(df)


df = load_data()

# --- DISPLAY METRICS & DATA TABLE ---
st.subheader("Experimental Results")

# Fixed: Replacing deprecated `use_container_width=True` with `width="stretch"`
st.dataframe(df, width="stretch")

# --- PLOTTING ---
st.subheader("CO₂ Conversion & Selectivity Over Time")

fig = px.line(
    df,
    x="Time_on_Stream_h",
    y=["CO2_Conversion_%", "MeOH_Selectivity_%"],
    labels={
        "Time_on_Stream_h": "Time on Stream (h)",
        "value": "Percentage (%)",
    },
    title="Reaction Profile",
)

# Fixed: Replacing deprecated `use_container_width=True` with `width="stretch"`
st.plotly_chart(fig, width="stretch")
