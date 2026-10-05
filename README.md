# MXN Quantitative Pricing & Risk 

A comprehensive Fixed Income and Derivatives pricing engine built in Python. This suite models Mexican market instruments (TIIE, Bonos M) and USD/MXN cross-currency derivatives using institutional-grade quantitative methods.

##  Core Capabilities

The engine is built on a modular architecture, sharing a centralized yield curve bootstrapping and dual-curve discounting framework:

*   **Module 1: Yield Curve Bootstrapping & Dual-Curve Discounting** 
    * OIS discounting curve via PCHIP interpolation.
    * TIIE forward projection curve using numeric bootstrapping (`fsolve`) and Nelson-Siegel-Svensson (NSS) parametric smoothing.
*   **Module 2: Interest Rate Swaps (IRS) & CCS**
    * TIIE Legacy IRS valuation with exact day-count conventions and +24 bps Banxico adjustments.
    * USD/MXN Cross Currency Swaps (CCS) including principal exchange MTM.
*   **Module 3: FX Forwards & Visual Sensitivities**
    * Outright FX Forward pricing using continuous interest rate parity.
    * Break-even and sensitivity visualization via Matplotlib.
*   **Module 4: Options & Greeks (Garman-Kohlhagen)**
    * European FX Options pricing.
    * Analytical Greeks calculation (Delta, Gamma, Vega, Theta).
*   **Module 5: Advanced Bond Valuation & Risk**
    * Mexican Government Bonds (Bonos M) pricing (Clean/Dirty).
    * Iterative Yield-to-Maturity (YTM) calculation using Newton-Raphson.
    * Risk Metrics: Macaulay/Modified Duration, Convexity, and numerical DV01 (Bump & Revalue).

## Tech Stack
* **Python** (Core Logic)
* **SciPy** (`optimize.newton`, `optimize.fsolve`, `optimize.curve_fit`, `stats.norm`, `interpolate.PchipInterpolator`)
* **NumPy & Pandas** (Vectorization and structured reporting)
* **Matplotlib** (Financial visualization and P&L charting)

* ## 📚 Base Teórica y Referencias Bibliográficas

La arquitectura matemática y financiera de este motor de valoración[cite: 1] está fundamentada en estándares institucionales y literatura cuantitativa avanzada. La principal fuente de referencia para las metodologías aplicadas es el **Manual de instrumentos de renta fija, estructurados de tipos de interés y crédito** (Roberto Knop Muszynski, Roberto Castro Riesco, et al.).

Los modelos e implementaciones teóricas extraídas de esta literatura y aplicadas directamente en el código[cite: 1] incluyen:

* **Valoración *Dual-Curve* (Post-2008):** Separación estricta de la curva de descuento colateralizado (OIS) y la curva de proyección interbancaria (TIIE) para el *pricing* libre de arbitraje en *swaps*[cite: 1].
* **Construcción y Suavizado de Curvas:** *Bootstrapping* de tasas cero cupón utilizando interpolación PCHIP para los nodos cortos y el modelo paramétrico de **Nelson-Siegel-Svensson (NSS)** para calibrar la estructura temporal a largo plazo[cite: 1].
* **Modelado de Opciones de Tipo de Cambio:** Implementación del modelo de **Garman-Kohlhagen** (extensión de Black-Scholes para divisas) para evaluar primas teóricas y griegas analíticas (Delta, Gamma, Vega, Theta)[cite: 1].
* **Medición de Riesgo Estructural:** Uso de métodos numéricos (Newton-Raphson) para el cálculo de *Yield to Maturity* (YTM), junto con la derivación de Duración de Macaulay/Modificada, Convexidad y simulación *Bump & Revalue* (+1 pb) para el cálculo del DV01[cite: 1].
* **Paridad Cubierta de Tasas de Interés:** Base matemática para la extracción de factores de descuento implícitos OIS y la valoración de derivados multimoneda, incluyendo FX Forwards y el intercambio de principales en *Cross Currency Swaps* (CCS)[cite: 1].

## How to Run
Ensure `insumos_ois.xlsx` and `curva_datos.xlsx` are located in the root directory. Execute `mxn_pricing_risk_engine.py` to run the valuation pipeline across all asset classes and print the risk matrices.

## 📊 Market Data (As of Date)
The yield curves and market parameters provided in the sample Excel files (`insumos_ois.xlsx` and `curva_datos.xlsx`) reflect market conditions as of **October 1st**. The engine is completely dynamic; you can replace these files with updated daily snapshots to re-run valuations under current market conditions.
