"""
DataFrame utilities for data processing.
"""

import pandas as pd
from typing import Any, Dict, List, Optional
import math


def make_json_compliant(data: Any) -> Any:
    """
    Recursively process data to ensure JSON compliance by replacing NaN and Inf values.
    
    Args:
        data: The data to be processed (can be dict, list, or primitive types)
    Returns:
        JSON-compliant data with NaN and Inf replaced by None
    """
    if isinstance(data, dict):
        return {k: make_json_compliant(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_compliant(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")
    elif isinstance(data, pd.Series):
        return data.tolist()
    else:
        return data


def df_to_json_safe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame to a JSON-safe list of dictionaries.
    
    Args:
        df: DataFrame to convert
        
    Returns:
        List of dictionaries with JSON-safe values
    """
    records = df.to_dict(orient="records")
    return make_json_compliant(records)


def truncate_dataframe(df: pd.DataFrame, max_rows: int = 1000) -> pd.DataFrame:
    """
    Truncate a DataFrame to a maximum number of rows.
    
    Args:
        df: DataFrame to truncate
        max_rows: Maximum number of rows
        
    Returns:
        Truncated DataFrame
    """
    if len(df) > max_rows:
        return df.head(max_rows)
    return df


def get_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get a summary of a DataFrame including shape, columns, and sample data.
    
    Args:
        df: DataFrame to summarize
        
    Returns:
        Dictionary with summary information
    """
    if df is None or df.empty:
        return {
            "shape": (0, 0),
            "columns": [],
            "dtypes": {},
            "sample": [],
        }
    
    return {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "sample": df.head(5).to_dict(orient="records"),
        "memory_usage_bytes": df.memory_usage(deep=True).sum(),
    }

