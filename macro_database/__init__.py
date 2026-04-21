"""
Economic Indicators Dashboard
A Streamlit-based dashboard for exploring Macroeconomic data
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .database import (
    get_oracle_connection,
    get_data,
    get_locations,
    get_indicators,
    get_units,
    test_connection
)

__all__ = [
    'get_oracle_connection',
    'get_data',
    'get_locations',
    'get_indicators',
    'get_units',
    'test_connection'
]