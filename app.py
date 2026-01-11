"""
Streamlit Application for RRG Chart Visualization
Visualizes Relative Rotation Graphs for different sectors on daily and weekly basis
Redesigned UI with three-pane layout: Left (Settings), Middle (Chart), Right (Selection)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import colorsys
import time
from dotenv import load_dotenv
import warnings
import logging

# Suppress all Streamlit warnings about Session State API
# This prevents warning messages from appearing in the UI
warnings.filterwarnings("ignore", message=".*Session State API.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*was created with a default value but also had its value set via the Session State API.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*created with a default value but also had its value set via the Session State API.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*default value but also had its value set.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*The widget with key.*was created with a default value but also had its value set via the Session State API.*", category=UserWarning)

# Suppress Streamlit session state logging
logging.getLogger("streamlit.runtime.state.session_state").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.state").setLevel(logging.ERROR)

# Suppress all UserWarnings (Streamlit uses these for widget warnings)
warnings.filterwarnings("ignore", category=UserWarning)

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from loaders.AngelOneLoader import AngelOneLoader
from rrg_calculator import RRGCalculator
from sectors import BENCHMARKS, SECTORS, SUB_SECTORS
from token_fetcher import get_token_from_symbol
from scrip_master_search import search_indices, search_stocks, search_etfs, get_item_by_symbol, get_stocks, get_etfs, get_indices, get_etfs

# Custom CSS to remove top margin and make UI compact
st.markdown("""
    <style>
        .main .block-container {
            padding-top: 0.5rem;
            padding-bottom: 1rem;
        }
        h3 {
            font-size: 1.2rem;
            margin-bottom: 0.3rem;
            margin-top: 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Load API credentials from environment variables
API_CONFIG = {
    "API_KEY": os.getenv("API_KEY", ""),
    "CLIENT_ID": os.getenv("CLIENT_ID", ""),
    "PASSWORD": os.getenv("PASSWORD", ""),
    "TOTP_TOKEN": os.getenv("TOTP_TOKEN", ""),
    "EXCHANGE": os.getenv("EXCHANGE", "NSE")
}

# Validate that all required credentials are present
if not all([API_CONFIG["API_KEY"], API_CONFIG["CLIENT_ID"], API_CONFIG["PASSWORD"], API_CONFIG["TOTP_TOKEN"]]):
    st.error("⚠️ Missing API credentials! Please create a .env file with your AngelOne API credentials. See .env.example for reference.")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="RRG Chart Visualization",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Major indices to initialize on first load (sectoral indices)
MAJOR_INDICES = [
    "NIFTY Bank",
    "NIFTY Financial Services",
    "NIFTY IT",
    "NIFTY FMCG",
    "NIFTY Pharma",
    "NIFTY Healthcare",
    "NIFTY Auto",
    "NIFTY Metal",
    "NIFTY Energy",
    "NIFTY Realty",
    "NIFTY PSU Bank",
    "NIFTY Infrastructure"
]

# Default stocks to show when Stock tab is selected
DEFAULT_STOCKS = [
    "RELIANCE-EQ",
    "TCS-EQ",
    "HDFCBANK-EQ",
    "INFY-EQ",
    "ICICIBANK-EQ",
    "HINDUNILVR-EQ"
]

# Default ETFs to show when ETF tab is selected
DEFAULT_ETFS = [
    "BANKBEES-EQ",
    "GOLDBEES-EQ",
    "JUNIORBEES-EQ",
    "ITBEES-EQ"
]

# Initialize session state
if 'loader' not in st.session_state:
    st.session_state.loader = None
if 'token_cache' not in st.session_state:
    st.session_state.token_cache = {}
if 'selected_indices' not in st.session_state:
    st.session_state.selected_indices = []
if 'selected_stocks' not in st.session_state:
    st.session_state.selected_stocks = []
if 'selected_etfs' not in st.session_state:
    st.session_state.selected_etfs = []
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Index"
if 'is_initialized' not in st.session_state:
    st.session_state.is_initialized = False
if 'chart_cache_key' not in st.session_state:
    st.session_state.chart_cache_key = None
if 'cached_chart' not in st.session_state:
    st.session_state.cached_chart = None
if 'cached_items_data' not in st.session_state:
    st.session_state.cached_items_data = None
if 'cached_calculator' not in st.session_state:
    st.session_state.cached_calculator = None
if 'animation_date_index' not in st.session_state:
    st.session_state.animation_date_index = None
if 'is_animating' not in st.session_state:
    st.session_state.is_animating = False
if 'available_dates' not in st.session_state:
    st.session_state.available_dates = []
# Per-tab animation state
if 'use_animation_index' not in st.session_state:
    st.session_state.use_animation_index = False
if 'use_animation_stock' not in st.session_state:
    st.session_state.use_animation_stock = False
if 'use_animation_etf' not in st.session_state:
    st.session_state.use_animation_etf = False


def initialize_default_items():
    """Initialize default items based on active tab"""
    active_tab = st.session_state.get('active_tab', 'Index')
    
    # Set default timeframe to weekly on first load
    if 'timeframe' not in st.session_state:
        st.session_state.timeframe = 'weekly'
    
    # Initialize indices if Index tab is active and no indices selected
    if active_tab == "Index" and not st.session_state.selected_indices:
        try:
            all_indices = get_indices()
            major_indices_dict = {}
            
            for idx in all_indices:
                # Skip NIFTY 50 and NIFTY (exact matches)
                if idx['symbol'].upper() in ['NIFTY 50', 'NIFTY', 'NIFTY50'] or idx['name'].upper() in ['NIFTY 50', 'NIFTY', 'NIFTY50']:
                    continue
                
                # Match by symbol first
                if idx['symbol'] in MAJOR_INDICES:
                    major_indices_dict[idx['symbol']] = idx
                else:
                    # Try to match by name (use word boundaries to avoid partial matches)
                    idx_name_upper = idx['name'].upper()
                    idx_symbol_upper = idx['symbol'].upper()
                    
                    for major in MAJOR_INDICES:
                        major_upper = major.upper()
                        # Exact symbol match
                        if idx_symbol_upper == major_upper:
                            if major not in major_indices_dict:
                                major_indices_dict[major] = idx
                                break
                        # Check if name matches exactly or as a complete word (not substring)
                        elif (idx_name_upper == major_upper or 
                              idx_name_upper.replace(' ', '') == major_upper.replace(' ', '') or
                              # Match as complete word (not substring) - e.g., "NIFTY IT" matches "NIFTY IT" but not "NIFTY 50"
                              (major_upper in idx_name_upper and 
                               (idx_name_upper.startswith(major_upper + ' ') or 
                                idx_name_upper.endswith(' ' + major_upper) or
                                ' ' + major_upper + ' ' in idx_name_upper))):
                            if major not in major_indices_dict:
                                major_indices_dict[major] = idx
                                break
            
            # Add to selected indices
            for major_symbol in MAJOR_INDICES:
                if major_symbol in major_indices_dict:
                    idx_item = major_indices_dict[major_symbol]
                    if not any(x['symbol'] == idx_item['symbol'] for x in st.session_state.selected_indices):
                        st.session_state.selected_indices.append(idx_item)
        except Exception:
            pass
    
    # Initialize stocks if Stock tab is active and no stocks selected
    elif active_tab == "Stock" and not st.session_state.selected_stocks:
        try:
            all_stocks = get_stocks()
            for default_symbol in DEFAULT_STOCKS:
                # Find stock by symbol
                stock_item = next((s for s in all_stocks if s['symbol'] == default_symbol), None)
                if stock_item and not any(x['symbol'] == stock_item['symbol'] for x in st.session_state.selected_stocks):
                    st.session_state.selected_stocks.append(stock_item)
        except Exception:
            pass
    
    # Initialize ETFs if ETF tab is active and no ETFs selected
    elif active_tab == "ETF" and not st.session_state.selected_etfs:
        try:
            all_etfs = get_etfs()
            for default_symbol in DEFAULT_ETFS:
                # Find ETF by symbol
                etf_item = next((e for e in all_etfs if e['symbol'] == default_symbol), None)
                if etf_item and not any(x['symbol'] == etf_item['symbol'] for x in st.session_state.selected_etfs):
                    st.session_state.selected_etfs.append(etf_item)
        except Exception:
            pass


def generate_unique_colors(count: int) -> list:
    """Generate unique colors for chart tails"""
    colors = []
    for i in range(count):
        hue = i / count
        saturation = 0.7 + (i % 3) * 0.1
        lightness = 0.5 + (i % 2) * 0.1
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )
        colors.append(hex_color)
    return colors


def initialize_api_loader():
    """Initialize AngelOne API loader with retry logic and better error handling"""
    # Close existing loader if timeframe changed
    if st.session_state.loader is not None:
        try:
            st.session_state.loader.close()
        except:
            pass
    
    # Retry logic for connection timeouts
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            loader = AngelOneLoader(
                config=API_CONFIG,
                tf=st.session_state.get('timeframe', 'daily'),
                period=st.session_state.get('period', 200)
            )
            return loader
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a connection timeout error
            is_timeout = ('timeout' in error_str or 
                         'connection' in error_str or 
                         'max retries' in error_str or
                         'connecttimeouterror' in error_str)
            
            if is_timeout and attempt < max_retries - 1:
                # Retry with exponential backoff
                import time
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # Only show error on final attempt or for non-timeout errors
                if attempt == max_retries - 1:
                    # Log error silently - don't show error message to user
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to initialize API loader after {max_retries} attempts: {e}")
                    # Don't show st.error - let the app continue without loader
                    # The generate_chart function will handle None loader gracefully
                elif not is_timeout:
                    # Non-timeout errors - log but don't retry
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to initialize API loader: {e}")
                return None
    
    return None


def get_token(symbol):
    """Get token for symbol, using cache if available"""
    if symbol in st.session_state.token_cache:
        return st.session_state.token_cache[symbol]
    
    token = get_token_from_symbol(symbol)
    if token:
        st.session_state.token_cache[symbol] = token
    return token


def get_stock_data(loader, symbol, token):
    """Get stock data from loader"""
    try:
        df = loader.get(symbol, token)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching data for {symbol} (token: {token}): {e}")
        return None


def create_rrg_chart_with_animation(items_data, calculator, tail_count=8, colors_map=None, filtered_dates=None):
    """
    Create RRG chart with Plotly animation frames for smooth transitions
    
    :param items_data: Dict of {symbol: (rs_series, momentum_series, df)}
    :param calculator: RRGCalculator instance
    :param tail_count: Number of tail points to show
    :param colors_map: Dict mapping symbol to color
    :param filtered_dates: List of dates to create frames for
    """
    fig = go.Figure()
    
    if not filtered_dates or not items_data:
        # Return empty chart if no dates or data
        fig.update_xaxes(title_text="RS Ratio", range=[93, 107], showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(title_text="RS Momentum", range=[93, 107], showgrid=True, gridwidth=1, gridcolor='lightgray')
        # Add quadrant backgrounds for empty chart
        fig.add_shape(type="rect", x0=93, y0=100, x1=100, y1=107, fillcolor="#b1ebff", layer="below", line_width=0)
        fig.add_shape(type="rect", x0=100, y0=100, x1=107, y1=107, fillcolor="#bdffc9", layer="below", line_width=0)
        fig.add_shape(type="rect", x0=100, y0=93, x1=107, y1=100, fillcolor="#fff7b8", layer="below", line_width=0)
        fig.add_shape(type="rect", x0=93, y0=93, x1=100, y1=100, fillcolor="#ffb9c6", layer="below", line_width=0)
        fig.add_hline(y=100, line_dash="dash", line_color="black", line_width=0.5)
        fig.add_vline(x=100, line_dash="dash", line_color="black", line_width=0.5)
        fig.update_layout(
            title=f"RRG Chart - {st.session_state.get('benchmark_name', 'NIFTY 50')} ({st.session_state.get('timeframe', 'daily').upper()})",
            height=600,
            hovermode='closest',
            template='plotly_white',
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5)
        )
        return fig
    
    # Calculate step for frames (fewer frames for performance)
    step = max(1, len(filtered_dates) // (50 * tail_count))
    frame_dates = filtered_dates[::step]
    if frame_dates[-1] != filtered_dates[-1]:
        frame_dates.append(filtered_dates[-1])
    
    # Calculate global axis range from all data
    x_min, x_max = 200, 0
    y_min, y_max = 200, 0
    
    for symbol, (rs_series, momentum_series, df) in items_data.items():
        if len(rs_series) > 0 and len(momentum_series) > 0:
            x_min = min(x_min, rs_series.min())
            x_max = max(x_max, rs_series.max())
            y_min = min(y_min, momentum_series.min())
            y_max = max(y_max, momentum_series.max())
    
    # Calculate symmetric range around center (100, 100)
    center_x, center_y = 100, 100
    if x_min >= 200 or x_max <= 0:
        x_range = y_range = 7
    else:
        # Calculate maximum distance from center on each axis
        # Add reasonable padding (5% of data range, minimum 1.5 units)
        x_data_range = x_max - x_min
        y_data_range = y_max - y_min
        x_padding = max(x_data_range * 0.05, 1.5)
        y_padding = max(y_data_range * 0.05, 1.5)
        
        x_dist_from_center = max(abs(x_min - center_x), abs(x_max - center_x)) + x_padding
        y_dist_from_center = max(abs(y_min - center_y), abs(y_max - center_y)) + y_padding
        x_range = max(x_dist_from_center, 7)
        y_range = max(y_dist_from_center, 7)
    
    # Calculate axis limits
    x_axis_min = center_x - x_range
    x_axis_max = center_x + x_range
    y_axis_min = center_y - y_range
    y_axis_max = center_y + y_range
    
    # Add quadrant backgrounds (stretched to corners based on calculated ranges)
    fig.add_shape(
        type="rect",
        x0=x_axis_min, y0=100, x1=center_x, y1=y_axis_max,
        fillcolor="#b1ebff",  # Light blue - Improving
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=center_x, y0=100, x1=x_axis_max, y1=y_axis_max,
        fillcolor="#bdffc9",  # Light green - Leading
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=center_x, y0=y_axis_min, x1=x_axis_max, y1=100,
        fillcolor="#fff7b8",  # Light yellow - Weakening
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=x_axis_min, y0=y_axis_min, x1=center_x, y1=100,
        fillcolor="#ffb9c6",  # Light pink - Lagging
        layer="below",
        line_width=0,
    )
    
    # Add quadrant lines (static)
    fig.add_hline(y=100, line_dash="dash", line_color="black", line_width=0.5)
    fig.add_vline(x=100, line_dash="dash", line_color="black", line_width=0.5)
    
    # Create frames for each date
    frames = []
    for frame_date in frame_dates:
        cutoff_ts = pd.Timestamp(frame_date) if not isinstance(frame_date, pd.Timestamp) else frame_date
        
        frame_data = []
        for symbol, (rs_series, momentum_series, df) in items_data.items():
            # Filter data up to cutoff_date
            rs_filtered = rs_series[rs_series.index <= cutoff_ts]
            momentum_filtered = momentum_series[momentum_series.index <= cutoff_ts]
            
            if len(rs_filtered) == 0 or len(momentum_filtered) == 0:
                continue
            if len(rs_filtered) < tail_count or len(momentum_filtered) < tail_count:
                continue
            
            try:
                rs_tail = rs_filtered.iloc[-tail_count:]
                momentum_tail = momentum_filtered.iloc[-tail_count:]
                current_rs = rs_filtered.iloc[-1]
                current_momentum = momentum_filtered.iloc[-1]
            except (IndexError, KeyError):
                continue
            
            color = colors_map.get(symbol, "#000000") if colors_map else "#000000"
            
            # Tail line trace
            frame_data.append(go.Scatter(
                x=rs_tail.values,
                y=momentum_tail.values,
                mode='lines+markers',
                name=symbol,
                line=dict(color=color, width=2),
                marker=dict(size=8, color=color),
                hovertemplate=f'<b>{symbol}</b><br>' +
                             'RS: %{x:.2f}<br>' +
                             'Momentum: %{y:.2f}<br>' +
                             '<extra></extra>',
                showlegend=True
            ))
            
            # Current point trace
            frame_data.append(go.Scatter(
                x=[current_rs],
                y=[current_momentum],
                mode='markers+text',
                name=f'{symbol} (Current)',
                marker=dict(size=15, color=color, symbol='circle'),
                text=[symbol],
                textposition="top center",
                textfont=dict(size=10, color=color),
                hovertemplate=f'<b>{symbol}</b><br>RS: {current_rs:.2f}<br>Momentum: {current_momentum:.2f}<br>Quadrant: {calculator.get_quadrant(current_rs, current_momentum)}<br><extra></extra>',
                showlegend=False
            ))
        
        # Create frame
        frames.append(go.Frame(
            data=frame_data,
            name=str(frame_date)
        ))
    
    # Add initial traces (empty, will be populated by first frame)
    for symbol in items_data.keys():
        color = colors_map.get(symbol, "#000000") if colors_map else "#000000"
        fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='lines+markers',
            name=symbol,
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color),
            showlegend=True
        ))
        fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='markers+text',
            name=f'{symbol} (Current)',
            marker=dict(size=15, color=color, symbol='circle'),
            showlegend=False
        ))
    
    # Set axis ranges (using calculated ranges)
    fig.update_xaxes(
        title_text="RS Ratio",
        range=[x_axis_min, x_axis_max],
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    fig.update_yaxes(
        title_text="RS Momentum",
        range=[y_axis_min, y_axis_max],
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    
    # Add quadrant labels positioned within chart bounds (after axis ranges are set)
    # Position labels at 15% from edges, ensuring they're visible and bold
    label_x_offset = x_range * 0.15
    label_y_offset = y_range * 0.15
    min_offset = 1.0  # Minimum offset to ensure visibility
    
    label_x_left = max(center_x - x_range + max(label_x_offset, min_offset), center_x - x_range + 1.0)
    label_x_right = min(center_x + x_range - max(label_x_offset, min_offset), center_x + x_range - 1.0)
    label_y_bottom = max(center_y - y_range + max(label_y_offset, min_offset), center_y - y_range + 1.0)
    label_y_top = min(center_y + y_range - max(label_y_offset, min_offset), center_y + y_range - 1.0)
    
    fig.add_annotation(
        x=label_x_left, 
        y=label_y_top, 
        text="<b>Improving</b>", 
        showarrow=False, 
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_right, 
        y=label_y_top, 
        text="<b>Leading</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_right, 
        y=label_y_bottom, 
        text="<b>Weakening</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_left, 
        y=label_y_bottom, 
        text="<b>Lagging</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    
    # Add frames
    fig.frames = frames
    
    # Animation controls
    fig.update_layout(
        title=f"RRG Chart - {st.session_state.get('benchmark_name', 'NIFTY 50')} ({st.session_state.get('timeframe', 'daily').upper()})",
        height=600,
        hovermode='closest',
        template='plotly_white',
        margin=dict(b=75, l=50, r=50, t=50),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5),
        updatemenus=[{
            "buttons": [
                {
                    "args": [None, {
                        "frame": {"duration": 300, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 200, "easing": "linear"}
                    }],
                    "label": "▶️ Play",
                    "method": "animate"
                },
                {
                    "args": [[None], {
                        "frame": {"duration": 0, "redraw": True},
                        "mode": "immediate",
                        "transition": {"duration": 0}
                    }],
                    "label": "⏸️ Pause",
                    "method": "animate"
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 1},
            "showactive": True,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": -0.355,
            "yanchor": "top"
        }],
        sliders=[{
            "active": len(frames) - 1,
            "yanchor": "top",
            "xanchor": "left",
            "currentvalue": {
                "prefix": "Date: ",
                "visible": True,
                "xanchor": "right"
            },
            "transition": {"duration": 200, "easing": "linear"},
            "pad": {"b": 10, "t": 1},
            "len": 0.9,
            "x": 0.1,
            "y": -0.36,
            "steps": [
                {
                    "args": [[frame.name], {
                        "frame": {"duration": 0, "redraw": True},
                        "mode": "immediate",
                        "transition": {"duration": 0}
                    }],
                    "label": pd.Timestamp(frame.name).strftime('%d %b %Y') if isinstance(frame.name, str) else str(frame.name),
                    "method": "animate"
                }
                for frame in frames
            ]
        }]
    )
    
    return fig


def precompute_charts_for_dates(items_data, calculator, tail_count, colors_map, dates):
    """
    Precompute RRG charts for all dates in the given list.
    Returns a dictionary mapping date (as normalized timestamp) to chart figure.
    """
    precomputed = {}
    for date in dates:
        # Normalize date for consistent key
        if isinstance(date, pd.Timestamp):
            date_key = date.normalize()
        else:
            date_key = pd.Timestamp(date).normalize()
        
        # Create chart for this date
        fig = create_rrg_chart(
            items_data,
            None,
            calculator,
            tail_count=tail_count,
            colors_map=colors_map,
            cutoff_date=date_key
        )
        precomputed[date_key] = fig
    
    return precomputed


def create_rrg_chart(items_data, benchmark_data, calculator, tail_count=8, colors_map=None, cutoff_date=None):
    """
    Create RRG chart using Plotly
    
    :param items_data: Dict of {symbol: (rs_series, momentum_series, df)}
    :param benchmark_data: Benchmark DataFrame
    :param calculator: RRGCalculator instance
    :param tail_count: Number of tail points to show
    :param colors_map: Dict mapping symbol to color
    :param cutoff_date: Optional datetime to filter data up to this date
    """
    fig = go.Figure()
    
    # Track min/max for axis limits
    x_min, x_max = 200, 0
    y_min, y_max = 200, 0
    
    # Plot each item
    for symbol, (rs_series, momentum_series, df) in items_data.items():
        # Filter data up to cutoff_date if provided
        if cutoff_date is not None:
            # Convert cutoff_date to pandas Timestamp and normalize to date only (no time component)
            cutoff_ts = pd.Timestamp(cutoff_date) if not isinstance(cutoff_date, pd.Timestamp) else cutoff_date
            cutoff_ts = cutoff_ts.normalize()  # Remove time component for exact date matching
            
            # Filter series to only include dates up to and including cutoff_date
            # Normalize index dates for comparison to ensure exact date matching (especially for weekly charts)
            rs_mask = [pd.Timestamp(d).normalize() <= cutoff_ts for d in rs_series.index]
            momentum_mask = [pd.Timestamp(d).normalize() <= cutoff_ts for d in momentum_series.index]
            
            rs_series = rs_series[rs_mask]
            momentum_series = momentum_series[momentum_mask]
        
        # Validate that we have enough data
        if len(rs_series) == 0 or len(momentum_series) == 0:
            continue
        if len(rs_series) < tail_count or len(momentum_series) < tail_count:
            continue
        
        try:
            # Get tail data (last tail_count points up to cutoff_date)
            rs_tail = rs_series.iloc[-tail_count:]
            momentum_tail = momentum_series.iloc[-tail_count:]
            
            # Get current values (last point up to cutoff_date)
            current_rs = rs_series.iloc[-1]
            current_momentum = momentum_series.iloc[-1]
        except (IndexError, KeyError):
            # Skip items with invalid data
            continue
        
        # Get unique color for this symbol
        color = colors_map.get(symbol, "#000000") if colors_map else "#000000"
        
        # Update min/max
        x_min = min(x_min, rs_tail.min())
        x_max = max(x_max, rs_tail.max())
        y_min = min(y_min, momentum_tail.min())
        y_max = max(y_max, momentum_tail.max())
        
        # Add tail line
        fig.add_trace(go.Scatter(
            x=rs_tail.values,
            y=momentum_tail.values,
            mode='lines+markers',
            name=symbol,
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color),
            hovertemplate=f'<b>{symbol}</b><br>' +
                         'RS: %{x:.2f}<br>' +
                         'Momentum: %{y:.2f}<br>' +
                         '<extra></extra>',
            showlegend=True
        ))
        
        # Add current point with label
        fig.add_trace(go.Scatter(
            x=[current_rs],
            y=[current_momentum],
            mode='markers+text',
            name=f'{symbol} (Current)',
            marker=dict(size=15, color=color, symbol='circle'),
            text=[symbol],
            textposition="top center",
            textfont=dict(size=10, color=color),
            hovertemplate=f'<b>{symbol}</b><br>' +
                         f'RS: {current_rs:.2f}<br>' +
                         f'Momentum: {current_momentum:.2f}<br>' +
                         f'Quadrant: {calculator.get_quadrant(current_rs, current_momentum)}<br>' +
                         '<extra></extra>',
            showlegend=False
        ))
    
    # Calculate symmetric range around center (100, 100)
    # The center point (100, 100) should always be exactly in the middle
    center_x = 100
    center_y = 100
    
    if x_min >= 200 or x_max <= 0:
        # No data - use default symmetric range
        x_range = 7  # Default range: 93 to 107 (7 units on each side)
        y_range = 7
    else:
        # Calculate maximum distance from center on each axis
        # Add reasonable padding (5% of data range, minimum 1.5 units)
        x_data_range = x_max - x_min
        y_data_range = y_max - y_min
        x_padding = max(x_data_range * 0.05, 1.5)
        y_padding = max(y_data_range * 0.05, 1.5)
        
        x_dist_from_center = max(abs(x_min - center_x), abs(x_max - center_x)) + x_padding
        y_dist_from_center = max(abs(y_min - center_y), abs(y_max - center_y)) + y_padding
        
        # Ensure minimum range for visibility
        x_range = max(x_dist_from_center, 7)
        y_range = max(y_dist_from_center, 7)
    
    # Calculate axis limits
    x_axis_min = center_x - x_range
    x_axis_max = center_x + x_range
    y_axis_min = center_y - y_range
    y_axis_max = center_y + y_range
    
    # Add quadrant backgrounds (stretched to corners based on calculated ranges)
    fig.add_shape(
        type="rect",
        x0=x_axis_min, y0=100, x1=center_x, y1=y_axis_max,
        fillcolor="#b1ebff",  # Light blue - Improving
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=center_x, y0=100, x1=x_axis_max, y1=y_axis_max,
        fillcolor="#bdffc9",  # Light green - Leading
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=center_x, y0=y_axis_min, x1=x_axis_max, y1=100,
        fillcolor="#fff7b8",  # Light yellow - Weakening
        layer="below",
        line_width=0,
    )
    fig.add_shape(
        type="rect",
        x0=x_axis_min, y0=y_axis_min, x1=center_x, y1=100,
        fillcolor="#ffb9c6",  # Light pink - Lagging
        layer="below",
        line_width=0,
    )
    
    # Add quadrant lines
    fig.add_hline(y=100, line_dash="dash", line_color="black", line_width=0.5)
    fig.add_vline(x=100, line_dash="dash", line_color="black", line_width=0.5)
    
    # Set symmetric ranges centered at (100, 100)
    fig.update_xaxes(
        title_text="RS Ratio",
        range=[x_axis_min, x_axis_max],
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    fig.update_yaxes(
        title_text="RS Momentum",
        range=[y_axis_min, y_axis_max],
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    
    # Add quadrant labels positioned within chart bounds (after axis ranges are set)
    # Position labels at 15% from edges, ensuring they're visible and bold
    label_x_offset = x_range * 0.15
    label_y_offset = y_range * 0.15
    min_offset = 1.0  # Minimum offset to ensure visibility
    
    label_x_left = max(center_x - x_range + max(label_x_offset, min_offset), center_x - x_range + 1.0)
    label_x_right = min(center_x + x_range - max(label_x_offset, min_offset), center_x + x_range - 1.0)
    label_y_bottom = max(center_y - y_range + max(label_y_offset, min_offset), center_y - y_range + 1.0)
    label_y_top = min(center_y + y_range - max(label_y_offset, min_offset), center_y + y_range - 1.0)
    
    fig.add_annotation(
        x=label_x_left, 
        y=label_y_top, 
        text="<b>Improving</b>", 
        showarrow=False, 
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_right, 
        y=label_y_top, 
        text="<b>Leading</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_right, 
        y=label_y_bottom, 
        text="<b>Weakening</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    fig.add_annotation(
        x=label_x_left, 
        y=label_y_bottom, 
        text="<b>Lagging</b>", 
        showarrow=False,
        font=dict(size=13, color="black", family="Arial Black"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
    
    # Update title with cutoff date if provided
    title_date = cutoff_date.strftime('%d %b %Y') if cutoff_date else datetime.now().strftime('%d %b %Y')
    fig.update_layout(
        title=f"RRG Chart - {st.session_state.get('benchmark_name', 'NIFTY 50')} ({st.session_state.get('timeframe', 'daily').upper()}) - {title_date}",
        height=600,
        hovermode='closest',
        template='plotly_white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig


def generate_chart():
    """Generate RRG chart based on current selections and settings"""
    # Get selected items ONLY from the active tab
    all_selected = []
    active_tab = st.session_state.get('active_tab', 'Index')
    
    # Only add items from the active tab
    if active_tab == "Index":
        for idx in st.session_state.selected_indices:
            token = idx.get("token")
            all_selected.append(("Index", idx["symbol"], idx["name"], token))
    elif active_tab == "Stock":
        for stock in st.session_state.selected_stocks:
            # Use .get() to handle missing token key gracefully
            token = stock.get("token")
            all_selected.append(("Stock", stock["symbol"], stock["name"], token))
    elif active_tab == "ETF":
        for etf in st.session_state.selected_etfs:
            token = etf.get("token")
            all_selected.append(("ETF", etf["symbol"], etf["name"], token))
    
    # Always return a chart (even if no items selected, will show quadrants only)
    # Initialize items_data as empty dict if no selections
    items_data = {}
    calculator = None
    benchmark_df = None
    
    # Get computation method
    use_standard_jdk = st.session_state.get('computation_method', 'Enhanced') == 'Standard JDK'
    timeframe = st.session_state.get('timeframe', 'weekly')
    
    # For Standard JDK, period is used for ROC calculation (taken from roc_shift slider)
    # For Enhanced, roc_shift is used for ROC calculation
    roc_shift = st.session_state.get('roc_shift', 10)
    if use_standard_jdk:
        # Standard JDK uses period for ROC calculation
        standard_period = roc_shift
    else:
        # Enhanced uses roc_shift for ROC calculation
        standard_period = st.session_state.get('roc_period', 20)  # Deprecated, kept for compatibility
    
    if not all_selected:
        # Return empty chart with just quadrants
        calculator = RRGCalculator(
            window=st.session_state.get('window', 14),
            period=standard_period,
            ema_span=14,  # Fixed in formula
            roc_shift=roc_shift,
            ema_roc_span=st.session_state.get('ema_roc_span', 14),
            use_standard_jdk=use_standard_jdk
        )
        fig = create_rrg_chart(items_data, None, calculator, tail_count=st.session_state.get('tail_count', 8))
        return fig, items_data, calculator
    
    # Check if loader needs to be reinitialized (timeframe changed)
    current_timeframe = st.session_state.get('timeframe', 'daily')
    
    needs_reinit = False
    if st.session_state.loader is None:
        needs_reinit = True
    else:
        # Check if timeframe changed
        loader_tf = getattr(st.session_state.loader, 'tf', None)
        if loader_tf != current_timeframe:
            needs_reinit = True
    
    # Reinitialize loader if needed
    if needs_reinit:
        if st.session_state.loader is not None:
            try:
                st.session_state.loader.close()
            except:
                pass
        
        loader = initialize_api_loader()
        if loader:
            st.session_state.loader = loader
        else:
            # Return empty chart if loader fails
            calculator = RRGCalculator(
                window=st.session_state.get('window', 14),  # Deprecated, kept for compatibility
                period=standard_period,
                ema_span=14,  # Deprecated, kept for compatibility
                roc_shift=roc_shift,
                ema_roc_span=st.session_state.get('ema_roc_span', 14),  # m: used for EMA_RS span, RS_Ratio rolling mean, and EMA_ROC span
                use_standard_jdk=use_standard_jdk
            )
            fig = create_rrg_chart({}, None, calculator, tail_count=st.session_state.get('tail_count', 8))
            return fig, {}, calculator
    
    # Get benchmark
    benchmark_symbol = BENCHMARKS.get(st.session_state.get('benchmark_name', 'NIFTY 50'), 'Nifty 50')
    benchmark_token = get_token(benchmark_symbol)
    
    if not benchmark_token:
        # Return empty chart if token not found
        calculator = RRGCalculator(
            window=st.session_state.get('window', 14),
            period=standard_period,
            ema_span=14,  # Fixed in formula
            roc_shift=roc_shift,
            ema_roc_span=st.session_state.get('ema_roc_span', 14),
            use_standard_jdk=use_standard_jdk
        )
        fig = create_rrg_chart({}, None, calculator, tail_count=st.session_state.get('tail_count', 8))
        return fig, {}, calculator
                
    # Get benchmark data
    try:
        benchmark_df = get_stock_data(st.session_state.loader, benchmark_symbol, benchmark_token)
        if benchmark_df is None or benchmark_df.empty:
            # Return empty chart instead of None
            calculator = RRGCalculator(
                window=st.session_state.get('window', 14),  # Deprecated, kept for compatibility
                period=standard_period,
                ema_span=14,  # Deprecated, kept for compatibility
                roc_shift=roc_shift,
                ema_roc_span=st.session_state.get('ema_roc_span', 14),  # m: used for EMA_RS span, RS_Ratio rolling mean, and EMA_ROC span
                use_standard_jdk=use_standard_jdk
            )
            fig = create_rrg_chart({}, None, calculator, tail_count=st.session_state.get('tail_count', 8))
            return fig, {}, calculator
    except Exception as e:
        # Return empty chart instead of None
        calculator = RRGCalculator(
            window=st.session_state.get('window', 14),
            period=standard_period,
            ema_span=14,  # Fixed in formula
            roc_shift=roc_shift,
            ema_roc_span=st.session_state.get('ema_roc_span', 14),
            use_standard_jdk=use_standard_jdk
        )
        fig = create_rrg_chart({}, None, calculator, tail_count=st.session_state.get('tail_count', 8))
        return fig, {}, calculator
                
    benchmark_closes = benchmark_df['Close']
                
    # Initialize calculator
    calculator = RRGCalculator(
        window=st.session_state.get('window', 14),
        period=standard_period,
        ema_span=14,  # Fixed in formula
        roc_shift=roc_shift,
        ema_roc_span=st.session_state.get('ema_roc_span', 14),
        use_standard_jdk=use_standard_jdk
    )
    
    # Process each selected item (only from active tab - already filtered)
    items_data = {}
    tail_count = st.session_state.get('tail_count', 8)
    
    for item_type, symbol, name, token in all_selected:
        # Ensure we have a valid token - try to fetch if missing or invalid
        # Token might be None, empty string, or string "None"
        if not token or str(token).strip() == '' or str(token).lower() == 'none':
            token = get_token(symbol)
            if not token:
                # Skip items without valid tokens
                continue
        
        # Get stock data
        item_df = get_stock_data(st.session_state.loader, symbol, token)
        if item_df is None or item_df.empty:
            continue
        
        item_closes = calculator.process_series(item_df['Close'])
        benchmark_processed = calculator.process_series(benchmark_closes)
        
        # Align indices
        common_dates = item_closes.index.intersection(benchmark_processed.index)
        window = st.session_state.get('window', 14)
        # For Standard JDK, use period; for Enhanced, use roc_shift
        if use_standard_jdk:
            min_period = standard_period
        else:
            min_period = roc_shift
        
        if len(common_dates) < window + min_period:
            continue
        
        item_aligned = item_closes.loc[common_dates]
        benchmark_aligned = benchmark_processed.loc[common_dates]
        
        # Calculate RS and Momentum
        try:
            rs_series = calculator.calculate_rs(item_aligned, benchmark_aligned)
            momentum_series = calculator.calculate_momentum(rs_series)
                    
            # Only store if we have valid data
            if len(rs_series) > 0 and len(momentum_series) > 0:
                items_data[symbol] = (rs_series, momentum_series, item_df)
                
                # FIX 3: Always update available_dates if we have new data, don't just check if empty
                if len(rs_series) > 0:
                    # Get all available dates from the series and normalize to date-only (no time component)
                    all_dates = sorted(set(rs_series.index.tolist() + momentum_series.index.tolist()))
                    # Normalize dates to date-only for consistent matching
                    all_dates = [pd.Timestamp(d).normalize().to_pydatetime() if isinstance(d, pd.Timestamp) else pd.Timestamp(d).normalize().to_pydatetime() for d in all_dates]
                    # Always update available_dates with dates from first item (or merge if multiple items)
                    if not st.session_state.available_dates:
                        st.session_state.available_dates = all_dates
                    else:
                        # Merge dates to ensure we have all available dates
                        existing_dates = set(st.session_state.available_dates)
                        new_dates = set(all_dates)
                        merged_dates = sorted(list(existing_dates | new_dates))
                        st.session_state.available_dates = merged_dates
        except Exception as e:
            # Skip items that fail calculation
            continue
    
    # Generate unique colors (even if items_data is empty, chart will still be created)
    if items_data:
        colors = generate_unique_colors(len(items_data))
        colors_map = {symbol: colors[i] for i, symbol in enumerate(items_data.keys())}
    else:
        colors_map = {}
    
    # Create chart (will show quadrants even if no items)
    fig = create_rrg_chart(
        items_data, 
        benchmark_df if items_data else None, 
        calculator, 
        tail_count=tail_count,
        colors_map=colors_map
    )
    
    return fig, items_data, calculator


def main():
    # Initialize default items will be called in middle pane before chart generation
    # This prevents double initialization and double chart generation
    
    # On very first load, ensure no stale cache is used and chart renders for defaults
    # Don't set is_initialized here - set it AFTER chart is generated to ensure first load detection works
    if not st.session_state.get("is_initialized", False):
        st.session_state.chart_cache_key = None
        st.session_state.cached_chart = None
        st.session_state.cached_items_data = None
        st.session_state.cached_calculator = None
    
    # Initialize loader (will be done in generate_chart if needed)
    
    # Three-column layout
    col_left, col_middle, col_right = st.columns([2, 5, 2])
    
    # LEFT PANE - Chart Settings
    with col_left:
        # Large heading for left pane
        st.markdown("<h1 style='font-size: 1.8em; margin-top: 0; margin-bottom: 0.8em; font-weight: bold;'>RRG Chart: Sectoral Rotation Analysis</h1>", unsafe_allow_html=True)
        
        st.markdown("<h4 style='font-size: 1.05em; margin-bottom: 0.3em;'>⚙️ Chart Settings</h4>", unsafe_allow_html=True)
        
        # Benchmark Selection
        benchmark_options = list(BENCHMARKS.keys())
        benchmark_name = st.selectbox(
            "Benchmark",
            benchmark_options,
            key="benchmark_name"
        )
        
        # Chart Settings
        timeframe_display = st.selectbox(
            "Timeframe",
            ["Daily", "Weekly", "Monthly"],
            index=1,  # Default to Weekly
            key="timeframe_display"
        )
        # Convert display value to lowercase for internal use and store in session_state
        timeframe = timeframe_display.lower() if timeframe_display else "weekly"
        previous_timeframe = st.session_state.get('previous_timeframe')
        st.session_state.timeframe = timeframe
        
        # Store timeframe change status before updating previous_timeframe
        timeframe_changed_flag = previous_timeframe is not None and previous_timeframe != timeframe
        st.session_state.timeframe_changed = timeframe_changed_flag
        
        # Clear loader when timeframe changes
        if timeframe_changed_flag:
            st.session_state.loader = None
            st.session_state.previous_timeframe = timeframe
        
        # Determine default tail count based on computation method
        if 'computation_method' not in st.session_state:
            st.session_state.computation_method = "Enhanced"
        
        if st.session_state.computation_method == "Standard JDK":
            default_tail_count = 4
        else:  # Enhanced
            default_tail_count = 8
        
        # Tail Count slider - use session state value if exists, otherwise use default
        # Don't set in session state before slider to avoid warning
        tail_count_value = st.session_state.get('tail_count', default_tail_count)
        tail_count = st.slider(
            "Tail Count",
            min_value=2,
            max_value=10,
            value=tail_count_value,
            step=1,
            key="tail_count"
        )
        
        # RRG Calculation Settings
        st.markdown("<h4 style='font-size: 1.05em; margin-bottom: 0.3em;'>⚙️ RRG Settings</h4>", unsafe_allow_html=True)
        
        # RRG Computation Method Selection - moved under RRG Settings
        # Use CSS to make radio buttons horizontal and prevent text wrapping
        st.markdown("""
        <style>
        div[data-testid="stRadio"] > div {
            flex-direction: row;
            display: flex;
            gap: 20px;
        }
        div[data-testid="stRadio"] > div > label {
            flex: 0 0 auto;
            white-space: nowrap;
            min-width: fit-content;
        }
        </style>
        """, unsafe_allow_html=True)
        
        computation_method = st.radio(
            "Computation Method",
            ["Enhanced", "Standard JDK"],
            index=0 if st.session_state.computation_method == "Enhanced" else 1,
            key="computation_method"
        )
        
        # Clear cache only when computation method actually changes (not on first load)
        previous_computation_method = st.session_state.get('previous_computation_method')
        if previous_computation_method is not None and previous_computation_method != computation_method:
            # Only clear cache if method actually changed (not on first initialization)
            st.session_state.chart_cache_key = None
            st.session_state.cached_chart = None
            st.session_state.cached_items_data = None
            st.session_state.cached_calculator = None
            # Clear precomputed charts cache when method changes
            # Get active_tab from session state
            active_tab_for_precompute = st.session_state.get('active_tab', 'Index')
            precomputed_charts_key = f"precomputed_charts_{active_tab_for_precompute.lower()}"
            if precomputed_charts_key in st.session_state:
                del st.session_state[precomputed_charts_key]
            # Note: We don't update tail_count here because the widget is already instantiated
            # The user can manually change the tail count if needed
            # The default tail count is set when the slider is created based on computation_method
        # Always update previous_computation_method to current value
        st.session_state.previous_computation_method = computation_method
        
        # Determine if Standard JDK is selected
        use_standard_jdk = computation_method == 'Standard JDK'
        
        # Set default values based on timeframe and computation method
        if use_standard_jdk:
            # Standard JDK defaults: m and k based on timeframe
            if timeframe == 'weekly':
                default_ema_roc_span = 14  # m
                default_roc_shift = 10  # k
            elif timeframe == 'daily':
                default_ema_roc_span = 20  # m
                default_roc_shift = 20  # k
            else:  # monthly
                default_ema_roc_span = 6  # m
                default_roc_shift = 3  # k
        else:
            # Enhanced defaults
            # m is fixed at 14 for all timeframes
            default_ema_roc_span = 14
            
            # k varies by timeframe: 20 (Daily), 10 (Weekly), 3 (Monthly)
            if timeframe == 'weekly':
                default_roc_shift = 10
            elif timeframe == 'daily':
                default_roc_shift = 20
            else:  # monthly
                default_roc_shift = 3
        
        # For both Enhanced and Standard JDK, always update session state based on current timeframe
        # This ensures sliders reflect the correct defaults when timeframe changes
        # Check if timeframe or computation method changed
        timeframe_changed = st.session_state.get('timeframe_changed', False)
        computation_method_changed = previous_computation_method is not None and previous_computation_method != computation_method
        
        # Always update session state to match defaults for current timeframe and computation method
        # For Enhanced: m stays at 14, but k changes with timeframe (20/10/3)
        # For Standard JDK: both m and k change with timeframe
        if use_standard_jdk:
            # For Standard JDK, update when timeframe or computation method changes
            if timeframe_changed or computation_method_changed:
                st.session_state.ema_roc_span = default_ema_roc_span
                st.session_state.roc_shift = default_roc_shift
            else:
                # Initialize if not exists
                if 'ema_roc_span' not in st.session_state:
                    st.session_state.ema_roc_span = default_ema_roc_span
                if 'roc_shift' not in st.session_state:
                    st.session_state.roc_shift = default_roc_shift
        else:
            # For Enhanced mode, always update to ensure k matches current timeframe
            # m is always 14, k changes with timeframe (20/10/3)
            st.session_state.ema_roc_span = default_ema_roc_span  # Always 14 for Enhanced
            st.session_state.roc_shift = default_roc_shift  # Changes with timeframe
        
        # Reset timeframe_changed flag after using it
        st.session_state.timeframe_changed = False
        
        # Get values from session state - sliders with key parameter will use these values
        # The slider widget will read from session state when key is provided
        ema_roc_span_value = st.session_state.get('ema_roc_span', default_ema_roc_span)
        roc_shift_value = st.session_state.get('roc_shift', default_roc_shift)
        
        ema_roc_span = st.slider(
            "EMA Window Period (m)",
            min_value=5,
            max_value=52,
            value=ema_roc_span_value,
            step=1,
            key="ema_roc_span",
            help="Window period: For Enhanced (EMA span), For Standard JDK (RS EMA period m)"
        )
        
        roc_shift = st.slider(
            "ROC Shift Period (k)",
            min_value=5,
            max_value=52,
            value=roc_shift_value,
            step=1,
            key="roc_shift",
            help="Period for ROC: Enhanced uses as shift(k), Standard JDK uses as ROC lookback period (k)"
        )
        
        # Keep window for backward compatibility (deprecated, now uses ema_roc_span)
        window = st.session_state.get('window', default_ema_roc_span)
        
        # Keep roc_period for backward compatibility (deprecated)
        default_roc = 52 if timeframe == "weekly" else 20
        roc_period = st.session_state.get('roc_period', default_roc)
    
    # MIDDLE PANE - RRG Chart
    with col_middle:
        # Create chart placeholder to avoid flickering during animation
        if 'chart_placeholder' not in st.session_state:
            st.session_state.chart_placeholder = st.empty()
        
        # Always generate chart (auto-refresh) - chart will always be visible
        active_tab = st.session_state.get('active_tab', 'Index')
        
        # Initialize default items if needed (only called once here to prevent double generation)
        prev_selected_count = len(st.session_state.get('selected_indices', [])) if active_tab == "Index" else (
            len(st.session_state.get('selected_stocks', [])) if active_tab == "Stock" else 
            len(st.session_state.get('selected_etfs', []))
        )
        initialize_default_items()
        new_selected_count = len(st.session_state.get('selected_indices', [])) if active_tab == "Index" else (
            len(st.session_state.get('selected_stocks', [])) if active_tab == "Stock" else 
            len(st.session_state.get('selected_etfs', []))
        )
        
        # If items were just initialized, clear cache to force regeneration
        # Use a flag to prevent clearing cache multiple times in the same run
        initialization_key = f"items_initialized_{active_tab}_{new_selected_count}"
        if new_selected_count > prev_selected_count:
            if st.session_state.get(initialization_key) != new_selected_count:
                st.session_state.chart_cache_key = None
                st.session_state.cached_chart = None
                st.session_state.cached_items_data = None
                st.session_state.cached_calculator = None
                st.session_state[initialization_key] = new_selected_count
        
        # Create a cache key based on all factors that affect the chart
        # This prevents regeneration when just searching (not selecting)
        def get_chart_cache_key():
            active_tab = st.session_state.get('active_tab', 'Index')
            # Get selected items for active tab only
            if active_tab == "Index":
                selected_items = tuple(sorted([idx['symbol'] for idx in st.session_state.selected_indices]))
            elif active_tab == "Stock":
                selected_items = tuple(sorted([stock['symbol'] for stock in st.session_state.selected_stocks]))
            else:  # ETF
                selected_items = tuple(sorted([etf['symbol'] for etf in st.session_state.selected_etfs]))
            
            # NOTE: cutoff_date is NOT included in cache key
            # We use precomputed charts for different dates, so cutoff_date changes don't trigger regeneration
            # cutoff_date only affects which precomputed chart to display
            
            return (
                active_tab,
                selected_items,
                st.session_state.get('benchmark_name', 'NIFTY 50'),
                st.session_state.get('timeframe', 'weekly'),
                st.session_state.get('tail_count', 8),
                st.session_state.get('window', 14),
                st.session_state.get('roc_shift', 10),
                st.session_state.get('ema_roc_span', 14),
                st.session_state.get('computation_method', 'Enhanced')  # Include computation method in cache key
                # cutoff_date is NOT included - we use precomputed charts for different dates
            )
        
        current_cache_key = get_chart_cache_key()
        
        # Only regenerate chart if cache key changed (selections or settings changed)
        # Also regenerate if items were just initialized (new items added) or on first load
        items_just_initialized = new_selected_count > prev_selected_count
        is_first_load = not st.session_state.get("is_initialized", False)
        has_items_but_no_chart = (new_selected_count > 0 and 
                                  (st.session_state.cached_chart is None or 
                                   st.session_state.chart_cache_key is None))
        
        # Force regeneration on first load if we have items, or if cache key doesn't match, or if chart is missing
        # Also handle case where both cache keys are None (first load) - they match but we still need to generate
        cache_keys_match = (st.session_state.chart_cache_key == current_cache_key and 
                           st.session_state.chart_cache_key is not None)
        
        if (not cache_keys_match or 
            st.session_state.cached_chart is None or
            items_just_initialized or
            has_items_but_no_chart or
            (is_first_load and new_selected_count > 0)):
            # Preserve available_dates temporarily during regeneration
            previous_available_dates = st.session_state.get('available_dates', [])
            
            # Reset animation state when chart is regenerated (but preserve available_dates)
            # Don't clear available_dates - it will be repopulated by generate_chart() if needed
            # Only clear if we're sure new data will be available
            st.session_state.animation_date_index = None
            st.session_state.is_animating = False
            
            with st.spinner(f"Generating RRG chart for {active_tab}..."):
                fig, items_data, calculator = generate_chart()
            
            # If available_dates wasn't populated by generate_chart(), restore previous dates
            # This ensures slider always has dates to work with
            if not st.session_state.available_dates and previous_available_dates:
                st.session_state.available_dates = previous_available_dates
            # Also try to extract from items_data if still empty
            elif not st.session_state.available_dates and items_data:
                for symbol, (rs_series, momentum_series, df) in items_data.items():
                    if len(rs_series) > 0:
                        all_dates = sorted(set(rs_series.index.tolist() + momentum_series.index.tolist()))
                        all_dates = [pd.Timestamp(d).to_pydatetime() if isinstance(d, pd.Timestamp) else d for d in all_dates]
                        st.session_state.available_dates = all_dates
                        break
            
            # Cache the chart
            st.session_state.cached_chart = fig
            st.session_state.cached_items_data = items_data
            st.session_state.cached_calculator = calculator
            st.session_state.chart_cache_key = current_cache_key
            
            # Mark as initialized AFTER chart is successfully generated
            # This ensures first load detection works correctly
            if is_first_load:
                st.session_state.is_initialized = True
        else:
            # Use cached chart
            fig = st.session_state.cached_chart
            items_data = st.session_state.cached_items_data
            calculator = st.session_state.cached_calculator
            
            # FIX: Always extract dates from cached items_data to ensure synchronization
            if items_data:
                # Extract dates from cached items_data
                for symbol, (rs_series, momentum_series, df) in items_data.items():
                    if len(rs_series) > 0:
                        all_dates = sorted(set(rs_series.index.tolist() + momentum_series.index.tolist()))
                        all_dates = [pd.Timestamp(d).to_pydatetime() if isinstance(d, pd.Timestamp) else d for d in all_dates]
                        # Always update available_dates with dates from cached data
                        st.session_state.available_dates = all_dates
                        break
        
        # Animation using Plotly's built-in frames
        available_dates = st.session_state.get('available_dates', [])
        
        # Get per-tab animation state
        active_tab = st.session_state.get('active_tab', 'Index')
        if active_tab == "Index":
            animation_key = "use_animation_index"
        elif active_tab == "Stock":
            animation_key = "use_animation_stock"
        else:  # ETF
            animation_key = "use_animation_etf"
        
        # Initialize animation state for this tab if not exists
        if animation_key not in st.session_state:
            st.session_state[animation_key] = False
        
        # FIX 1: Always extract dates from items_data and update available_dates
        # This ensures dates are always synchronized with current items_data
        if items_data:
            extracted_dates = []
            for symbol, (rs_series, momentum_series, df) in items_data.items():
                if len(rs_series) > 0:
                    # Normalize dates to date-only (no time component) for consistent matching
                    all_dates = sorted(set(rs_series.index.tolist() + momentum_series.index.tolist()))
                    all_dates = [pd.Timestamp(d).normalize().to_pydatetime() if isinstance(d, pd.Timestamp) else pd.Timestamp(d).normalize().to_pydatetime() for d in all_dates]
                    extracted_dates = all_dates
                    break
            
            # ALWAYS update available_dates if we have extracted dates from items_data
            # This ensures dates are always synchronized with current data
            if extracted_dates:
                st.session_state.available_dates = extracted_dates
                available_dates = extracted_dates
        
        # Initialize cutoff_date key for this tab
        cutoff_date_key = f"cutoff_date_{active_tab.lower()}"
        if cutoff_date_key not in st.session_state:
            st.session_state[cutoff_date_key] = None
        
        # Get per-tab animation state BEFORE chart creation
        active_tab_for_animation = st.session_state.get('active_tab', 'Index')
        if active_tab_for_animation == "Index":
            animation_key = "use_animation_index"
        elif active_tab_for_animation == "Stock":
            animation_key = "use_animation_stock"
        else:  # ETF
            animation_key = "use_animation_etf"
        
        # Initialize animation state for this tab if not exists
        if animation_key not in st.session_state:
            st.session_state[animation_key] = False
        
        # Get use_animation value BEFORE chart creation (needed for chart type decision)
        # Create the checkbox here so it's available for chart creation decision
        use_animation = st.checkbox("Enable Animation", value=st.session_state.get(animation_key, False), key=animation_key)
        
        # Generate colors map early so it's available for precomputation
        colors = generate_unique_colors(len(items_data)) if items_data else []
        colors_map = {symbol: colors[i] for i, symbol in enumerate(items_data.keys())} if items_data else {}
        
        # Time Period slider - positioned BEFORE chart generation to update cutoff_date first
        cutoff_date = None
        if available_dates and items_data:
            # Filter available dates based on timeframe for slider
            timeframe = st.session_state.get('timeframe', 'daily')
            if timeframe == 'daily':
                max_days = 180  # 6 months for daily charts
            elif timeframe == 'weekly':
                max_days = 365  # 1 year for weekly charts
            else:  # monthly
                max_days = 2190  # 6 years for monthly charts
            
            # Filter dates based on timeframe
            filtered_dates = []
            if available_dates:
                latest_date = available_dates[-1]
                if isinstance(latest_date, pd.Timestamp):
                    latest_date = latest_date.to_pydatetime()
                earliest_allowed = latest_date - timedelta(days=max_days)
                
                for d in available_dates:
                    d_dt = pd.Timestamp(d).to_pydatetime() if isinstance(d, pd.Timestamp) else d
                    if d_dt >= earliest_allowed:
                        filtered_dates.append(d_dt)
            
            if not filtered_dates and available_dates:
                filtered_dates = available_dates
            
            # Create slider for time period selection
            if filtered_dates:
                # Initialize slider index if not set
                slider_index_key = f"time_period_slider_index_{active_tab.lower()}"
                if slider_index_key not in st.session_state:
                    st.session_state[slider_index_key] = len(filtered_dates) - 1
                
                # Ensure index is within bounds
                max_index = len(filtered_dates) - 1
                if st.session_state[slider_index_key] > max_index:
                    st.session_state[slider_index_key] = max_index
                elif st.session_state[slider_index_key] < 0:
                    st.session_state[slider_index_key] = 0
                
                # Create date labels for slider
                date_labels = [d.strftime('%d %b %Y') for d in filtered_dates]
                
                # Precompute charts for all dates if not already done
                precomputed_charts_key = f"precomputed_charts_{active_tab.lower()}"
                precomputed_cache_key = f"precomputed_cache_key_{active_tab.lower()}"
                
                # Check if we need to precompute (items_data changed, or not yet computed)
                current_precompute_key = (
                    tuple(sorted(items_data.keys())) if items_data else (),
                    st.session_state.get('tail_count', 8),
                    st.session_state.get('computation_method', 'Enhanced')
                )
                
                needs_precompute = (
                    precomputed_charts_key not in st.session_state or
                    st.session_state.get(precomputed_cache_key) != current_precompute_key
                )
                
                # Store precomputation task - will be done after chart is displayed (non-blocking)
                if needs_precompute and items_data and calculator:
                    st.session_state['_pending_precompute'] = {
                        'items_data': items_data,
                        'calculator': calculator,
                        'tail_count': st.session_state.get('tail_count', 8),
                        'colors_map': colors_map,
                        'filtered_dates': filtered_dates,
                        'precomputed_charts_key': precomputed_charts_key,
                        'precomputed_cache_key': precomputed_cache_key,
                        'current_precompute_key': current_precompute_key
                    }
                
                # Time Period slider
                selected_index = st.select_slider(
                    "Time Period",
                    options=list(range(len(filtered_dates))),
                    value=st.session_state[slider_index_key],
                    format_func=lambda x: date_labels[x] if x < len(date_labels) else "",
                    key=f"time_period_slider_{active_tab.lower()}"
                )
                
                # Update session state and cutoff_date
                st.session_state[slider_index_key] = selected_index
                if selected_index < len(filtered_dates):
                    selected_date = filtered_dates[selected_index]
                    # Normalize the date to remove time component for exact matching
                    if isinstance(selected_date, pd.Timestamp):
                        selected_date = selected_date.normalize()
                    else:
                        selected_date = pd.Timestamp(selected_date).normalize()
                    st.session_state[cutoff_date_key] = selected_date
                    cutoff_date = selected_date
                else:
                    # Use stored cutoff_date if slider index is invalid
                    cutoff_date = st.session_state.get(cutoff_date_key, None)
        else:
            # No slider available, use stored cutoff_date or None
            cutoff_date = st.session_state.get(cutoff_date_key, None)
        
        # Create chart based on animation state
        if available_dates and items_data and use_animation:
            # Create animated chart with Plotly frames
            tail_count = st.session_state.get('tail_count', 8)
            
            # Filter available dates based on timeframe for animation
            timeframe = st.session_state.get('timeframe', 'daily')
            if timeframe == 'daily':
                max_days = 180  # 6 months for daily charts
            elif timeframe == 'weekly':
                max_days = 365  # 1 year for weekly charts
            else:  # monthly
                max_days = 2190  # 6 years for monthly charts
            
            filtered_available_dates = []
            if available_dates:
                latest_date = available_dates[-1]
                if isinstance(latest_date, pd.Timestamp):
                    latest_date = latest_date.to_pydatetime()
                earliest_allowed = latest_date - timedelta(days=max_days)
                
                for d in available_dates:
                    d_dt = pd.Timestamp(d).to_pydatetime() if isinstance(d, pd.Timestamp) else d
                    if d_dt >= earliest_allowed:
                        filtered_available_dates.append(d_dt)
            
            if not filtered_available_dates and available_dates:
                filtered_available_dates = available_dates
            
            with st.spinner("Preparing animation frames..."):
                fig = create_rrg_chart_with_animation(
                    items_data,
                    calculator,
                    tail_count=tail_count,
                    colors_map=colors_map,
                    filtered_dates=filtered_available_dates
                )
        else:
            # Create static chart with cutoff date
            # Try to use precomputed chart if available
            precomputed_charts_key = f"precomputed_charts_{active_tab.lower()}"
            if cutoff_date and precomputed_charts_key in st.session_state:
                # Normalize cutoff_date for lookup
                if isinstance(cutoff_date, pd.Timestamp):
                    cutoff_key = cutoff_date.normalize()
                else:
                    cutoff_key = pd.Timestamp(cutoff_date).normalize()
                
                precomputed_charts = st.session_state[precomputed_charts_key]
                if cutoff_key in precomputed_charts:
                    # Use precomputed chart - instant update!
                    fig = precomputed_charts[cutoff_key]
                else:
                    # Fallback to generating chart if precomputed not available
                    fig = create_rrg_chart(
                        items_data,
                        None,
                        calculator,
                        tail_count=st.session_state.get('tail_count', 8),
                        colors_map=colors_map,
                        cutoff_date=cutoff_date
                    )
            else:
                # No precomputed charts available, generate normally
                fig = create_rrg_chart(
                    items_data,
                    None,
                    calculator,
                    tail_count=st.session_state.get('tail_count', 8),
                    colors_map=colors_map,
                    cutoff_date=cutoff_date
                )
        
        # Always display chart (even if empty, shows quadrants)
        if fig:
            # Use placeholder to update chart smoothly
            with st.session_state.chart_placeholder.container():
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True}, key="rrg_chart")
            st.session_state.current_items_data = items_data
            st.session_state.current_calculator = calculator
        
        # Note: Enable Animation checkbox is already created above (before chart creation)
        # It's displayed there to ensure it's always visible and available for chart type decision
        
        # Do precomputation after chart is displayed (non-blocking for initial display)
        if '_pending_precompute' in st.session_state:
            precompute_task = st.session_state['_pending_precompute']
            # Only precompute if we still need it (cache key hasn't changed)
            precomputed_charts_key = precompute_task['precomputed_charts_key']
            precomputed_cache_key = precompute_task['precomputed_cache_key']
            current_precompute_key = precompute_task['current_precompute_key']
            
            if (precomputed_charts_key not in st.session_state or
                st.session_state.get(precomputed_cache_key) != current_precompute_key):
                # Precompute charts for all dates (this happens after chart is displayed)
                with st.spinner("Precomputing charts for all time periods..."):
                    precomputed_charts = precompute_charts_for_dates(
                        precompute_task['items_data'],
                        precompute_task['calculator'],
                        precompute_task['tail_count'],
                        precompute_task['colors_map'],
                        precompute_task['filtered_dates']
                    )
                    st.session_state[precomputed_charts_key] = precomputed_charts
                    st.session_state[precomputed_cache_key] = current_precompute_key
            
            # Clear the pending task
            del st.session_state['_pending_precompute']
        
        # Fallback: create empty chart with quadrants if no fig
        if not fig:
            # Get computation method for fallback calculator
            use_standard_jdk_fallback = st.session_state.get('computation_method', 'Enhanced') == 'Standard JDK'
            roc_shift_fallback = st.session_state.get('roc_shift', 10)
            if use_standard_jdk_fallback:
                standard_period_fallback = roc_shift_fallback
            else:
                standard_period_fallback = st.session_state.get('roc_period', 20)  # Deprecated, kept for compatibility
            
            calculator = RRGCalculator(
                window=st.session_state.get('window', 14),  # Deprecated, kept for compatibility
                period=standard_period_fallback,
                ema_span=14,  # Deprecated, kept for compatibility
                roc_shift=roc_shift_fallback,
                ema_roc_span=st.session_state.get('ema_roc_span', 14),  # m: used for EMA_RS span, RS_Ratio rolling mean, and EMA_ROC span
                use_standard_jdk=use_standard_jdk_fallback
            )
            fig = create_rrg_chart({}, None, calculator, tail_count=st.session_state.get('tail_count', 8))
            with st.session_state.chart_placeholder.container():
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True}, key="rrg_empty_chart")
    
    # RIGHT PANE - Selection Buttons and Lists
    with col_right:
        # Three buttons for Index, Stock, ETF (no header to save space)
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        
        with btn_col1:
            btn_type = "primary" if st.session_state.active_tab == "Index" else "secondary"
            if st.button("Index", key="btn_index", use_container_width=True, type=btn_type):
                st.session_state.active_tab = "Index"
                st.rerun()
        
        with btn_col2:
            btn_type = "primary" if st.session_state.active_tab == "Stock" else "secondary"
            if st.button("Stock", key="btn_stock", use_container_width=True, type=btn_type):
                st.session_state.active_tab = "Stock"
                st.rerun()
        
        with btn_col3:
            btn_type = "primary" if st.session_state.active_tab == "ETF" else "secondary"
            if st.button("ETF", key="btn_etf", use_container_width=True, type=btn_type):
                st.session_state.active_tab = "ETF"
                # Force initialization of default ETFs before chart generation
                # This ensures ETFs are populated before chart is generated
                try:
                    if not st.session_state.selected_etfs:
                        all_etfs = get_etfs()
                        for default_symbol in DEFAULT_ETFS:
                            etf_item = next((e for e in all_etfs if e['symbol'] == default_symbol), None)
                            if etf_item and not any(x['symbol'] == etf_item['symbol'] for x in st.session_state.selected_etfs):
                                st.session_state.selected_etfs.append(etf_item)
                except Exception:
                    pass
                # Clear cache to force chart regeneration when switching to ETF tab
                st.session_state.chart_cache_key = None
                st.session_state.cached_chart = None
                st.session_state.cached_items_data = None
                st.session_state.cached_calculator = None
                st.rerun()
        
        # Search box and results based on active tab (removed divider to save space)
        if st.session_state.active_tab == "Index":
            # Search box for indices
            st.markdown("<h4 style='font-size: 1.0em; margin-bottom: 0.2em;'>Search Indices</h4>", unsafe_allow_html=True)
            search_query = st.text_input("", key="search_index", placeholder="e.g., Nifty Bank, Nifty IT, Nifty 50", label_visibility="collapsed")
            
            if search_query and len(search_query.strip()) >= 1:
                # Search and filter indices
                try:
                    with st.spinner("Searching indices..."):
                        results = search_indices(search_query.strip(), limit=100)
                    
                    if results:
                        # Create options for multiselect
                        index_options = {f"{idx['name']} ({idx['symbol']})": idx for idx in results}
                        st.markdown("<h4 style='font-size: 1.0em; margin-bottom: 0.2em;'>Select Indices</h4>", unsafe_allow_html=True)
                        selected_index_keys = st.multiselect(
                            "",
                            options=list(index_options.keys()),
                            key="multiselect_indices_search",
                            label_visibility="collapsed"
                        )
                        
                        # Update selected indices
                        if selected_index_keys:
                            for key in selected_index_keys:
                                idx_item = index_options[key]
                                if not any(x['symbol'] == idx_item['symbol'] for x in st.session_state.selected_indices):
                                    st.session_state.selected_indices.append(idx_item)
                                    st.rerun()
                    else:
                        st.info("No indices found. Try a different search term (e.g., Nifty Bank, Nifty IT).")
                except Exception as e:
                    st.error(f"Error searching indices: {str(e)}")
            else:
                # Show all indices if no search query
                all_indices = get_indices()
                index_options = {f"{idx['name']} ({idx['symbol']})": idx for idx in all_indices}
                
                # Multi-select dropdown
                st.markdown("<h4 style='font-size: 1.0em; margin-bottom: 0.2em;'>Select Indices</h4>", unsafe_allow_html=True)
                selected_index_keys = st.multiselect(
                    "",
                    options=list(index_options.keys()),
                    default=[f"{idx['name']} ({idx['symbol']})" for idx in st.session_state.selected_indices 
                            if f"{idx['name']} ({idx['symbol']})" in index_options],
                    key="multiselect_indices",
                    label_visibility="collapsed"
                )
                
                # Update selected indices based on multiselect
                current_selected_symbols = {idx['symbol'] for idx in st.session_state.selected_indices}
                new_selected_symbols = {index_options[key]['symbol'] for key in selected_index_keys}
                
                # Check if selection changed
                selection_changed = False
                
                # Add new selections
                for key in selected_index_keys:
                    idx_item = index_options[key]
                    if idx_item['symbol'] not in current_selected_symbols:
                        st.session_state.selected_indices.append(idx_item)
                        selection_changed = True
                
                # Remove deselected items
                new_list = [
                    idx for idx in st.session_state.selected_indices 
                    if idx['symbol'] in new_selected_symbols
                ]
                if len(new_list) != len(st.session_state.selected_indices):
                    selection_changed = True
                st.session_state.selected_indices = new_list
                
                if selection_changed:
                    st.rerun()
        
        elif st.session_state.active_tab == "Stock":
            search_query = st.text_input("Search Stocks", key="search_stock", placeholder="e.g., HDFCBANK, RELIANCE, TCS")
            
            # Tip text below Search Stocks
            st.info("💡 Enter a search term to find stocks")
            
            # Sector Selection Combo Box - always displayed, comes after tip text
            # Get all sectors and sub-sectors
            all_sectors = list(SECTORS.keys())
            all_sub_sectors = list(SUB_SECTORS.keys()) if SUB_SECTORS else []
            sector_options = sorted(all_sectors + all_sub_sectors)
            
            selected_sector = st.selectbox(
                "Select Sector",
                options=[""] + sector_options,
                key="sector_selectbox",
                format_func=lambda x: f"📁 {x}" if x else "Select a sector..."
            )
            
            # Search query handling with Select Stocks multiselect - comes after Select Sector
            if search_query and len(search_query.strip()) >= 1:  # Require at least 1 character
                try:
                    with st.spinner("Searching stocks..."):
                        # Search stocks with improved matching
                        results = search_stocks(search_query.strip(), limit=100)
                    
                    if results:
                        # Create options for multiselect
                        stock_options = {f"{stock['name']} ({stock['symbol']})": stock for stock in results}
                        selected_stock_keys = st.multiselect(
                            "Select Stocks",
                            options=list(stock_options.keys()),
                            key="multiselect_stocks_search"
                        )
                        
                        # Update selected stocks - add to existing list (don't clear)
                        # Silently add to Selected Items without showing additional UI elements
                        if selected_stock_keys:
                            stocks_added_from_search = False
                            for key in selected_stock_keys:
                                stock_item = stock_options[key]
                                if not any(x['symbol'] == stock_item['symbol'] for x in st.session_state.selected_stocks):
                                    st.session_state.selected_stocks.append(stock_item)
                                    stocks_added_from_search = True
                            
                            # Clear cache to force chart regeneration when stocks are added
                            if stocks_added_from_search:
                                st.session_state.chart_cache_key = None
                                st.session_state.cached_chart = None
                                st.session_state.cached_items_data = None
                                st.session_state.cached_calculator = None
                                # Clear precomputed charts cache
                                active_tab_for_search = st.session_state.get('active_tab', 'Stock')
                                precomputed_charts_key = f"precomputed_charts_{active_tab_for_search.lower()}"
                                if precomputed_charts_key in st.session_state:
                                    del st.session_state[precomputed_charts_key]
                                st.rerun()
                    else:
                        # Provide helpful message and try to diagnose
                        st.warning(f"No stocks found for '{search_query}'")
                        
                        # Try to check if scrip master is loading and show sample stocks
                        try:
                            from scrip_master_search import fetch_scrip_master, get_stocks
                            scrip_data = fetch_scrip_master()
                            if scrip_data is None:
                                st.error("⚠️ Unable to load stock data. Please check your internet connection.")
                            else:
                                # Count total stocks
                                nse_stocks = [x for x in scrip_data if x.get('exch_seg') == 'NSE' and x.get('instrumenttype') == 'EQ' and x.get('symbol', '').endswith('-EQ')]
                                st.info(f"💡 Database has {len(nse_stocks)} stocks available.")
                                
                                # Show some sample stocks to help user
                                all_stocks = get_stocks()
                                if all_stocks:
                                    st.write("**Sample stocks in database:**")
                                    sample_stocks = all_stocks[:10]  # Show first 10
                                    for stock in sample_stocks:
                                        st.write(f"- {stock['name']} ({stock['symbol']})")
                                
                                st.markdown("""
                                **Try searching by:**
                                - **Symbol**: HDFCBANK, TCS, RELIANCE, INFY, ICICIBANK
                                - **Name**: HDFC Bank, Tata Consultancy, Reliance Industries  
                                - **Partial match**: HDFC, TATA, REL, INF
                                """)
                        except Exception as e:
                            st.error(f"Error checking stock database: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"Error searching stocks: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
            elif search_query and len(search_query.strip()) == 0:
                st.info("Please enter a search term.")
            
            # Handle sector selection - selected_sector is already defined above (always displayed)
            if selected_sector and selected_sector != "":
                # Check if this sector was just processed to avoid duplicate processing
                last_processed_sector = st.session_state.get('last_processed_sector', None)
                if selected_sector != last_processed_sector:
                    with st.spinner(f"Adding stocks from {selected_sector}..."):
                        # Clear existing stocks first when a sector is selected
                        st.session_state.selected_stocks = []
                        
                        stocks_added = 0
                        sector_symbols = []
                        
                        # Check if it's a main sector or sub-sector
                        if selected_sector in SECTORS:
                            sector_symbols = SECTORS[selected_sector]
                        elif SUB_SECTORS and selected_sector in SUB_SECTORS:
                            sector_symbols = SUB_SECTORS[selected_sector]
                        
                        # Add stocks from the sector - create stock items directly from symbols
                        for symbol in sector_symbols:
                            # Try to get stock info from scrip master first
                            # Try with original symbol format first (with -EQ if present)
                            stock_item = get_item_by_symbol(symbol)
                            
                            # If not found with original format, try without -EQ suffix
                            if not stock_item and symbol.endswith('-EQ'):
                                symbol_clean = symbol.replace('-EQ', '')
                                stock_item = get_item_by_symbol(symbol_clean)
                            
                            # If still not found, create a basic stock item from the symbol
                            if not stock_item:
                                # Try to get token using original symbol format first
                                token = get_token(symbol)
                                # If token not found, try without -EQ
                                if not token and symbol.endswith('-EQ'):
                                    symbol_clean = symbol.replace('-EQ', '')
                                    token = get_token(symbol_clean)
                                
                                # Use the original symbol format (with -EQ if it was there)
                                # This ensures it matches the scrip master format
                                stock_item = {
                                    'symbol': symbol,  # Keep original format (e.g., "HDFCBANK-EQ")
                                    'name': symbol.replace('-EQ', '').replace('-', ' ').title(),
                                    'exch_seg': 'NSE',
                                    'instrumenttype': 'EQ',
                                    'token': token if token else None
                                }
                            else:
                                # Ensure token exists in stock_item, fetch if missing
                                if 'token' not in stock_item or not stock_item.get('token'):
                                    # Try with the symbol from stock_item first, then original symbol
                                    token = get_token(stock_item.get('symbol', symbol))
                                    if not token:
                                        token = get_token(symbol)
                                    if token:
                                        stock_item['token'] = token
                            
                            # Add stock to selected stocks (no need to check duplicates since we cleared the list)
                            if stock_item:
                                st.session_state.selected_stocks.append(stock_item)
                                stocks_added += 1
                        
                        if stocks_added > 0:
                            st.success(f"✅ Added {stocks_added} stocks from {selected_sector}")
                            # Mark this sector as processed
                            st.session_state.last_processed_sector = selected_sector
                            # Clear cache to force chart regeneration
                            st.session_state.chart_cache_key = None
                            st.session_state.cached_chart = None
                            st.session_state.cached_items_data = None
                            st.session_state.cached_calculator = None
                            # Clear precomputed charts cache
                            active_tab_for_sector = st.session_state.get('active_tab', 'Stock')
                            precomputed_charts_key = f"precomputed_charts_{active_tab_for_sector.lower()}"
                            if precomputed_charts_key in st.session_state:
                                del st.session_state[precomputed_charts_key]
                            st.rerun()
                        else:
                            st.info(f"No stocks found for {selected_sector}")
                            st.session_state.last_processed_sector = selected_sector
                elif selected_sector == last_processed_sector:
                    # Sector was already processed, don't show message again
                    pass
        
        elif st.session_state.active_tab == "ETF":
            # Search box for ETFs
            search_query = st.text_input("Search ETFs", key="search_etf", placeholder="e.g., NIFTYBEES, GOLDBEES, BANKBEES")
            
            if search_query and len(search_query.strip()) >= 1:
                # Search and filter ETFs
                try:
                    with st.spinner("Searching ETFs..."):
                        results = search_etfs(search_query.strip(), limit=100)
                    
                    if results:
                        # Create options for multiselect
                        etf_options = {f"{etf['name']} ({etf['symbol']})": etf for etf in results}
                        selected_etf_keys = st.multiselect(
                            "Select ETFs",
                            options=list(etf_options.keys()),
                            key="multiselect_etfs_search"
                        )
                        
                        # Update selected ETFs
                        if selected_etf_keys:
                            for key in selected_etf_keys:
                                etf_item = etf_options[key]
                                if not any(x['symbol'] == etf_item['symbol'] for x in st.session_state.selected_etfs):
                                    st.session_state.selected_etfs.append(etf_item)
                                    st.rerun()
                    else:
                        st.info("No ETFs found. Try a different search term (e.g., NIFTYBEES, GOLDBEES, BANKBEES).")
                except Exception as e:
                    st.error(f"Error searching ETFs: {str(e)}")
            else:
                # Show all ETFs if no search query
                all_etfs = get_etfs()
                etf_options = {f"{etf['name']} ({etf['symbol']})": etf for etf in all_etfs}
                
                # Multi-select dropdown
                selected_etf_keys = st.multiselect(
                    "Select ETFs",
                    options=list(etf_options.keys()),
                    default=[f"{etf['name']} ({etf['symbol']})" for etf in st.session_state.selected_etfs 
                            if f"{etf['name']} ({etf['symbol']})" in etf_options],
                    key="multiselect_etfs"
                )
                
                # Update selected ETFs based on multiselect
                current_selected_symbols = {etf['symbol'] for etf in st.session_state.selected_etfs}
                new_selected_symbols = {etf_options[key]['symbol'] for key in selected_etf_keys}
                
                # Check if selection changed
                selection_changed = False
                
                # Add new selections
                for key in selected_etf_keys:
                    etf_item = etf_options[key]
                    if etf_item['symbol'] not in current_selected_symbols:
                        st.session_state.selected_etfs.append(etf_item)
                        selection_changed = True
                
                # Remove deselected items
                new_list = [
                    etf for etf in st.session_state.selected_etfs 
                    if etf['symbol'] in new_selected_symbols
                ]
                if len(new_list) != len(st.session_state.selected_etfs):
                    selection_changed = True
                st.session_state.selected_etfs = new_list
                
                if selection_changed:
                    st.rerun()
        
        # Display selected items (only for active tab) - scrollable container (removed divider to save space)
        st.markdown("<h4 style='font-size: 1.0em; margin-bottom: 0.3em;'>Selected Items</h4>", unsafe_allow_html=True)
        
        # Use Streamlit's native scrollable container with fixed height
        max_height = 300  # pixels
        
        if st.session_state.active_tab == "Index":
            if st.session_state.selected_indices:
                # Use Streamlit container with fixed height for scrolling
                with st.container(height=max_height, border=True):
                    for idx in st.session_state.selected_indices:
                        col_name, col_btn = st.columns([3, 1])
                        with col_name:
                            st.write(f"• {idx['name']} ({idx['symbol']})")
                        with col_btn:
                            if st.button("❌", key=f"rm_idx_{idx['symbol']}"):
                                st.session_state.selected_indices.remove(idx)
                                st.rerun()
            else:
                st.info("No indices selected")
        
        elif st.session_state.active_tab == "Stock":
            if st.session_state.selected_stocks:
                # Use Streamlit container with fixed height for scrolling
                with st.container(height=max_height, border=True):
                    for stock in st.session_state.selected_stocks:
                        col_name, col_btn = st.columns([3, 1])
                        with col_name:
                            st.write(f"• {stock['name']} ({stock['symbol']})")
                        with col_btn:
                            if st.button("❌", key=f"rm_stock_{stock['symbol']}"):
                                st.session_state.selected_stocks.remove(stock)
                                st.rerun()
            else:
                st.info("No stocks selected")
        
        elif st.session_state.active_tab == "ETF":
            if st.session_state.selected_etfs:
                # Use Streamlit container with fixed height for scrolling
                with st.container(height=max_height, border=True):
                    for etf in st.session_state.selected_etfs:
                        col_name, col_btn = st.columns([3, 1])
                        with col_name:
                            st.write(f"• {etf['name']} ({etf['symbol']})")
                        with col_btn:
                            if st.button("❌", key=f"rm_etf_{etf['symbol']}"):
                                st.session_state.selected_etfs.remove(etf)
                                st.rerun()
            else:
                st.info("No ETFs selected")
    
    # Tabs for Data Table, RRG Computation, and About
    tab1, tab2, tab3 = st.tabs(["📋 Current RRG Values", "🔢 RRG Computation", "ℹ️ About RRG Charts"])
    
    with tab1:
        if 'current_items_data' in st.session_state and 'current_calculator' in st.session_state:
            items_data = st.session_state.current_items_data
            calculator = st.session_state.current_calculator
            
            data_rows = []
            for symbol, (rs_series, momentum_series, _) in items_data.items():
                # Check if series have data before accessing
                if len(rs_series) == 0 or len(momentum_series) == 0:
                    continue
                
                try:
                    current_rs = rs_series.iloc[-1]
                    current_momentum = momentum_series.iloc[-1]
                    quadrant = calculator.get_quadrant(current_rs, current_momentum)
                    data_rows.append({
                        "Symbol": symbol,
                        "RS Ratio": f"{current_rs:.2f}",
                        "RS Momentum": f"{current_momentum:.2f}",
                        "Quadrant": quadrant
                    })
                except (IndexError, KeyError) as e:
                    # Skip items with invalid data
                    continue
                
            if data_rows:
                df_display = pd.DataFrame(data_rows)
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("No data available. Select items to generate RRG chart.")
        else:
            st.info("No data available. Select items to generate RRG chart.")
    
    with tab2:
        st.markdown("## RRG Computation Methods")
        st.markdown("This section explains how RS_Ratio and RS_Momentum are calculated using both the Enhanced Implementation and Standard JdK methodology.")
        
        st.markdown("---")
        
        # RS-Ratio Section
        st.markdown("### RS-Ratio Calculation")
        
        st.markdown("#### Enhanced Implementation (EMA-Based Ratio Normalization)")
        st.markdown("""
        **Step 1: Calculate Relative Strength**
        ```
        RS = Stock_Close / Benchmark_Close
        ```
        
        **Step 2: Calculate Exponential Moving Average**
        ```
        EMA_RS(t) = α × RS(t) + (1-α) × EMA_RS(t-1)
        where α = 2/(m+1), m = 14 (default)
        ```
        
        **Step 3: Calculate RS-Ratio**
        ```
        RS_Ratio = 100 × (EMA_RS / Rolling_Mean(EMA_RS, m))
        ```
        """)
        
        st.markdown("**Key Advantages:**")
        st.markdown("- ✅ **EMA weighting**: Recent data gets exponentially more weight → faster trend detection")
        st.markdown("- ✅ **Ratio normalization**: Direct interpretation (105 = 5% above recent average)")
        st.markdown("- ✅ **Reduced lag**: Responds 2-3 periods earlier than SMA-based methods")
        
        st.markdown("---")
        
        st.markdown("#### Standard JdK Implementation (EMA Smoothing with Z-Score Normalization)")
        st.markdown("""
        **Step 1: Calculate Relative Strength**
        ```
        RS = Stock_Close / Benchmark_Close
        ```
        
        **Step 2: Calculate JdK Relative Strength (EMA Smoothing)**
        ```
        JdK_RS(t) = α × RS(t) + (1-α) × JdK_RS(t-1)
        where α = 2/(m+1), m = 14 (default, RS EMA period)
        ```
        
        **Step 3: Calculate RS-Ratio using Z-Score**
        ```
        RS_Ratio = 100 + 10 × (JdK_RS - Rolling_Mean(JdK_RS, m)) / Rolling_StdDev(JdK_RS, m)
        ```
        """)
        
        st.markdown("**Characteristics:**")
        st.markdown("- ✅ Uses EMA smoothing for faster response than pure SMA-based methods")
        st.markdown("- ⚠️ Z-score normalization requires statistical interpretation")
        st.markdown("- ⚠️ More sensitive to volatility spikes compared to ratio normalization")
        
        st.markdown("---")
        
        # RS-Momentum Section
        st.markdown("### RS-Momentum Calculation")
        
        st.markdown("#### Enhanced Implementation (EMA-Based Percentage Scaling)")
        st.markdown("""
        **Step 1: Calculate Rate of Change**
        ```
        ROC(t) = (RS_Ratio(t) - RS_Ratio(t-k)) / RS_Ratio(t-k)
        where k = 10 (default, short-term momentum)
        ```
        
        **Step 2: Calculate Exponential Moving Average of ROC**
        ```
        EMA_ROC(t) = α × ROC(t) + (1-α) × EMA_ROC(t-1)
        where α = 2/(m+1), m = 14
        ```
        
        **Step 3: Calculate RS-Momentum**
        ```
        RS_Momentum = 100 + 100 × EMA_ROC
        ```
        """)
        
        st.markdown("**Key Advantages:**")
        st.markdown("- ✅ **Direct percentage**: Momentum of 102 = 2% positive momentum (no conversion needed)")
        st.markdown("- ✅ **Short lookback (k=10)**: Captures recent momentum relevant for current swing trade")
        st.markdown("- ✅ **Faster signals**: EMA smoothing detects acceleration/deceleration earlier")
        
        st.markdown("---")
        
        st.markdown("#### Standard JdK Implementation (ROC of Smoothed RS with Z-Score Normalization)")
        st.markdown("""
        **Step 1: Calculate Rate of Change of JdK_RS**
        ```
        ROC(t) = (JdK_RS(t) - JdK_RS(t-k)) / JdK_RS(t-k)
        where k = 10 (default, ROC lookback period)
        ```
        
        **Step 2: Calculate JdK_ROC (EMA Smoothing of ROC)**
        ```
        JdK_ROC(t) = α × ROC(t) + (1-α) × JdK_ROC(t-1)
        where α = 2/(m+1), m = 14
        ```
        
        **Step 3: Calculate RS-Momentum using Z-Score**
        ```
        RS_Momentum = 100 + 10 × (JdK_ROC - Rolling_Mean(JdK_ROC, m)) / Rolling_StdDev(JdK_ROC, m)
        ```
        """)
        
        st.markdown("**Characteristics:**")
        st.markdown("- ✅ Calculates momentum from smoothed RS (JdK_RS) rather than RS_Ratio")
        st.markdown("- ✅ Uses EMA smoothing for faster response")
        st.markdown("- ⚠️ Z-score bounds values by historical volatility")
        
        st.markdown("---")
        
        # Comparison Table
        st.markdown("### Comparison: Enhanced vs Standard")
        
        comparison_data = {
            "Feature": ["Signal Speed", "Interpretation", "Momentum Period", "Volatility Sensitivity"],
            "Enhanced": ["2-3 periods faster", "Direct percentage", "10 periods (relevant)", "Stable ratio-based"],
            "Standard JdK": ["Delayed", "Statistical units", "52 weeks (outdated)", "Z-score volatility-dependent"],
            "Trading Impact": ["Earlier entry/exit", "Faster decisions", "Current market focus", "Fewer false signals"]
        }
        
        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Parameters Section
        st.markdown("### Key Parameters")
        
        st.markdown("**Enhanced Implementation:**")
        param_enhanced = {
            "Parameter": ["EMA Span (m)", "ROC Shift Period (k)"],
            "Symbol": ["m", "k"],
            "Default": ["14", "10"],
            "Description": [
                "Span for EMA of RS and EMA of ROC, and rolling window for RS_Ratio",
                "Shift period for ROC calculation (short-term momentum)"
            ]
        }
        st.dataframe(pd.DataFrame(param_enhanced), use_container_width=True, hide_index=True)
        
        st.markdown("**Standard JdK:**")
        param_standard = {
            "Parameter": ["Window", "Period"],
            "Default (Weekly)": ["14", "52"],
            "Default (Daily)": ["14", "20-26"],
            "Description": [
                "Period for SMA and StdDev calculation",
                "Period for ROC calculation (weeks/days)"
            ]
        }
        st.dataframe(pd.DataFrame(param_standard), use_container_width=True, hide_index=True)
    
    with tab3:
        st.markdown("""
        ## About RRG Charts
        
        **Relative Rotation Graphs (RRG)** visualize the relative strength and momentum of securities compared to a benchmark.
        
        ### Quadrants:
        - **Leading** (Top-Right): High RS, High Momentum - Strong performers expected to outperform
        - **Weakening** (Top-Left): High RS, Low Momentum - Losing momentum, may start to underperform
        - **Lagging** (Bottom-Left): Low RS, Low Momentum - Weak performers likely to underperform
        - **Improving** (Bottom-Right): Low RS, High Momentum - Gaining strength, may soon outperform
        
        ### How to Read:
        - Each line (tail) represents a security's movement over time
        - The tail shows historical positions
        - The current position is marked with a larger dot
        - Colors are unique for each security for easy identification
        - Securities typically rotate clockwise through quadrants
        
        ### Usage:
        1. Select a benchmark from the left pane
        2. Adjust chart settings (timeframe, period, tail count)
        3. Search and add indices, stocks, or ETFs from the right pane
        4. The chart updates automatically when selections change
    """)


if __name__ == "__main__":
    main()
