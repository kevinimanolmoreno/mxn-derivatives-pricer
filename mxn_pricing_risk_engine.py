# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 15:01:28 2026

@author: akaIs
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
from scipy.optimize import fsolve, curve_fit

SPOT_USDMXN = 18.0774


# 1. CURVA OIS (DESCUENTO Y TASAS USD)

try:
    df_ois = pd.read_excel('insumos_ois.xlsx')
    nodos_ois = df_ois.iloc[:, 0].values
    fwds_ois = df_ois.iloc[:, 1].values + SPOT_USDMXN # Asumiendo que vienen en puntos
    us_ois = df_ois.iloc[:, 2].values / 100
except:
    # Datos de respaldo 
    nodos_ois = np.array([30, 90, 180, 360, 720, 1800])
    fwds_ois = np.array([18.1198, 18.2013, 18.3259, 18.5914, 19.2694, 21.9143])
    us_ois = np.array([4.04, 4.25, 4.36, 4.58, 4.85, 4.99]) / 100

dias_ois, ln_desc_ois, ln_desc_us = [], [], []

for d, fwd, tus in zip(nodos_ois, fwds_ois, us_ois):
    t_y = d / 360
    # Paridad MexDer para OIS MXN
    td_simple = ((fwd / SPOT_USDMXN) * (1 + tus * t_y) - 1) / t_y
    df_mxn = 1 / (1 + td_simple * t_y)
    df_usd = 1 / (1 + tus * t_y) # Curva USD
    
    dias_ois.append(d)
    ln_desc_ois.append(np.log(df_mxn))
    ln_desc_us.append(np.log(df_usd))

interp_ois_mxn = PchipInterpolator(dias_ois, ln_desc_ois)
interp_ois_usd = PchipInterpolator(dias_ois, ln_desc_us)

def factores_descuento(t):
    """Devuelve (DF_MXN, DF_USD, Tasa_OIS_Continua, Tasa_USD_Continua)"""
    t = np.maximum(t, 1e-5)
    t_y = t / 360
    ln_m = interp_ois_mxn(t)
    ln_u = interp_ois_usd(t)
    return float(np.exp(ln_m)), float(np.exp(ln_u)), float(-ln_m/t_y), float(-ln_u/t_y)

def tasa_fwd_mercado(tiempo_dias):
    """Calcula el Forward USD/MXN exacto para cualquier día usando paridad continua"""
    df_mxn, df_usd, _, _ = factores_descuento(tiempo_dias)
    return SPOT_USDMXN * (df_usd / df_mxn)


# 2. CURVA TIIE (PROYECCIÓN HÍBRIDA)
try:
    df_proj = pd.read_excel('curva_datos.xlsx')
except:
    datos = {'Plazo':[22,85,169,350,673,1247,2024,3431,5888,10438], 
             'Tasa':[6.14,6.68,6.92,7.41,8.12,8.50,8.00,8.00,7.75,8.00], 
             'Tipo':['cete']*5 + ['bono']*5}
    df_proj = pd.DataFrame(datos)

dias_proj, ln_desc_proj, tasas_cont_proj = [], [], []

for _, row in df_proj.iterrows():
    dias = row.iloc[0]; tasa = row.iloc[1] / 100; tipo = str(row.iloc[2]).strip().lower()
    t_years = dias / 360 
    if tipo == 'cete':
        df_i = 1 / (1 + tasa * t_years)
        dias_proj.append(dias); tasas_cont_proj.append(-np.log(df_i) / t_years); ln_desc_proj.append(np.log(df_i))
    elif tipo == 'bono':
        cupon = tasa * (182 / 360); dias_cupones = np.arange(dias % 182 or 182, dias + 1, 182)
        def optim_zc(zc_guess):
            interp = PchipInterpolator(dias_proj + [dias], ln_desc_proj + [-zc_guess[0]*t_years])
            suma = sum(cupon * np.exp(interp(dc)) for dc in dias_cupones)
            return (suma + (1 + cupon) * np.exp(-zc_guess[0]*t_years)) - 1.0 
        zc_sol = fsolve(optim_zc, x0=[tasa])[0]
        dias_proj.append(dias); tasas_cont_proj.append(zc_sol); ln_desc_proj.append(-zc_sol * t_years)

interp_corta = PchipInterpolator(dias_proj, ln_desc_proj)
def svensson(t, b0, b1, b2, b3, tau1, tau2):
    term1, term2 = t/tau1, t/tau2
    f1 = (1 - np.exp(-term1)) / term1
    return b0 + b1*f1 + b2*(f1 - np.exp(-term1)) + b3*(((1 - np.exp(-term2)) / term2) - np.exp(-term2))
params_sv, _ = curve_fit(svensson, np.array(dias_proj)/360, tasas_cont_proj, p0=[0.10,-0.02,0.02,0.02,2.0,5.0], bounds=([0.0,-1,-1,-1,0.1,0.1], [0.15,1,1,1,20,20]))

def proyeccion_tiie_legacy(d_ini, d_fin):
    """Proyecta la TIIE futura a 28D + 24 bps de ajuste"""
    def tasa_z(d): return -interp_corta(d)/(d/360) if d <= 1095 else svensson(d/360, *params_sv)
    df1 = np.exp(-tasa_z(d_ini) * (d_ini/360)) if d_ini > 0 else 1.0
    df2 = np.exp(-tasa_z(d_fin) * (d_fin/360))
    tasa_s = (np.exp((-np.log(df2/df1)/((d_fin-d_ini)/360)) * ((d_fin-d_ini)/360)) - 1) / ((d_fin-d_ini)/360)
    return tasa_s + 0.0024





# MODULO 1: IRS SOBRE TIIE 
def valuar_irs_tiie(nocional, tasa_fija, plazo_total_dias):
    print("\n" + "="*80)
    print(f" VALUACIÓN IRS TIIE | Plazo: {plazo_total_dias}d | Nocional: ${nocional:,.0f}")
    print("="*80)
    
    cupones = np.arange(28, plazo_total_dias + 1, 28)
    npv_fijo, npv_flotante = 0, 0
    tasas_reporte = []
    
    for i, d_pago in enumerate(cupones):
        d_ini = cupones[i-1] if i > 0 else 0
        tiie = proyeccion_tiie_legacy(d_ini, d_pago)
        df_mxn, _, ois_cont, _ = factores_descuento(d_pago)
        
        flujo_fij = nocional * tasa_fija * (28/360)
        flujo_flt = nocional * tiie * (28/360)
        
        npv_fijo += flujo_fij * df_mxn
        npv_flotante += flujo_flt * df_mxn
        
        tasas_reporte.append({
            'Día': d_pago,
            'OIS_Cont (%)': ois_cont * 100,
            'TIIE_Fwd (%)': tiie * 100,
            'DF_MXN': df_mxn,
            'MTM_Marginal': (flujo_flt - flujo_fij) * df_mxn
        })

    df_rep = pd.DataFrame(tasas_reporte)
    print(df_rep.head(5).to_string(formatters={'OIS_Cont (%)': '{:.4f}'.format, 'TIIE_Fwd (%)': '{:.4f}'.format, 'DF_MXN': '{:.6f}'.format, 'MTM_Marginal': '${:,.2f}'.format}))
    print("... (Mostrando primeros 5 cupones) ...")
    
    mtm_total = npv_flotante - npv_fijo
    print("-" * 80)
    print(f"VALOR DE MERCADO NETO (Recibiendo TIIE, Pagando Fija): ${mtm_total:,.2f}\n")
    
    # GRAFICA
    plt.figure(figsize=(10, 4))
    plt.bar(df_rep['Día'], df_rep['MTM_Marginal'], width=15, color=np.where(df_rep['MTM_Marginal']>0, 'green', 'red'))
    plt.title('IRS: Flujo de Caja Neto Descontado (Mes a Mes)')
    plt.xlabel('Días')
    plt.ylabel('MTM Marginal (MXN)')
    plt.axhline(0, color='black', lw=1)
    plt.grid(alpha=0.3)
    plt.show()

# EJECUTAR:
valuar_irs_tiie(nocional=10_000_000, tasa_fija=0.08, plazo_total_dias=360)




# MODULO 2: CROSS CURRENCY SWAP (USD/MXN)

def valuar_ccs(nocional_usd, tasa_fija_usd, spread_mxn, plazo_dias):
    """Asume Pagar Fija en USD y Recibir TIIE + Spread en MXN"""
    nocional_mxn = nocional_usd * SPOT_USDMXN
    
    print("\n" + "="*80)
    print(f" VALUACIÓN CROSS CURRENCY SWAP | Plazo: {plazo_dias}d")
    print(f" Nocional: ${nocional_usd:,.0f} USD  <--->  ${nocional_mxn:,.0f} MXN (Spot {SPOT_USDMXN})")
    print("="*80)
    
    cupones = np.arange(28, plazo_dias + 1, 28)
    npv_cupones_usd, npv_cupones_mxn = 0, 0
    
    for i, d_pago in enumerate(cupones):
        d_ini = cupones[i-1] if i > 0 else 0
        tiie = proyeccion_tiie_legacy(d_ini, d_pago) + spread_mxn
        df_mxn, df_usd, _, _ = factores_descuento(d_pago)
        
        npv_cupones_usd += (nocional_usd * tasa_fija_usd * (28/360)) * df_usd
        npv_cupones_mxn += (nocional_mxn * tiie * (28/360)) * df_mxn

    # Intercambio Final de Principales
    df_final_mxn, df_final_usd, _, _ = factores_descuento(plazo_dias)
    npv_prin_usd = nocional_usd * df_final_usd
    npv_prin_mxn = nocional_mxn * df_final_mxn
    
    # Valor Total en MXN (Pata MXN - Pata USD convertida a MXN de hoy)
    mtm_usd_en_mxn = (npv_cupones_usd + npv_prin_usd) * SPOT_USDMXN
    mtm_mxn_total = (npv_cupones_mxn + npv_prin_mxn)
    mtm_neto = mtm_mxn_total - mtm_usd_en_mxn
    
    print(f"VP Cupones USD (Pagas)   : ${npv_cupones_usd:,.2f} USD")
    print(f"VP Principal USD (Pagas) : ${npv_prin_usd:,.2f} USD")
    print(f"VP Cupones MXN (Cobras)  : ${npv_cupones_mxn:,.2f} MXN")
    print(f"VP Principal MXN (Cobras): ${npv_prin_mxn:,.2f} MXN")
    print("-" * 80)
    print(f"VALOR MTM NETO DEL CCS (En MXN): ${mtm_neto:,.2f}\n")
    
    # GRAFICA
    plt.figure(figsize=(8, 5))
    labels = ['Cupones USD\n(Pagas)', 'Principal USD\n(Pagas)', 'Cupones MXN\n(Cobras)', 'Principal MXN\n(Cobras)']
    valores = [-npv_cupones_usd * SPOT_USDMXN, -npv_prin_usd * SPOT_USDMXN, npv_cupones_mxn, npv_prin_mxn]
    
    plt.bar(labels, valores, color=['red', 'darkred', 'green', 'darkgreen'])
    plt.title('CCS: Descomposición de Valor Presente (MXN Equiv)')
    plt.ylabel('Millones de MXN')
    plt.axhline(0, color='black', lw=1)
    plt.grid(axis='y', alpha=0.3)
    plt.show()

# EJECUTAR
valuar_ccs(nocional_usd=1_000_000, tasa_fija_usd=0.045, spread_mxn=0.0, plazo_dias=1800)






# MODULO 3: FX FORWARD (USD/MXN)

def valuar_fx_forward(nocional_usd, strike_pactado, plazo_dias, compra_usd=True):
    print("\n" + "="*80)
    print(f" VALUACIÓN FX FORWARD | Plazo: {plazo_dias}d | Strike Pactado: {strike_pactado}")
    print("="*80)
    
    # Extraemos métricas limpias del motor
    df_mxn, df_usd, tasa_ois_mxn, tasa_us = factores_descuento(plazo_dias)
    fwd_mercado = tasa_fwd_mercado(plazo_dias)
    
    # Valuación MTM
    if compra_usd:
        mtm = (fwd_mercado - strike_pactado) * nocional_usd * df_mxn
        postura = "COMPRA USD"
    else:
        mtm = (strike_pactado - fwd_mercado) * nocional_usd * df_mxn
        postura = "VENTA USD"
        
    print(f"Postura            : {postura} de ${nocional_usd:,.0f}")
    print(f"Tasa OIS MXN (Cont): {tasa_ois_mxn*100:.4f}%")
    print(f"Tasa USD Fed (Cont): {tasa_us*100:.4f}%")
    print(f"Spot Actual        : {SPOT_USDMXN:.4f}")
    print(f"Fwd de Mercado Hoy : {fwd_mercado:.4f}  <- Precio justo al día de hoy")
    print("-" * 80)
    print(f"VALOR MTM NETO DEL CONTRATO: ${mtm:,.2f} MXN\n")
    
    # GRAFICA: Análisis de Sensibilidad (¿Qué pasa si el Forward de mercado se mueve?)
    escenarios_fwd = np.linspace(fwd_mercado - 1.0, fwd_mercado + 1.0, 50)
    mtms_simulados = [(f - strike_pactado) * nocional_usd * df_mxn if compra_usd else (strike_pactado - f) * nocional_usd * df_mxn for f in escenarios_fwd]
    
    plt.figure(figsize=(8, 4))
    plt.plot(escenarios_fwd, mtms_simulados, color='blue', lw=2)
    plt.axvline(fwd_mercado, color='orange', linestyle='--', label=f'Mercado Hoy ({fwd_mercado:.2f})')
    plt.axvline(strike_pactado, color='red', linestyle='--', label=f'Strike Pactado ({strike_pactado:.2f})')
    plt.axhline(0, color='black')
    
    plt.fill_between(escenarios_fwd, mtms_simulados, 0, where=(np.array(mtms_simulados)>0), color='green', alpha=0.2)
    plt.fill_between(escenarios_fwd, mtms_simulados, 0, where=(np.array(mtms_simulados)<0), color='red', alpha=0.2)
    
    plt.title('FX Forward: Sensibilidad del MTM ante Movimientos del Dólar')
    plt.xlabel('Precio Forward en el Mercado')
    plt.ylabel('MTM en Pesos (MXN)')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.show()

# EJECUTAR
valuar_fx_forward(nocional_usd=5_000_000, strike_pactado=18.00, plazo_dias=180, compra_usd=True)






# MODULO 4: CÁLCULO DE GRIEGAS Y SENSIBILIDADES (Riesgo)

def calcular_griegas_fx(strike, dias_vencimiento, volatilidad_implicita, tipo='call'):
    """Calcula las griegas analíticas (Garman-Kohlhagen) para una opción FX"""
    T = dias_vencimiento / 360
    S = SPOT_USDMXN
    K = strike
    sigma = volatilidad_implicita
    
    # Motor 1: Factores y Tasas
    _, _, r_mxn, r_usd = factores_descuento(dias_vencimiento)
    
    # D1 y D2
    d1 = (np.log(S / K) + (r_mxn - r_usd + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Derivada de la normal estándar (PDF)
    nd1 = norm.pdf(d1) 
    
    if tipo.lower() == 'call':
        delta = np.exp(-r_usd * T) * norm.cdf(d1)
        # Theta anualizada y luego dividida entre 360 para Theta diaria
        theta_T = (- (S * np.exp(-r_usd*T) * nd1 * sigma) / (2 * np.sqrt(T)) 
                   + r_usd * S * np.exp(-r_usd*T) * norm.cdf(d1) 
                   - r_mxn * K * np.exp(-r_mxn*T) * norm.cdf(d2))
    else: # Put
        delta = -np.exp(-r_usd * T) * norm.cdf(-d1)
        theta_T = (- (S * np.exp(-r_usd*T) * nd1 * sigma) / (2 * np.sqrt(T)) 
                   - r_usd * S * np.exp(-r_usd*T) * norm.cdf(-d1) 
                   + r_mxn * K * np.exp(-r_mxn*T) * norm.cdf(-d2))
        
    # Gamma y Vega son iguales para Call y Put
    gamma = (nd1 * np.exp(-r_usd * T)) / (S * sigma * np.sqrt(T))
    vega = S * np.exp(-r_usd * T) * nd1 * np.sqrt(T)
    
    # Ajustes de escala estándar en trading
    vega_1pct = vega * 0.01           # Sensibilidad a 1% de shock en Vol
    theta_1dia = theta_T / 360        # Pérdida de valor por 1 día que pasa
    
    print("\n" + "="*80)
    print(f" MATRIZ DE RIESGO (GRIEGAS FX) | {tipo.upper()} | Strike {K}")
    print("="*80)
    print(f"DELTA (Riesgo Spot) : {delta:.4f} USD (Por cada 1 USD nocional)")
    print(f"GAMMA (Curvatura)   : {gamma:.4f}")
    print(f"VEGA  (Riesgo Vol)  : {vega_1pct:.4f} MXN (Por 1% de alza en volatilidad)")
    print(f"THETA (Time Decay)  : {theta_1dia:.4f} MXN (Pérdida por día transcurrido)")
    print("-" * 80 + "\n")
    
    return delta, gamma, vega_1pct, theta_1dia


def calcular_dv01_irs(nocional, tasa_fija, plazo_total_dias):
    """
    Calcula el DV01 (Riesgo de Tasa) simulando un Bump & Revalue Numérico.
    Choque = +1 Punto Base (0.01% o 0.0001) a la curva TIIE.
    """
    cupones = np.arange(28, plazo_total_dias + 1, 28)
    npv_base, npv_shock = 0, 0
    bump = 0.0001 # 1 Punto base
    
    for i, d_pago in enumerate(cupones):
        d_ini = cupones[i-1] if i > 0 else 0
        df_mxn, _, _, _ = factores_descuento(d_pago)
        
        # 1. TIIE Base
        tiie_base = proyeccion_tiie_legacy(d_ini, d_pago)
        flujo_flt_base = nocional * tiie_base * (28/360)
        
        # 2. TIIE Shockeada (+1 pb)
        tiie_shock = tiie_base + bump
        flujo_flt_shock = nocional * tiie_shock * (28/360)
        
        flujo_fij = nocional * tasa_fija * (28/360)
        
        # MTM Acumulado
        npv_base += (flujo_flt_base - flujo_fij) * df_mxn
        npv_shock += (flujo_flt_shock - flujo_fij) * df_mxn
        
    dv01 = npv_shock - npv_base
    
    print("="*80)
    print(f" SENSIBILIDAD DE TASA (DV01) - IRS TIIE")
    print("="*80)
    print(f"MTM Base                : ${npv_base:,.2f} MXN")
    print(f"MTM con Shock (+1 bps)  : ${npv_shock:,.2f} MXN")
    print(f"DV01 Total              : ${dv01:,.2f} MXN por cada punto base")
    print("="*80 + "\n")
    
    return dv01

# EJECUTAR:
# 1. Griegas de la Opción
_ = calcular_griegas_fx(strike=18.50, dias_vencimiento=90, volatilidad_implicita=0.115, tipo='call')

# 2. Sensibilidad (DV01) de un Swap de 10 Millones a 360 días
_ = calcular_dv01_irs(nocional=10_000_000, tasa_fija=0.08, plazo_total_dias=360)



#MODULO 5: OPCIONES DE TIPO DE CAMBIO. TIPO EUROPEO

from scipy.stats import norm

def valuar_opcion_fx(strike, dias_vencimiento, volatilidad_implicita, tipo='call'):
    """
    Valúa una opción Europea USD/MXN.
    strike: Nivel de tipo de cambio pactado (K)
    dias_vencimiento: Días hasta la expiración
    volatilidad_implicita: Volatilidad anualizada (ej. 0.12 para 12%)
    tipo: 'call' (compra USD) o 'put' (venta USD)
    """
    T = dias_vencimiento / 360
    S = SPOT_USDMXN
    K = strike
    sigma = volatilidad_implicita
    
    # Extraemos las tasas continuas exactas para el plazo
    df_mxn, df_usd, r_mxn, r_usd = factores_descuento(dias_vencimiento)
    
    # Modelo Garman-Kohlhagen
    d1 = (np.log(S / K) + (r_mxn - r_usd + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if tipo.lower() == 'call':
        precio = S * np.exp(-r_usd * T) * norm.cdf(d1) - K * np.exp(-r_mxn * T) * norm.cdf(d2)
    elif tipo.lower() == 'put':
        precio = K * np.exp(-r_mxn * T) * norm.cdf(-d2) - S * np.exp(-r_usd * T) * norm.cdf(-d1)
    else:
        raise ValueError("El tipo debe ser 'call' o 'put'")
        
    print("\n" + "="*80)
    print(f" VALUACIÓN FX OPTION ({tipo.upper()}) | Expiración: {dias_vencimiento}d | Strike: {K}")
    print("="*80)
    print(f"Spot Actual (S)    : {S:.4f}")
    print(f"Tasa Doméstica (r_d): {r_mxn*100:.4f}% (MXN Continua)")
    print(f"Tasa Extranjera(r_f): {r_usd*100:.4f}% (USD Continua)")
    print(f"Volatilidad (sigma): {sigma*100:.2f}%")
    print("-" * 80)
    print(f"PRIMA TEÓRICA      : {precio:.4f} MXN por cada 1 USD")
    print("="*80 + "\n")
    
    return precio

# EJECUTAR
prima_call = valuar_opcion_fx(strike=18.50, dias_vencimiento=90, volatilidad_implicita=0.115, tipo='call')

prima_put = valuar_opcion_fx(strike=17.80, dias_vencimiento=180, volatilidad_implicita=0.122, tipo='put')



# MODULO 5: VALUACIÓN DE BONOS (Bonos M) Y RIESGO

from scipy.optimize import newton

def valuar_bono_m(tasa_cupon, dias_vencimiento, nominal=100):
    """
    Valúa un Bono M (cupones cada 182 días) usando la curva cero (Svensson).
    Calcula Precio Limpio/Sucio, YTM, Duración, Convexidad y DV01.
    """
    print("\n" + "="*85)
    print(f" VALUACIÓN DE BONO | Vencimiento: {dias_vencimiento}d | Cupón: {tasa_cupon*100:.2f}% | Nominal: ${nominal}")
    print("="*85)
    
    # 1. Identificar fechas de pago (hacia atrás desde el vencimiento)
    dias_cupones = np.arange(dias_vencimiento % 182 or 182, dias_vencimiento + 1, 182)
    flujo_cupon = nominal * tasa_cupon * (182 / 360)
    
    vp_flujos_total = 0
    datos_flujos = []
    
    # 2. Descuento de flujos con la Curva Cero (NSS)
    for d in dias_cupones:
        t_years = d / 360
        # Usamos tu función svensson 
        tasa_cero = svensson(t_years, *params_sv) 
        df = np.exp(-tasa_cero * t_years)
        
        es_ultimo = (d == dias_vencimiento)
        flujo = flujo_cupon + nominal if es_ultimo else flujo_cupon
        vp_flujo = flujo * df
        vp_flujos_total += vp_flujo
        
        datos_flujos.append({
            'Días': int(d),
            'Tasa Cero (%)': tasa_cero * 100,
            'Factor Desc': df,
            'Flujo (MXN)': flujo,
            'VP Flujo (MXN)': vp_flujo
        })
        
    precio_sucio = vp_flujos_total
    
    # 3. Intereses Devengados y Precio Limpio
    dias_transcurridos = 182 - (dias_vencimiento % 182 or 182)
    interes_devengado = nominal * tasa_cupon * (dias_transcurridos / 360)
    precio_limpio = precio_sucio - interes_devengado
    
    # 4. Cálculo de YTM (Rendimiento al Vencimiento)
    # Función objetivo: El VP de los flujos descontados a la YTM debe ser igual al Precio Sucio
    def objetivo_ytm(y):
        vp_ytm = 0
        for d in dias_cupones:
            flujo = flujo_cupon + nominal if d == dias_vencimiento else flujo_cupon
            vp_ytm += flujo / ((1 + y * (182/360)) ** (d / 182))
        return vp_ytm - precio_sucio
    
    # Encontrar la raíz usando el método de Newton
    ytm = newton(objetivo_ytm, x0=tasa_cupon)
    
    # 5. Cálculo de Métricas de Riesgo (Duración y Convexidad)
    mac_dur_num = 0
    convexidad_num = 0
    
    for d in dias_cupones:
        t_periodos = d / 182
        t_years = d / 360
        flujo = flujo_cupon + nominal if d == dias_vencimiento else flujo_cupon
        
        # Valor presente del flujo usando la YTM discreta
        vp_ytm = flujo / ((1 + ytm * (182/360)) ** t_periodos)
        
        mac_dur_num += t_years * vp_ytm
        # Aproximación teórica de convexidad
        convexidad_num += (t_years**2 + t_years*(182/360)) * vp_ytm 
        
    duracion_macaulay = mac_dur_num / precio_sucio
    duracion_modificada = duracion_macaulay / (1 + ytm * (182/360))
    convexidad = convexidad_num / (precio_sucio * (1 + ytm * (182/360))**2)
    
    # DV01: Pérdida de valor en MXN por un aumento de 1 punto base (0.01%)
    dv01 = duracion_modificada * precio_sucio * 0.0001
    
    
    df_reporte = pd.DataFrame(datos_flujos)
    print("CRONOGRAMA DE FLUJOS (Mostrando los primeros y últimos 3):")
    if len(df_reporte) > 6:
        print(pd.concat([df_reporte.head(3), df_reporte.tail(3)]).to_string(index=False, float_format="%.4f"))
    else:
        print(df_reporte.to_string(index=False, float_format="%.4f"))
    
    print("\n" + "-"*85)
    print(" MÉTRICAS DE VALORACIÓN (PRICING)")
    print("-"*85)
    print(f"Precio Limpio (Clean Price) : ${precio_limpio:.4f} MXN")
    print(f"Intereses Devengados        : ${interes_devengado:.4f} MXN (Días transcurridos: {dias_transcurridos})")
    print(f"Precio Sucio (Dirty Price)  : ${precio_sucio:.4f} MXN")
    print(f"Yield to Maturity (YTM)     : {ytm*100:.4f}%")
    
    print("\n" + "-"*85)
    print(" MEDIDAS DE RIESGO DE TASA (SENSITIVITIES)")
    print("-"*85)                                       
    print(f"Duración de Macaulay        : {duracion_macaulay:.4f} años")
    print(f"Duración Modificada         : {duracion_modificada:.4f} años")
    print(f"Convexidad                  : {convexidad:.4f}")
    print(f"DV01 (Riesgo por 1 pb)      : ${dv01:.4f} MXN (Por cada $100 nominales)")
    print("="*85 + "\n")
    
    return precio_limpio, ytm, duracion_modificada, dv01

# EJECUTAR
_ = valuar_bono_m(tasa_cupon=0.075, dias_vencimiento=3600, nominal=100)
