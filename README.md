# MXN Quantitative Pricing & Risk 

A comprehensive Fixed Income and Derivatives pricing engine built in Python. This suite models Mexican market instruments (TIIE, Bonos M) and USD/MXN cross-currency derivatives using institutional-grade quantitative methods.

##  Core Capabilities

The engine is built on a modular architecture, sharing a centralized yield curve bootstrapping and dual-curve discounting framework:

**Module 1: Yield Curve Bootstrapping & Dual-Curve Discounting** 
    * OIS discounting curve via PCHIP interpolation.
    * TIIE forward projection curve using numeric bootstrapping (`fsolve`) and Nelson-Siegel-Svensson (NSS) parametric smoothing. **Module 2: Interest Rate Swaps (IRS) & CCS**
    * TIIE Legacy IRS valuation with exact day-count conventions and +24 bps Banxico adjustments.
    * USD/MXN Cross Currency Swaps (CCS) including principal exchange MTM.
**Module 3: FX Forwards & Visual Sensitivities**
    * Outright FX Forward pricing using continuous interest rate parity.
    * Break-even and sensitivity visualization via Matplotlib.
**Module 4: Options & Greeks (Garman-Kohlhagen)**
    * European FX Options pricing.
    * Analytical Greeks calculation (Delta, Gamma, Vega, Theta).
**Module 5: Advanced Bond Valuation & Risk**
    * Mexican Government Bonds (Bonos M) pricing (Clean/Dirty).
    * Iterative Yield-to-Maturity (YTM) calculation using Newton-Raphson.
    * Risk Metrics: Macaulay/Modified Duration, Convexity, and numerical DV01 (Bump & Revalue).

## Tech Stack
**Python** (Core Logic)
**SciPy** (`optimize.newton`, `optimize.fsolve`, `optimize.curve_fit`, `stats.norm`, `interpolate.PchipInterpolator`)
**NumPy & Pandas** (Vectorization and structured reporting)
**Matplotlib** (Financial visualization and P&L charting)

## Theoretical Background & References

The mathematical and financial architecture of this pricing engine is rooted in institutional standards and advanced quantitative literature. The primary reference for the applied methodologies is the **Manual de instrumentos de renta fija, estructurados de tipos de interés y crédito** (Roberto Knop Muszynski, Roberto Castro Riesco, et al.).

The theoretical models and implementations extracted from this literature and applied directly in the code include:

**Dual-Curve Valuation (Post-2008)** Strict separation of the collateralized discounting curve (OIS) and the interbank projection curve (TIIE) for arbitrage-free swap pricing.
**Curve Construction & Smoothing** Zero-coupon yield curve bootstrapping using PCHIP interpolation for the short end and the **Nelson-**Siegel-Svensson (NSS)** parametric model to calibrate the long-term term structure.
**FX Options Modeling** Implementation of the **Garman-Kohlhagen** model (an extension of Black-Scholes for currencies) to evaluate theoretical premiums and analytical Greeks (Delta, Gamma, Vega, Theta).
**Structural Risk Measurement** Use of numerical methods (Newton-Raphson) to calculate Yield to Maturity (YTM), along with the derivation of Macaulay/Modified Duration, Convexity, and a numerical *Bump & Revalue* simulation (+1 bps) for DV01 calculation.
**Covered Interest Rate Parity** Mathematical foundation for extracting implicit OIS discount factors and pricing multi-currency derivatives, including FX Forwards and principal exchanges in Cross Currency Swaps (CCS).

## How to Run
Ensure `insumos_ois.xlsx` and `curva_datos.xlsx` are located in the root directory. Execute `mxn_pricing_risk_engine.py` to run the valuation pipeline across all asset classes and print the risk matrices.

## Market Data (As of Date)
The yield curves and market parameters provided in the sample Excel files (`insumos_ois.xlsx` and `curva_datos.xlsx`) reflect market conditions as of **October 1st**. The engine is completely dynamic; you can replace these files with updated daily snapshots to re-run valuations under current market conditions.
