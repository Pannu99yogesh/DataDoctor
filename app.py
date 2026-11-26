import io
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="DataDoctor | Data Quality Analyzer",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Natural, calm colour palette
SAGE = "#789477"
FOREST = "#344B3B"
IVORY = "#F7F6F0"
SAND = "#EEEDE5"
TERRACOTTA = "#C47C5A"
MUTED = "#77756D"

# ---------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {IVORY};
        color: #343832;
    }}
    [data-testid="stSidebar"] {{
        background-color: #EEEDE5;
        border-right: 1px solid #D8D5C9;
    }}
    h1, h2, h3 {{
        color: {FOREST};
    }}
    .brand-kicker {{
        color: {SAGE};
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 2px;
        margin-bottom: 4px;
    }}
    .hero-title {{
        color: {FOREST};
        font-size: 42px;
        font-weight: 750;
        line-height: 1.15;
        margin: 0;
    }}
    .hero-subtitle {{
        color: {MUTED};
        font-size: 16px;
        margin-top: 8px;
    }}
    .section-note {{
        color: {MUTED};
        font-size: 14px;
    }}
    div[data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 1px solid #E4E1D7;
        border-radius: 12px;
        padding: 15px 16px;
    }}
    div.stButton > button,
    div.stDownloadButton > button {{
        border-radius: 9px;
        border: 1px solid {SAGE};
        background: {SAGE};
        color: white;
        font-weight: 600;
    }}
    div.stButton > button:hover,
    div.stDownloadButton > button:hover {{
        background: {FOREST};
        border-color: {FOREST};
        color: white;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def read_dataset(uploaded_file):
    """Read CSV or Excel file into a pandas DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Please upload a CSV or Excel file.")


def get_outlier_counts(df):
    """Count IQR outliers in each numeric column."""
    counts = {}
    numeric_columns = df.select_dtypes(include=np.number).columns

    for column in numeric_columns:
        series = df[column].dropna()
        if series.empty:
            counts[column] = 0
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        counts[column] = int(((series < lower) | (series > upper)).sum())

    return counts


def calculate_quality_score(df):
    """
    DataDoctor's custom quality score.
    It considers missing cells (70%) and duplicate rows (30%).
    This is a project-defined metric, not an industry standard.
    """
    if df.empty or df.shape[1] == 0:
        return 0.0

    total_cells = max(df.shape[0] * df.shape[1], 1)
    missing_rate = float(df.isna().sum().sum()) / total_cells
    duplicate_rate = float(df.duplicated().sum()) / max(len(df), 1)

    score = 100 * (1 - (0.7 * missing_rate) - (0.3 * duplicate_rate))
    return round(max(0.0, min(100.0, score)), 2)


def clean_dataset(
    df,
    missing_method,
    duplicate_method,
    outlier_method,
):
    """Apply the selected cleaning operations and return a cleaned copy."""
    cleaned = df.copy()

    # Missing values
    if missing_method == "Drop rows with missing values":
        cleaned = cleaned.dropna()

    elif missing_method == "Fill numeric with median, text with mode":
        for column in cleaned.columns:
            if pd.api.types.is_numeric_dtype(cleaned[column]):
                median = cleaned[column].median()
                if pd.notna(median):
                    cleaned[column] = cleaned[column].fillna(median)
            else:
                modes = cleaned[column].mode(dropna=True)
                if not modes.empty:
                    cleaned[column] = cleaned[column].fillna(modes.iloc[0])

    elif missing_method == "Fill missing values with zero":
        cleaned = cleaned.fillna(0)

    # Duplicate rows
    if duplicate_method == "Remove duplicate rows":
        cleaned = cleaned.drop_duplicates()

    # Outliers in numeric columns
    numeric_columns = cleaned.select_dtypes(include=np.number).columns
    if outlier_method in (
        "Cap outliers using IQR",
        "Remove rows containing IQR outliers",
    ):
        row_mask = pd.Series(True, index=cleaned.index)

        for column in numeric_columns:
            series = cleaned[column].dropna()
            if series.empty:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            if outlier_method == "Cap outliers using IQR":
                cleaned[column] = cleaned[column].clip(
                    lower=lower, upper=upper
                )
            else:
                row_mask &= (
                    cleaned[column].isna()
                    | cleaned[column].between(lower, upper)
                )

        if outlier_method == "Remove rows containing IQR outliers":
            cleaned = cleaned.loc[row_mask]

    return cleaned.reset_index(drop=True)


def make_pdf_report(
    original_df,
    cleaned_df,
    original_score,
    cleaned_score,
    missing_method,
    duplicate_method,
    outlier_method,
):
    """Create a PDF summary report in memory."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("DataDoctor - Data Quality Report", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 18))

    summary_data = [
        ["Metric", "Before cleaning", "After cleaning"],
        ["Rows", str(len(original_df)), str(len(cleaned_df))],
        ["Columns", str(original_df.shape[1]), str(cleaned_df.shape[1])],
        [
            "Missing cells",
            str(int(original_df.isna().sum().sum())),
            str(int(cleaned_df.isna().sum().sum())),
        ],
        [
            "Duplicate rows",
            str(int(original_df.duplicated().sum())),
            str(int(cleaned_df.duplicated().sum())),
        ],
        [
            "Quality score",
            f"{original_score}/100",
            f"{cleaned_score}/100",
        ],
    ]

    table = Table(summary_data, colWidths=[175, 150, 150])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FOREST)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F6F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D5C9")),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Cleaning operations selected", styles["Heading2"]))

    for label, choice in [
        ("Missing values", missing_method),
        ("Duplicate rows", duplicate_method),
        ("Outliers", outlier_method),
    ]:
        story.append(Paragraph(f"<b>{label}:</b> {choice}", styles["Normal"]))
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Note: DataDoctor's quality score is a custom project metric "
            "based on missing-cell rate and duplicate-row rate. It is not "
            "an industry-standard certification.",
            styles["Italic"],
        )
    )

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def show_quality_chart(before_score, after_score):
    chart_df = pd.DataFrame(
        {
            "Cleaning Stage": ["Before Cleaning", "After Cleaning"],
            "Quality Score": [before_score, after_score],
        }
    )

    fig = px.bar(
        chart_df,
        x="Cleaning Stage",
        y="Quality Score",
        text="Quality Score",
        range_y=[0, 100],
        color_discrete_sequence=[SAGE],
    )
    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        marker_line_color=FOREST,
        marker_line_width=1,
    )
    fig.update_layout(
        height=360,
        plot_bgcolor=IVORY,
        paper_bgcolor=IVORY,
        font_color=FOREST,
        yaxis_title="Quality score (out of 100)",
        xaxis_title="",
        margin=dict(l=20, r=20, t=35, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌿 DataDoctor")
    st.caption("Your data health workspace")
    st.divider()

    st.subheader("Upload dataset")
    st.write("Upload your CSV or Excel file")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "xlsx", "xls"],
        help="Supported formats: CSV, XLSX and XLS",
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("A simple workspace to inspect, clean and improve your data.")

# ---------------------------------------------------------
# MAIN HEADER
# ---------------------------------------------------------
st.markdown(
    """
    <div class="brand-kicker">DATA QUALITY WORKSPACE</div>
    <h1 class="hero-title">DataDoctor</h1>
    <p class="hero-subtitle">
        Understand your data. Fix the problems. Build confidence.
    </p>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ---------------------------------------------------------
# EMPTY STATE
# ---------------------------------------------------------
if uploaded_file is None:
    st.info("Upload a CSV or Excel dataset from the sidebar to get started.")
    st.markdown("### What you can do with DataDoctor")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 🔎 Inspect")
        st.write("Preview your dataset and identify missing values, duplicates and outliers.")

    with c2:
        st.markdown("#### 🧹 Clean")
        st.write("Choose how to handle missing data, duplicate rows and numeric outliers.")

    with c3:
        st.markdown("#### 📊 Compare")
        st.write("Compare data quality before and after cleaning and export a report.")

    st.stop()

# ---------------------------------------------------------
# LOAD DATASET
# ---------------------------------------------------------
try:
    uploaded_file.seek(0)
    original_df = read_dataset(uploaded_file)
except Exception as error:
    st.error(f"Could not read this file: {error}")
    st.stop()

if original_df.empty:
    st.warning("This dataset is empty. Please upload a file containing data.")
    st.stop()

# Keep a clean original copy for consistent analysis
original_df = original_df.copy()
missing_total = int(original_df.isna().sum().sum())
duplicate_total = int(original_df.duplicated().sum())
outlier_counts = get_outlier_counts(original_df)
outlier_total = int(sum(outlier_counts.values()))
original_score = calculate_quality_score(original_df)

# ---------------------------------------------------------
# DATASET OVERVIEW
# ---------------------------------------------------------
st.divider()
st.subheader("Dataset overview")
st.caption(
    f"File: {uploaded_file.name}  •  "
    f"{original_df.shape[0]:,} rows  •  {original_df.shape[1]:,} columns"
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", f"{original_df.shape[0]:,}")
m2.metric("Columns", f"{original_df.shape[1]:,}")
m3.metric("Missing cells", f"{missing_total:,}")
m4.metric("Duplicate rows", f"{duplicate_total:,}")

with st.expander("Preview uploaded dataset", expanded=True):
    st.dataframe(original_df.head(100), use_container_width=True)

# ---------------------------------------------------------
# DATA QUALITY ANALYSIS
# ---------------------------------------------------------
st.divider()
st.subheader("Data quality analysis")

left, right = st.columns(2)

with left:
    st.markdown("#### Missing values by column")
    missing_by_column = original_df.isna().sum()
    missing_by_column = missing_by_column[missing_by_column > 0]

    if missing_by_column.empty:
        st.success("Great! No missing values were found.")
    else:
        missing_chart_df = missing_by_column.rename("Missing values").reset_index()
        missing_chart_df.columns = ["Column", "Missing values"]
        fig_missing = px.bar(
            missing_chart_df,
            x="Column",
            y="Missing values",
            color_discrete_sequence=[TERRACOTTA],
        )
        fig_missing.update_layout(
            height=330,
            plot_bgcolor=IVORY,
            paper_bgcolor=IVORY,
            font_color=FOREST,
            xaxis_title="",
        )
        st.plotly_chart(fig_missing, use_container_width=True)
        st.dataframe(missing_chart_df, use_container_width=True, hide_index=True)

with right:
    st.markdown("#### Outliers by numeric column")
    outlier_chart_df = pd.DataFrame(
        {
            "Column": list(outlier_counts.keys()),
            "Outliers": list(outlier_counts.values()),
        }
    )

    if outlier_chart_df.empty:
        st.info("No numeric columns available for IQR outlier analysis.")
    elif int(outlier_chart_df["Outliers"].sum()) == 0:
        st.success("No IQR outliers were detected in numeric columns.")
    else:
        fig_outliers = px.bar(
            outlier_chart_df,
            x="Column",
            y="Outliers",
            color_discrete_sequence=[SAGE],
        )
        fig_outliers.update_layout(
            height=330,
            plot_bgcolor=IVORY,
            paper_bgcolor=IVORY,
            font_color=FOREST,
            xaxis_title="",
        )
        st.plotly_chart(fig_outliers, use_container_width=True)
        st.dataframe(outlier_chart_df, use_container_width=True, hide_index=True)

with st.expander("Detailed missing-value report"):
    missing_report = pd.DataFrame(
        {
            "Column": original_df.columns,
            "Missing values": original_df.isna().sum().values,
            "Missing percentage": (
                original_df.isna().mean().values * 100
            ).round(2),
        }
    )
    st.dataframe(missing_report, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# CLEANING CONTROLS
# ---------------------------------------------------------
st.divider()
st.subheader("Clean your dataset")
st.write("Choose the cleaning operations you want to apply.")

clean_col1, clean_col2, clean_col3 = st.columns(3)

with clean_col1:
    st.markdown("#### Missing values")
    missing_method = st.selectbox(
        "How should missing values be handled?",
        [
            "Keep missing values",
            "Drop rows with missing values",
            "Fill numeric with median, text with mode",
            "Fill missing values with zero",
        ],
        key="missing_method",
    )

with clean_col2:
    st.markdown("#### Duplicate rows")
    duplicate_method = st.selectbox(
        "How should duplicates be handled?",
        [
            "Keep duplicates",
            "Remove duplicate rows",
        ],
        key="duplicate_method",
    )

with clean_col3:
    st.markdown("#### Outliers")
    outlier_method = st.selectbox(
        "How should outliers be handled?",
        [
            "Keep outliers",
            "Cap outliers using IQR",
            "Remove rows containing IQR outliers",
        ],
        key="outlier_method",
    )

if st.button("✨ Clean Dataset", type="primary", use_container_width=True):
    cleaned_df = clean_dataset(
        original_df,
        missing_method,
        duplicate_method,
        outlier_method,
    )
    st.session_state["cleaned_df"] = cleaned_df
    st.session_state["cleaning_settings"] = {
        "missing": missing_method,
        "duplicates": duplicate_method,
        "outliers": outlier_method,
    }
    st.success("Your dataset has been cleaned successfully!")

# ---------------------------------------------------------
# RESULTS: CLEANED DATASET
# ---------------------------------------------------------
if "cleaned_df" in st.session_state:
    cleaned_df = st.session_state["cleaned_df"]
    cleaned_score = calculate_quality_score(cleaned_df)
    improvement = round(cleaned_score - original_score, 2)
    settings = st.session_state.get("cleaning_settings", {})

    st.divider()
    st.subheader("Cleaned dataset")
    st.caption(
        f"{cleaned_df.shape[0]:,} rows  •  "
        f"{cleaned_df.shape[1]:,} columns"
    )
    st.dataframe(cleaned_df.head(100), use_container_width=True)

    # Downloads
    csv_data = cleaned_df.to_csv(index=False).encode("utf-8")
    download_col1, download_col2 = st.columns(2)

    with download_col1:
        st.download_button(
            "⬇️ Download cleaned CSV",
            data=csv_data,
            file_name="datadoctor_cleaned_data.csv",
            mime="text/csv",
            use_container_width=True,
        )

    pdf_data = make_pdf_report(
        original_df,
        cleaned_df,
        original_score,
        cleaned_score,
        settings.get("missing", "Not specified"),
        settings.get("duplicates", "Not specified"),
        settings.get("outliers", "Not specified"),
    )

    with download_col2:
        st.download_button(
            "📄 Download PDF quality report",
            data=pdf_data,
            file_name="datadoctor_quality_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # Before / after metrics
    st.divider()
    st.subheader("Before vs After Cleaning")

    score_col1, score_col2, score_col3 = st.columns(3)
    score_col1.metric(
        "Original Quality Score",
        f"{original_score:.2f}/100",
    )
    score_col2.metric(
        "Cleaned Quality Score",
        f"{cleaned_score:.2f}/100",
    )
    score_col3.metric(
        "Score Improvement",
        f"{improvement:+.2f} points",
        delta=f"{improvement:+.2f} points",
    )

    st.markdown("#### Data Quality Improvement")
    show_quality_chart(original_score, cleaned_score)

    comparison = pd.DataFrame(
        {
            "Metric": [
                "Rows",
                "Columns",
                "Missing cells",
                "Duplicate rows",
                "Quality score",
            ],
            "Before cleaning": [
                len(original_df),
                original_df.shape[1],
                int(original_df.isna().sum().sum()),
                int(original_df.duplicated().sum()),
                original_score,
            ],
            "After cleaning": [
                len(cleaned_df),
                cleaned_df.shape[1],
                int(cleaned_df.isna().sum().sum()),
                int(cleaned_df.duplicated().sum()),
                cleaned_score,
            ],
        }
    )
    st.markdown("#### Cleaning summary")
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    if cleaned_score > original_score:
        st.success("The custom data quality score improved after cleaning.")
    elif cleaned_score == original_score:
        st.info("The custom data quality score stayed the same.")
    else:
        st.warning(
            "The custom data quality score decreased. Review the selected "
            "cleaning operations and the resulting dataset."
        )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.divider()
st.caption("DataDoctor • Built with Python, Pandas, Plotly and Streamlit")


