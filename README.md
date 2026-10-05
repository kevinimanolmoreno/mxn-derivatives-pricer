# Mexican Derivatives Pricing Engine (TIIE)

A quantitative finance valuation engine built in Python to price Mexican Interest Rate Swaps (IRS) using post-2008 dual-curve methodology (OIS discounting + TIIE projection). 

##  Features
* **Dual-Curve Valuation:** Strictly separates the OIS collateral discounting curve from the TIIE 28 forward projection curve.
* **Curve Construction:** Utilizes PCHIP interpolation for the short end and the **Nelson-Siegel-Svensson (NSS)** parametric model for long-term bootstrapping.
* **Legacy Adjustments:** Automatically incorporates the Banxico regulatory +24 bps adjustment for TIIE Legacy swaps.
* **Risk & Break-even Analysis:** Calculates Mark-to-Market (MTM) for portfolios and uses SciPy's numerical optimization (`fsolve`) to find the exact day a forward rate crosses a fixed target rate.

##  Technologies & Libraries Used
* `numpy` & `pandas` (Vectorized calculations and data manipulation)
* `scipy.optimize` (`fsolve`, `curve_fit`)
* `scipy.interpolate` (`PchipInterpolator`)
* `matplotlib` (P&L and swap profile visualizations)

##  How to Run
1. Ensure that the data files `insumos_ois.xlsx` and `curva_datos.xlsx` are located in the root directory; these contain information obtained from Bank of Mexico databases for fixed income, the Federal Reserve Board for U.S. fixed income, and Investing for forward points.
2. Run the main python script to output the MTM tables and the Break-even analysis.

##  Theoretical Background
The engine heavily relies on local market conventions (Actual/360, 28-day coupons) and roots its mathematical framework in standard fixed-income literature (e.g., Knop Muszynski's Fixed Income Instruments Manual).
