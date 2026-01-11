"""
RRG (Relative Rotation Graph) Calculator
Adapted from RRG-Lite implementation
"""
import pandas as pd
import numpy as np
import statistics


class RRGCalculator:
    """
    Calculate Relative Strength (RS) and RS Momentum for RRG charts
    Supports two computation methods:
    1. Enhanced (default): EMA-based ratio normalization
    2. Standard JDK: Z-score normalization with SMA
    """
    
    def __init__(self, window=14, period=52, ema_span=14, roc_shift=10, ema_roc_span=14, use_standard_jdk=False):
        """
        Initialize RRG Calculator
        
        :param window: Window size for rolling mean in RS_Ratio calculation (deprecated, now uses ema_roc_span)
        :param period: Period for ROC calculation (used for Standard JDK method)
        :param ema_span: Span for EMA calculation of RS (deprecated, now uses ema_roc_span)
        :param roc_shift: Shift period for ROC calculation (k, default 10) - used for Enhanced method
        :param ema_roc_span: Span for EMA calculation (m, default 14) - used for Enhanced method and window for Standard JDK
        :param use_standard_jdk: If True, use Standard JDK formulas; if False, use Enhanced formulas
        """
        self.window = window  # Deprecated, kept for compatibility
        self.period = period  # Used for Standard JDK ROC calculation
        self.ema_span = ema_span  # Deprecated, kept for compatibility
        self.roc_shift = roc_shift  # k: shift period for ROC (Enhanced method) or ROC lookback (Standard JDK)
        self.ema_roc_span = ema_roc_span  # m: span for EMA (Enhanced) or window for SMA/StdDev (Standard JDK)
        self.use_standard_jdk = use_standard_jdk  # Flag to select computation method
        self.jdk_rs = None  # Store JdK_RS for Standard JDK momentum calculation
    
    def calculate_rs(self, stock_df: pd.Series, benchmark_df: pd.Series) -> pd.Series:
        """
        Calculate RS_Ratio using either Enhanced or Standard JDK formula
        
        Enhanced:
        RS = stock_close / benchmark_close
        EMA_RS = RS.ewm(span=m, adjust=False).mean()
        RS_Ratio = 100 * EMA_RS / EMA_RS.rolling(m).mean()
        
        Standard JDK:
        RS = stock_close / benchmark_close
        JdK_RS = RS.ewm(span=m, adjust=False).mean()
        RS_Ratio = 100 + 10 * (JdK_RS - JdK_RS.rolling(m).mean()) / JdK_RS.rolling(m).std()
        
        :param stock_df: Stock close prices
        :param benchmark_df: Benchmark close prices
        :return: RS ratio series
        """
        # Reset JdK_RS for each calculation (for Standard JDK)
        if self.use_standard_jdk:
            self.jdk_rs = None
        
        if self.use_standard_jdk:
            # Standard JDK method: JdK Relative Strength with EMA smoothing
            # Step 1: Calculate Relative Strength (without 100 multiplier)
            rs = stock_df / benchmark_df
            
            # Step 2: JdK Relative Strength (EMA smoothing)
            # m = ema_roc_span (RS EMA period)
            jdk_rs = rs.ewm(span=self.ema_roc_span, adjust=False).mean()
            
            # Store JdK_RS for momentum calculation
            self.jdk_rs = jdk_rs
            
            # Step 3: RS-Ratio (X-axis)
            # RS_Ratio = 100 + 10 * (JdK_RS - JdK_RS.rolling(m).mean()) / JdK_RS.rolling(m).std()
            jdk_rs_mean = jdk_rs.rolling(window=self.ema_roc_span).mean()
            jdk_rs_std = jdk_rs.rolling(window=self.ema_roc_span).std(ddof=1)
            rs_ratio = 100 + 10 * (jdk_rs - jdk_rs_mean) / jdk_rs_std.replace(0, np.nan)
            
            return rs_ratio
        else:
            # Enhanced method: EMA-based ratio normalization
            # Step 1: Calculate RS (without 100 multiplier)
            rs = stock_df / benchmark_df
            
            # Step 2: Calculate EMA_RS with span=m (using ema_roc_span)
            ema_rs = rs.ewm(span=self.ema_roc_span, adjust=False).mean()
            
            # Step 3: Calculate RS_Ratio using rolling window=m
            ema_rs_mean = ema_rs.rolling(window=self.ema_roc_span).mean()
            rs_ratio = 100 * ema_rs / ema_rs_mean.replace(0, np.nan)
            
            return rs_ratio
    
    def calculate_momentum(self, rs_ratio: pd.Series) -> pd.Series:
        """
        Calculate RS_Momentum using either Enhanced or Standard JDK formula
        
        Enhanced:
        ROC = (RS_Ratio - RS_Ratio.shift(k)) / RS_Ratio.shift(k)
        EMA_ROC = ROC.ewm(span=m, adjust=False).mean()
        RS_Momentum = 100 + 100 * EMA_ROC
        
        Standard JDK:
        ROC = (JdK_RS - JdK_RS.shift(k)) / JdK_RS.shift(k)
        JdK_ROC = ROC.ewm(span=m, adjust=False).mean()
        RS_Momentum = 100 + 10 * (JdK_ROC - JdK_ROC.rolling(m).mean()) / JdK_ROC.rolling(m).std()
        
        :param rs_ratio: RS ratio series
        :return: RS momentum series
        """
        if self.use_standard_jdk:
            # Standard JDK method: Relative Strength Momentum (ROC of smoothed RS)
            # Step 1: Calculate ROC of JdK_RS (not RS_Ratio)
            # k = roc_shift (ROC lookback period)
            # ROC = (JdK_RS - JdK_RS.shift(k)) / JdK_RS.shift(k)
            if self.jdk_rs is None:
                # Fallback: if JdK_RS is not available, return zeros
                return pd.Series(index=rs_ratio.index, data=100.0)
            
            jdk_rs_shifted = self.jdk_rs.shift(self.roc_shift)
            roc = (self.jdk_rs - jdk_rs_shifted) / jdk_rs_shifted.replace(0, np.nan)
            
            # Step 2: Smooth Momentum (EMA of ROC)
            # m = ema_roc_span
            jdk_roc = roc.ewm(span=self.ema_roc_span, adjust=False).mean()
            
            # Step 3: RS-Momentum (Y-axis)
            # RS_Momentum = 100 + 10 * (JdK_ROC - JdK_ROC.rolling(m).mean()) / JdK_ROC.rolling(m).std()
            jdk_roc_mean = jdk_roc.rolling(window=self.ema_roc_span).mean()
            jdk_roc_std = jdk_roc.rolling(window=self.ema_roc_span).std(ddof=1)
            rs_momentum = 100 + 10 * (jdk_roc - jdk_roc_mean) / jdk_roc_std.replace(0, np.nan)
            
            return rs_momentum
        else:
            # Enhanced method: EMA-based percentage scaling
            # Step 1: Calculate ROC
            rs_ratio_shifted = rs_ratio.shift(self.roc_shift)
            roc = (rs_ratio - rs_ratio_shifted) / rs_ratio_shifted.replace(0, np.nan)
            
            # Step 2: Calculate EMA of ROC
            ema_roc = roc.ewm(span=self.ema_roc_span, adjust=False).mean()
            
            # Step 3: Calculate RS_Momentum
            rs_momentum = 100 + 100 * ema_roc
            
            return rs_momentum
    
    def process_series(self, ser: pd.Series) -> pd.Series:
        """
        Make corrections in series if there are duplicate indices
        or not sorted in correct order
        
        :param ser: Input series
        :return: Processed series
        """
        if ser.index.has_duplicates:
            ser = ser.loc[~ser.index.duplicated()]
        
        if not ser.index.is_monotonic_increasing:
            ser = ser.sort_index(ascending=True)
        
        return ser
    
    def get_quadrant(self, rs_value: float, momentum_value: float) -> str:
        """
        Determine which quadrant a point is in
        
        :param rs_value: RS ratio value
        :param momentum_value: RS momentum value
        :return: Quadrant name
        """
        if rs_value > 100 and momentum_value > 100:
            return "Leading"
        elif rs_value > 100 and momentum_value <= 100:
            return "Weakening"
        elif rs_value <= 100 and momentum_value > 100:
            return "Improving"
        else:
            return "Lagging"
    
    def get_color(self, rs_value: float, momentum_value: float) -> str:
        """
        Get color based on quadrant
        
        :param rs_value: RS ratio value
        :param momentum_value: RS momentum value
        :return: Hex color code
        """
        if rs_value > 100:
            return "#008217" if momentum_value > 100 else "#918000"  # Green or Yellow
        else:
            return "#00749D" if momentum_value > 100 else "#E0002B"  # Blue or Red

