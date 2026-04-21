"""
utils.py - Utility functions for the Economic Indicators Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px


def get_indicator_options(connection, data_group):
    """
    Get indicator options for the given data_group with multiple fallback strategies.
    """
    try:
        from .database import get_indicators
    except ImportError:
        from database import get_indicators
    
    _map = {
        'CONSUMER PRICE INDEX AND INFLATION': 'FACT_CPI',
        'BALANCE OF PAYMENTS': 'FACT_BOP',
        'MONETARY AND FINANCIAL STATISTICS': 'FACT_MONETARY',
        'FISCAL STATISTICS': 'FACT_FISC',
        'INTEREST RATES': 'FACT_INTEREST',
    }
    indicator_options = []

    # Strategy 1: query through fact table (avoids SECTION label mismatches)
    try:
        df_ind = get_indicators(connection, fact_table=_map.get(data_group))
        if not df_ind.empty:
            indicator_options = df_ind['INDICATOR_NAME'].tolist()
            return sorted(indicator_options)
    except Exception:
        pass
    
    # Strategy 2: Query from fact table join
    try:
        _map = {
            'CONSUMER PRICE INDEX AND INFLATION': 'FACT_CPI',
            'BALANCE OF PAYMENTS': 'FACT_BOP',
            'MONETARY AND FINANCIAL STATISTICS': 'FACT_MONETARY',
            'FISCAL STATISTICS': 'FACT_FISC',
            'INTEREST RATES': 'FACT_INTEREST',
        }
        fact_table = _map.get(data_group, 'FACT_CPI')
        query = f"""
            SELECT DISTINCT i.INDICATOR_NAME 
            FROM {fact_table} f
            JOIN DIM_INDICATOR i ON f.INDICATOR_ID = i.INDICATOR_ID
            ORDER BY i.INDICATOR_NAME
        """
        df = pd.read_sql(query, connection)
        indicator_options = df['INDICATOR_NAME'].tolist()
        if indicator_options:
            return sorted(indicator_options)
    except Exception:
        pass
    
    # Strategy 3: All indicators as last resort
    try:
        df_all = pd.read_sql(
            "SELECT DISTINCT INDICATOR_NAME FROM DIM_INDICATOR ORDER BY INDICATOR_NAME",
            connection
        )
        indicator_options = df_all['INDICATOR_NAME'].tolist()
        if indicator_options:
            return sorted(indicator_options)
    except Exception:
        pass
    
    return []


def get_indicator_description(connection, indicator_name):
    """Get description for a single indicator"""
    try:
        query = """
            SELECT DESCRIPTION 
            FROM DIM_INDICATOR 
            WHERE INDICATOR_NAME = :name
        """
        df = pd.read_sql(query, connection, params={'name': indicator_name})
        if not df.empty and pd.notna(df['DESCRIPTION'].iloc[0]):
            return df['DESCRIPTION'].iloc[0]
    except:
        pass
    return None


def display_indicator_descriptions(connection, selected_indicators):
    """Show descriptions in a clean expander"""
    if not selected_indicators:
        return
    
    with st.expander("📋 Indicator Descriptions", expanded=len(selected_indicators) <= 3):
        for ind in selected_indicators:
            desc = get_indicator_description(connection, ind)
            if desc:
                st.markdown(f"**{ind}**  \n{desc}")
            else:
                st.markdown(f"**{ind}** — *description not available*")


def render_date_filters(key_prefix, default_start_year=2020, default_end_year=2023):
    """
    Unified date filter UI — returns (start_year, end_year, start_month, end_month)
    """
    use_date_range = st.checkbox("Use calendar date range", value=False, key=f"{key_prefix}_use_range")
    
    if use_date_range:
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start date",
                value=pd.to_datetime(f"{default_start_year}-01-01"),
                min_value=pd.to_datetime("2015-01-01"),
                max_value=pd.to_datetime("2030-12-31"),
                key=f"{key_prefix}_start_dt"
            )
        with col_end:
            end_date = st.date_input(
                "End date",
                value=pd.to_datetime(f"{default_end_year}-12-31"),
                min_value=pd.to_datetime("2015-01-01"),
                max_value=pd.to_datetime("2030-12-31"),
                key=f"{key_prefix}_end_dt"
            )
        
        return (
            start_date.year, end_date.year,
            start_date.month, end_date.month
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_year = st.number_input(
                "From year", 2015, 2030, default_start_year, key=f"{key_prefix}_start_y"
            )
        with col2:
            end_year = st.number_input(
                "To year", 2015, 2030, default_end_year, key=f"{key_prefix}_end_y"
            )
        
        use_month_filter = st.checkbox("Filter specific months", key=f"{key_prefix}_month_filter")
        start_month = end_month = None
        
        if use_month_filter:
            col3, col4 = st.columns(2)
            with col3:
                start_month = st.number_input("Start month", 1, 12, 1, key=f"{key_prefix}_s_month")
            with col4:
                end_month = st.number_input("End month", 1, 12, 12, key=f"{key_prefix}_e_month")
        
        return start_year, end_year, start_month, end_month


def render_indicator_selector(connection, data_group, key_prefix):
    """
    Modern indicator multiselect with description support
    """
    st.markdown("**Filter by Indicators** (optional — leave empty for all)")
    
    options = get_indicator_options(connection, data_group)
    
    if not options:
        st.warning("No indicators could be loaded. Using full dataset.")
        return None
    
    selected = st.multiselect(
        f"{data_group} indicators",
        options=options,
        default=[],
        key=f"{key_prefix}_indicators",
        help="Select one or more indicators to focus the view",
        placeholder="All indicators will be included if none selected"
    )
    
    if selected:
        st.caption(f"Selected: {len(selected)} indicator(s)")
        display_indicator_descriptions(connection, selected)
    
    return selected if selected else None


def get_quick_stats(connection):
    """Quick counts for sidebar metrics"""
    stats = {'cpi_count': 0, 'bop_count': 0}
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM FACT_CPI")
        stats['cpi_count'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM FACT_BOP")
        stats['bop_count'] = cursor.fetchone()[0]
        cursor.close()
    except:
        pass
    return stats


def render_data_display(df: pd.DataFrame, data_group: str = "Data"):
    """
    Modern data presentation:
      - overview metrics
      - interactive Plotly line chart
      - styled dataframe in expander
      - CSV download
    """
    if df is None or df.empty:
        st.warning("No data returned. Try adjusting filters.")
        return

    # Overview cards
    st.subheader(f"{data_group} Overview")
    cols = st.columns([1, 1.2, 1, 1.3])
    cols[0].metric("Rows", f"{len(df):,}")
    
    time_candidates = ["TIME_PERIOD", "YEAR", "FISCAL_YEAR", "TIME_PERIOD"]
    time_col = next((c for c in time_candidates if c in df.columns), None)
    if time_col:
        cols[1].metric("Time range", f"{df[time_col].min()} – {df[time_col].max()}")
    
    numeric_cols = df.select_dtypes(include="number").columns
    cols[2].metric("Series", len(numeric_cols))
    cols[3].metric("Location", df["LOCATION_NAME"].iloc[0] if "LOCATION_NAME" in df.columns else "—")

    st.divider()

    # ─── Interactive Plotly chart ───────────────────────────────────────
    if time_col and len(numeric_cols) > 0:
        id_vars = [time_col]
        if "LOCATION_NAME" in df.columns:
            id_vars.append("LOCATION_NAME")

        value_vars = [c for c in df.columns if c not in id_vars + ["UNIT", "DESCRIPTION"]]

        if value_vars:
            df_melt = pd.melt(
                df,
                id_vars=id_vars,
                value_vars=value_vars,
                var_name="Indicator",
                value_name="Value"
            )

            fig = px.line(
                df_melt.sort_values(time_col),
                x=time_col,
                y="Value",
                color="Indicator",
                markers=True,
                title=f"{data_group} — Time Series Comparison",
                height=520,
                template="plotly_white"
            )

            fig.update_layout(
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_title=None,
                margin=dict(l=20, r=20, t=60, b=20)
            )

            # Nice formatting for large numbers
            if df_melt["Value"].max() > 1_000_000:
                fig.update_yaxes(tickformat=",")

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Raw table + download in expander
    with st.expander("📋 View Raw Data + Download", expanded=False):
        st.dataframe(
            df.style
              .format(precision=2, thousands=",")
              .background_gradient(subset=numeric_cols, cmap="Blues"),
            use_container_width=True,
            hide_index=True
        )

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"{data_group.lower()}_data_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key=f"dl_{data_group.lower()}"
        )


def format_connection_info(connection):
    """Safe extraction of connection metadata"""
    try:
        return {
            'version': connection.version,
            'username': connection.username or "connected user"
        }
    except:
        return {'version': 'Unknown', 'username': 'Unknown'}