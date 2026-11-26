
import pandas as pd
import numpy as np


# =====================================
# 1. MISSING VALUE ANALYSIS
# =====================================

def analyze_missing_values(df):

    missing_count = df.isnull().sum()

    missing_percentage = (
        df.isnull().mean() * 100
    )

    result = pd.DataFrame({
        "Column": df.columns,
        "Missing Count": missing_count.values,
        "Missing Percentage": missing_percentage.values
    })

    return result.sort_values(
        by="Missing Percentage",
        ascending=False
    )


# =====================================
# 2. DUPLICATE ANALYSIS
# =====================================

def analyze_duplicates(df):

    duplicate_count = df.duplicated().sum()

    return int(duplicate_count)


# =====================================
# 3. DATA TYPE ANALYSIS
# =====================================

def analyze_data_types(df):

    result = pd.DataFrame({
        "Column": df.columns,
        "Data Type": df.dtypes.astype(str).values,
        "Unique Values": [
            df[col].nunique() for col in df.columns
        ]
    })

    return result


# =====================================
# 4. OUTLIER DETECTION USING IQR
# =====================================

def detect_outliers(df):

    results = []

    numeric_columns = df.select_dtypes(
        include=np.number
    ).columns

    for column in numeric_columns:

        values = df[column].dropna()

        if len(values) < 4:
            continue

        q1 = values.quantile(0.25)

        q3 = values.quantile(0.75)

        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr

        upper_bound = q3 + 1.5 * iqr

        outliers = values[
            (values < lower_bound) |
            (values > upper_bound)
        ]

        results.append({
            "Column": column,
            "Outlier Count": len(outliers),
            "Lower Bound": lower_bound,
            "Upper Bound": upper_bound
        })

    return pd.DataFrame(results)


# =====================================
# 5. DATA QUALITY SCORE
# =====================================

def calculate_quality_score(df):

    if df.empty or len(df.columns) == 0:
        return 0.0

    total_cells = df.shape[0] * df.shape[1]

    missing_cells = int(df.isnull().sum().sum())

    missing_rate = missing_cells / total_cells

    duplicate_rate = df.duplicated().mean()

    score = 100 * (
        1 - (0.7 * missing_rate)
          - (0.3 * duplicate_rate)
    )

    return round(max(0, min(100, score)), 2)


# =====================================
# 6. COMPLETE DATASET ANALYSIS
# =====================================

def analyze_dataset(df):

    report = {

        "rows": df.shape[0],

        "columns": df.shape[1],

        "missing_values": analyze_missing_values(df),

        "duplicates": analyze_duplicates(df),

        "data_types": analyze_data_types(df),

        "outliers": detect_outliers(df),

        "quality_score": calculate_quality_score(df)

    }

    return report
