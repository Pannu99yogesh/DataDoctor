
import pandas as pd


def handle_missing_values(df, strategy="Keep"):
    """
    Handle missing values in a dataset.
    """
    cleaned_df = df.copy()

    if strategy == "Drop rows with missing values":
        cleaned_df = cleaned_df.dropna()

    elif strategy == "Fill with median/mode":
        for column in cleaned_df.columns:

            if cleaned_df[column].isnull().any():

                if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                    median_value = cleaned_df[column].median()

                    if pd.notna(median_value):
                        cleaned_df[column] = cleaned_df[column].fillna(
                            median_value
                        )

                else:
                    mode_values = cleaned_df[column].mode()

                    if not mode_values.empty:
                        cleaned_df[column] = cleaned_df[column].fillna(
                            mode_values[0]
                        )

    elif strategy == "Fill with zero":
        cleaned_df = cleaned_df.fillna(0)

    return cleaned_df


def remove_duplicates(df):
    """
    Remove duplicate rows from the dataset.
    """
    cleaned_df = df.copy()

    cleaned_df = cleaned_df.drop_duplicates()

    return cleaned_df


def handle_outliers(df, strategy="Keep"):
    """
    Handle numeric outliers using the IQR method.
    """
    cleaned_df = df.copy()

    if strategy == "Keep":
        return cleaned_df

    numeric_columns = cleaned_df.select_dtypes(
        include="number"
    ).columns

    if strategy == "Cap outliers using IQR":

        for column in numeric_columns:

            values = cleaned_df[column].dropna()

            if len(values) < 4:
                continue

            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)

            iqr = q3 - q1

            lower_bound = q1 - (1.5 * iqr)
            upper_bound = q3 + (1.5 * iqr)

            cleaned_df[column] = cleaned_df[column].clip(
                lower=lower_bound,
                upper=upper_bound
            )

    elif strategy == "Remove rows containing outliers":

        outlier_rows = pd.Series(
            False,
            index=cleaned_df.index
        )

        for column in numeric_columns:

            values = cleaned_df[column].dropna()

            if len(values) < 4:
                continue

            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)

            iqr = q3 - q1

            lower_bound = q1 - (1.5 * iqr)
            upper_bound = q3 + (1.5 * iqr)

            column_outliers = (
                (cleaned_df[column] < lower_bound) |
                (cleaned_df[column] > upper_bound)
            )

            outlier_rows = outlier_rows | column_outliers

        cleaned_df = cleaned_df.loc[~outlier_rows].copy()

    return cleaned_df


def clean_dataset(
    df,
    missing_strategy="Keep",
    remove_duplicate_rows=False,
    outlier_strategy="Keep"
):
    """
    Apply all selected cleaning operations.
    """

    cleaned_df = df.copy()

    # 1. Handle missing values
    cleaned_df = handle_missing_values(
        cleaned_df,
        missing_strategy
    )

    # 2. Remove duplicates if selected
    if remove_duplicate_rows:
        cleaned_df = remove_duplicates(cleaned_df)

    # 3. Handle outliers
    cleaned_df = handle_outliers(
        cleaned_df,
        outlier_strategy
    )

    return cleaned_df
