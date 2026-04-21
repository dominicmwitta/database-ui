"""
database.py - Database connection and query functions
"""

import os
import functools
import oracledb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


@functools.lru_cache(maxsize=16)
def get_oracle_connection(username: str, password: str, host: str, port: int = None, service_name: str = None):
    """
    Create Oracle database connection using makedsn approach
    
    Args:
        username: Database username
        password: Database password
        host: Database host (e.g., '172.16.1.219')
        port: Database port (default: 1522)
        service_name: Database service name (default: 'BOT6DB')
    
    Returns:
        Connection object or None if connection fails
    """
    port = port or int(os.getenv("DB_PORT", "1522"))
    service_name = service_name or os.getenv("DB_SERVICE_NAME", "BOT6DB")

    try:
        # Create DSN using makedsn
        dsn = oracledb.makedsn(host, port, service_name=service_name)
        
        # Create connection
        conn = oracledb.connect(
            user=username,
            password=password,
            dsn=dsn
        )
        
        print(f"[OK] Successfully connected to {host}:{port}/{service_name}")
        return conn

    except oracledb.Error as e:
        error, = e.args
        print(f"[ERROR] Oracle connection error: {error.message}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        raise
    


def execute_query(cursor, query, params=None, wide_format=True):
    """
    Execute SQL query and return results as DataFrame
    
    Args:
        cursor: Active database cursor object
        query: SQL query string
        params: Query parameters dictionary (optional)
        wide_format: If True, pivot to wide format with indicators as columns
    
    Returns:
        DataFrame with query results
    """
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)

        if wide_format and not df.empty:
            required_cols = ['TIME_PERIOD', 'LOCATION_NAME', 'INDICATOR_NAME', 'VALUE']
            if all(col in df.columns for col in required_cols):
                df = df.pivot_table(
                    index=['TIME_PERIOD', 'LOCATION_NAME'],
                    columns='INDICATOR_NAME',
                    values='VALUE',
                    aggfunc='first'
                ).reset_index()

        return df
    except Exception as e:
        print(f"[ERROR] Query error: {e}")
        raise


def get_data(
    connection,
    data_group: str,
    start_year=2020,
    start_month=None,
    start_day=None,
    end_year=2030,
    end_month=None,
    end_day=None,
    location='Tanzania',
    indicator_names=None,
    unit_names=None,
    aggregation='monthly',
    wide_format=True,
    fact_table=None,
):
    """
    Get data for any supported indicator group with flexible filtering and aggregation.

    Args:
        connection: Active Oracle connection object
        data_group: One of 'CONSUMER PRICE INDEX AND INFLATION', 'BALANCE OF PAYMENTS', 'MONETARY AND FINANCIAL STATISTICS',
                    'FISCAL STATISTICS', 'INTEREST RATES'
        start_year: Start year for data
        end_year: End year for data
        start_month: Start month (1-12, optional)
        end_month: End month (1-12, optional)
        location: Location name to filter
        indicator_names: List of indicator names to filter (optional)
        unit_names: List of unit names to filter (optional, e.g., ['USD Million', 'TZS Million'])
        aggregation: 'monthly', 'quarterly', 'annual', or 'fiscal_year'
        wide_format: If True, pivot data to wide format
    
    Returns:
        DataFrame with queried data
    """
    cursor = connection.cursor()

    map_table = {'Prices and Interest Rates': 'FACT_CPI',
                 'External Sector': 'FACT_BOP',
                 'Financial Sector Indicators': 'FACT_MONETARY',
                 'Government Finance Statistics':'FACT_FISC',
                 'INTEREST RATES':'FACT_INTEREST',
                 'National Accounts':'FACT_GDP',
                 'Payment Statistics': 'FACT_PAYMENT'}

    if fact_table is None:
        if data_group not in map_table:
            cursor.close()
            raise ValueError(f"Invalid data_group '{data_group}'. Must be one of: {', '.join(map_table.keys())}")
        fact_table = map_table[data_group]

    # Build query based on aggregation level
    if aggregation == 'monthly':
        # Monthly: return all data with proper time columns
        query = f"""
            SELECT 
                t.TIME_PERIOD,
                t.YEAR,
                t.MONTH,
                t.QUARTER,
                l.LOCATION_NAME,
                i.INDICATOR_NAME,
                i.INDICATOR_TYPE,
                i.DESCRIPTION,
                f.VALUE,
                u.UNIT
            FROM {fact_table} f
            JOIN DIM_TIME t ON f.TIME_ID = t.TIME_ID
            JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
            WHERE t.YEAR BETWEEN :start_year AND :end_year
            AND l.LOCATION_NAME = :location
        """
    
    elif aggregation == 'quarterly':
        # Quarterly: CPI/Interest → AVG; FLOW → SUM, STOCK → end-of-quarter, other → AVG.
        # National Accounts (FACT_GDP): percentage-change units → AVG regardless of type.
        if fact_table in ('FACT_CPI', 'FACT_INTEREST'):
            _value_expr = "AVG(f.VALUE)"
        elif fact_table == 'FACT_GDP':
            _value_expr = """CASE
                    WHEN UPPER(u.UNIT) LIKE '%PERCENT%' OR UPPER(u.UNIT) LIKE '%PERCENTAGE%' THEN AVG(f.VALUE)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.IS_QUARTER_END = 1 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        else:
            _value_expr = """CASE
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.IS_QUARTER_END = 1 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        query = f"""
            SELECT
                t.YEAR || 'Q' || t.QUARTER AS TIME_PERIOD,
                t.YEAR,
                t.QUARTER,
                l.LOCATION_NAME,
                i.INDICATOR_NAME,
                i.INDICATOR_TYPE,
                i.DESCRIPTION,
                {_value_expr} AS VALUE,
                u.UNIT
            FROM {fact_table} f
            JOIN DIM_TIME t ON f.TIME_ID = t.TIME_ID
            JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
            WHERE t.YEAR BETWEEN :start_year AND :end_year
            AND l.LOCATION_NAME = :location
        """
    
    elif aggregation == 'fiscal_year':
        # Fiscal Year (July-June): CPI/Interest → AVG; FLOW → SUM, STOCK → June end-value, other → AVG.
        # National Accounts (FACT_GDP): percentage-change units → AVG regardless of type.
        if fact_table in ('FACT_CPI', 'FACT_INTEREST'):
            _value_expr = "AVG(f.VALUE)"
        elif fact_table == 'FACT_GDP':
            _value_expr = """CASE
                    WHEN UPPER(u.UNIT) LIKE '%PERCENT%' OR UPPER(u.UNIT) LIKE '%PERCENTAGE%' THEN AVG(f.VALUE)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.MONTH = 6 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        else:
            _value_expr = """CASE
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.MONTH = 6 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        query = f"""
            SELECT
                'FY' || CASE
                    WHEN t.MONTH >= 7 THEN t.YEAR || '/' || (t.YEAR + 1)
                    ELSE (t.YEAR - 1) || '/' || t.YEAR
                END AS TIME_PERIOD,
                CASE
                    WHEN t.MONTH >= 7 THEN t.YEAR
                    ELSE t.YEAR - 1
                END AS FISCAL_YEAR,
                l.LOCATION_NAME,
                i.INDICATOR_NAME,
                i.INDICATOR_TYPE,
                i.DESCRIPTION,
                {_value_expr} AS VALUE,
                u.UNIT
            FROM {fact_table} f
            JOIN DIM_TIME t ON f.TIME_ID = t.TIME_ID
            JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
            WHERE (
                (t.YEAR = :start_year - 1 AND t.MONTH >= 7) OR
                (t.YEAR BETWEEN :start_year AND :end_year) OR
                (t.YEAR = :end_year + 1 AND t.MONTH <= 6)
            )
            AND l.LOCATION_NAME = :location
        """
    
    else:  # annual
        # Annual: CPI/Interest → AVG; FLOW → SUM, STOCK → December end-value, other → AVG.
        # National Accounts (FACT_GDP): percentage-change units → AVG regardless of type.
        if fact_table in ('FACT_CPI', 'FACT_INTEREST'):
            _value_expr = "AVG(f.VALUE)"
        elif fact_table == 'FACT_GDP':
            _value_expr = """CASE
                    WHEN UPPER(u.UNIT) LIKE '%PERCENT%' OR UPPER(u.UNIT) LIKE '%PERCENTAGE%' THEN AVG(f.VALUE)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.MONTH = 12 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        else:
            _value_expr = """CASE
                    WHEN UPPER(i.INDICATOR_TYPE) = 'STOCK' THEN MAX(CASE WHEN t.MONTH = 12 THEN f.VALUE END)
                    WHEN UPPER(i.INDICATOR_TYPE) = 'FLOW' THEN SUM(f.VALUE)
                    ELSE AVG(f.VALUE)
                END"""
        query = f"""
            SELECT
                t.YEAR AS TIME_PERIOD,
                t.YEAR,
                l.LOCATION_NAME,
                i.INDICATOR_NAME,
                i.INDICATOR_TYPE,
                i.DESCRIPTION,
                {_value_expr} AS VALUE,
                u.UNIT
            FROM {fact_table} f
            JOIN DIM_TIME t ON f.TIME_ID = t.TIME_ID
            JOIN DIM_LOCATION l ON f.LOCATION_ID = l.LOCATION_ID
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
            WHERE t.YEAR BETWEEN :start_year AND :end_year
            AND l.LOCATION_NAME = :location
        """
    
    params = {
        'start_year': start_year,
        'end_year': end_year,
        'location': location
    }

    # Precise start boundary (month-level; DAY column not present in DIM_TIME)
    if start_month:
        params['start_month'] = start_month
        query += (" AND (t.YEAR > :start_year"
                  " OR (t.YEAR = :start_year AND t.MONTH >= :start_month))")

    # Precise end boundary
    if end_month:
        params['end_month'] = end_month
        query += (" AND (t.YEAR < :end_year"
                  " OR (t.YEAR = :end_year AND t.MONTH <= :end_month))")

    # Add indicator filter if specified
    if indicator_names and len(indicator_names) > 0:
        if isinstance(indicator_names, str):
            indicator_names = [indicator_names]
        placeholders = ','.join([f':ind{i}' for i in range(len(indicator_names))])
        query += f" AND i.INDICATOR_NAME IN ({placeholders})"
        for i, name in enumerate(indicator_names):
            params[f'ind{i}'] = name
    
    # Add unit filter if specified
    if unit_names and len(unit_names) > 0:
        if isinstance(unit_names, str):
            unit_names = [unit_names]
        placeholders = ','.join([f':unit{i}' for i in range(len(unit_names))])
        query += f" AND u.UNIT IN ({placeholders})"
        for i, name in enumerate(unit_names):
            params[f'unit{i}'] = name

    # Add GROUP BY for aggregated queries
    if aggregation == 'quarterly':
        query += """
            GROUP BY t.YEAR, t.QUARTER, l.LOCATION_NAME, 
                     i.INDICATOR_NAME, i.INDICATOR_TYPE, i.DESCRIPTION, u.UNIT
            ORDER BY t.YEAR, t.QUARTER, i.INDICATOR_NAME
        """
    elif aggregation == 'fiscal_year':
        query += """
            GROUP BY 
                CASE 
                    WHEN t.MONTH >= 7 THEN t.YEAR
                    ELSE t.YEAR - 1
                END,
                CASE 
                    WHEN t.MONTH >= 7 THEN t.YEAR || '/' || (t.YEAR + 1)
                    ELSE (t.YEAR - 1) || '/' || t.YEAR
                END,
                l.LOCATION_NAME, 
                i.INDICATOR_NAME, i.INDICATOR_TYPE, i.DESCRIPTION, u.UNIT
            ORDER BY 
                CASE 
                    WHEN t.MONTH >= 7 THEN t.YEAR
                    ELSE t.YEAR - 1
                END, 
                i.INDICATOR_NAME
        """
    elif aggregation == 'annual':
        query += """
            GROUP BY t.YEAR, l.LOCATION_NAME, 
                     i.INDICATOR_NAME, i.INDICATOR_TYPE, i.DESCRIPTION, u.UNIT
            ORDER BY t.YEAR, i.INDICATOR_NAME
        """
    else:
        query += " ORDER BY t.TIME_PERIOD, l.LOCATION_NAME, i.INDICATOR_NAME"

    df = execute_query(cursor, query, params, wide_format=wide_format)
    cursor.close()
    return df


@functools.lru_cache(maxsize=8)
def get_units(_connection):
    """
    Get list of available units from database

    Args:
        _connection: Active Oracle connection object

    Returns:
        List of unit names
    """
    try:
        df = pd.read_sql("SELECT DISTINCT UNIT FROM DIM_UNITS ORDER BY UNIT", _connection)
        return df['UNIT'].tolist()
    except:
        return []


@functools.lru_cache(maxsize=64)
def get_units_for_indicators(_connection, indicator_names: tuple, indicator_type: str, fact_table: str = None):
    """
    Get list of units that are actually used by the specified indicators
    through the fact table join. Cached for 5 minutes.

    Args:
        _connection: Active Oracle connection object
        indicator_names: Tuple of indicator names to filter by (tuple for caching)
        indicator_type: Indicator group name (must be a key in MAP_TABLE) to determine which fact table to use

    Returns:
        List of unit names relevant to the selected indicators
    """
    if not indicator_names:
        return []

    try:
        if fact_table is None:
            map_table = {'CONSUMER PRICE INDEX AND INFLATION': 'FACT_CPI',
                         'BALANCE OF PAYMENTS': 'FACT_BOP',
                         'MONETARY AND FINANCIAL STATISTICS': 'FACT_MONETARY',
                         'FISCAL STATISTICS': 'FACT_FISC',
                         'INTEREST RATES': 'FACT_INTEREST',
                         'NATIONAL ACCOUNTS': 'FACT_GDP'}
            fact_table = map_table.get(indicator_type, 'FACT_CPI')

        # Create parameterized query
        placeholders = ','.join([f':ind{i}' for i in range(len(indicator_names))])
        query = f"""
            SELECT DISTINCT u.UNIT
            FROM {fact_table} f
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            LEFT JOIN DIM_UNITS u ON f.UNIT_ID = u.UNIT_ID
            WHERE i.INDICATOR_NAME IN ({placeholders})
            AND u.UNIT IS NOT NULL
            ORDER BY u.UNIT
        """
        params = {f'ind{i}': name for i, name in enumerate(indicator_names)}

        cursor = _connection.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        return [row[0] for row in rows if row[0]]
    except:
        return []


@functools.lru_cache(maxsize=8)
def get_locations(_connection):
    """
    Get list of available locations from database
    
    Args:
        _connection: Active Oracle connection object
    
    Returns:
        List of location names
    """
    try:
        df = pd.read_sql("SELECT DISTINCT LOCATION_NAME FROM DIM_LOCATION ORDER BY LOCATION_NAME", _connection)
        return df['LOCATION_NAME'].tolist()
    except:
        return []


@functools.lru_cache(maxsize=16)
def get_indicators(_connection, section=None, fact_table=None):
    """
    Get list of available indicators from database.

    When `fact_table` is provided the query joins through that fact table,
    guaranteeing results that match the actual data regardless of how
    DIM_INDICATOR.SECTION is labelled.  This is the preferred call pattern.

    When only `section` is provided the query filters DIM_INDICATOR.SECTION
    directly (legacy behaviour, relies on SECTION values matching).

    Args:
        _connection: Active Oracle connection object
        fact_table: Fact table name to join through (e.g. 'FACT_CPI').
                    Takes precedence over `section` when supplied.
        section: Filter by indicator group label stored in DIM_INDICATOR.SECTION
                 (e.g. 'CONSUMER PRICE INDEX AND INFLATION').  Used only when
                 fact_table is not provided.

    Returns:
        DataFrame with INDICATOR_NAME, DESCRIPTION, and DEFINITION columns.
    """
    try:
        if fact_table:
            query = f"""
                SELECT DISTINCT i.INDICATOR_NAME, i.DESCRIPTION, i.DEFINITION
                FROM {fact_table} f
                JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
                ORDER BY i.INDICATOR_NAME
            """
            return pd.read_sql(query, _connection)

        # Legacy path: filter by SECTION / INDICATOR_TYPE label
        if section:
            query = """
                SELECT INDICATOR_NAME, DESCRIPTION, DEFINITION, SECTION
                FROM DIM_INDICATOR
                WHERE (UPPER(SECTION) = UPPER(:section)
                       OR (SECTION IS NULL AND UPPER(INDICATOR_TYPE) = UPPER(:section)))
                ORDER BY INDICATOR_NAME
            """
            return pd.read_sql(query, _connection, params={'section': section})

        # No filter — return everything
        query = """
            SELECT INDICATOR_NAME, DESCRIPTION, DEFINITION,
                   CASE
                       WHEN EXISTS (SELECT 1 FROM USER_TAB_COLUMNS
                                    WHERE TABLE_NAME = 'DIM_INDICATOR'
                                    AND COLUMN_NAME = 'SECTION')
                       THEN SECTION
                       ELSE INDICATOR_TYPE
                   END AS SECTION
            FROM DIM_INDICATOR
            ORDER BY INDICATOR_NAME
        """
        return pd.read_sql(query, _connection)

    except Exception:
        try:
            query = "SELECT INDICATOR_NAME, DESCRIPTION, DEFINITION FROM DIM_INDICATOR"
            if section:
                query += " WHERE UPPER(SECTION) = UPPER(:section)"
                return pd.read_sql(query + " ORDER BY INDICATOR_NAME", _connection, params={'section': section})
            return pd.read_sql(query + " ORDER BY INDICATOR_NAME", _connection)
        except:
            return pd.DataFrame()


def test_connection(connection):
    """
    Test database connection by querying current timestamp
    
    Args:
        connection: Active Oracle connection object
    
    Returns:
        Tuple of (success: bool, message: str, timestamp: str)
    """
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT SYSDATE FROM DUAL")
        result = cursor.fetchone()
        cursor.close()
        return True, "Connection active", str(result[0])
    except Exception as e:
        return False, f"Connection failed: {e}", None