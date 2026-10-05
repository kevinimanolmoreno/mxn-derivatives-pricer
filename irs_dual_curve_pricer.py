# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 13:51:36 2026

@author: akaIs
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
from scipy.optimize import fsolve, curve_fit

print("="*80)
print(" INICIANDO MOTOR DE VALUACIÓN DUAL-CURVE (IRS TIIE LEGACY)")
print("="*80)


#CONSTRUCCIÓN DE CURVA OIS (DESCUENTO)

SPOT_USDMXN = 18.0774 # Tipo de cambio spot 

try:
    df_ois = pd.read_excel('insumos_ois.xlsx')
    df_ois.columns = ['Plazo_Dias', 'Puntos_Forward', 'Tasa_US_Porcentaje']
    
    dias_ois, ln_desc_ois = [], []
    for _, row in df_ois.iterrows():
        d = row['Plazo_Dias']
        fwd = SPOT_USDMXN + row['Puntos_Forward']
        valor_limpio = str(row['Tasa_US_Porcentaje']).replace('%', '').replace(',', '.').strip()
        tus = float(valor_limpio) / 100
        t_years = d / 360
        
        # Ecuación de Paridad MexDer para OIS
        td_simple = ((fwd / SPOT_USDMXN) * (1 + tus * t_years) - 1) / t_years
        df_nodo = 1 / (1 + td_simple * t_years)
        
        dias_ois.append(d)
        ln_desc_ois.append(np.log(df_nodo))
        
    interp_ois = PchipInterpolator(dias_ois, ln_desc_ois)
    print("[OK] Curva de Descuento OIS construida exitosamente.")
except Exception as e:
    print(f"[ERROR] No se pudo procesar la Curva OIS: {e}")

def factor_descuento_ois(tiempo_dias):
    """Devuelve el factor de descuento extraído de la curva OIS."""
    t = np.maximum(tiempo_dias, 1e-5)
    return float(np.exp(interp_ois(t)))


#CONSTRUCCIÓN DE CURVA PROYECCIÓN (HÍBRIDA)

try:
    df_proj = pd.read_excel('curva_datos.xlsx')
    df_proj.columns = ['Plazo_Dias', 'Tasa_Porcentaje', 'Tipo']
    df_proj = df_proj.sort_values('Plazo_Dias').reset_index(drop=True)

    dias_proj, ln_desc_proj, tasas_cont_proj = [], [], []

    # Bootstrapping (Espacio ln D)
    for _, row in df_proj.iterrows():
        dias = row['Plazo_Dias']
        tasa = row['Tasa_Porcentaje'] / 100
        tipo = str(row['Tipo']).strip().lower()
        t_years = dias / 360 
        
        if tipo == 'cete':
            df_i = 1 / (1 + tasa * t_years)
            dias_proj.append(dias)
            tasas_cont_proj.append(-np.log(df_i) / t_years)
            ln_desc_proj.append(np.log(df_i))
            
        elif tipo == 'bono':
            cupon = tasa * (182 / 360) 
            dias_cupones = np.arange(dias % 182, dias, 182)
            if len(dias_cupones) == 0 or dias_cupones[0] <= 0: dias_cupones = np.arange(182, dias, 182)
                
            def optimizar_tasa_cero(zc_guess):
                temp_dias = dias_proj + [dias]
                temp_lnD = ln_desc_proj + [-zc_guess[0] * t_years] 
                interp_temp = PchipInterpolator(temp_dias, temp_lnD)
                suma_cupones = sum(cupon * np.exp(interp_temp(d_c)) for d_c in dias_cupones)
                df_final = np.exp(-zc_guess[0] * t_years)
                return (suma_cupones + (1 + cupon) * df_final) - 1.0 
            
            zc_solucion = fsolve(optimizar_tasa_cero, x0=[tasa])[0]
            dias_proj.append(dias)
            tasas_cont_proj.append(zc_solucion)
            ln_desc_proj.append(-zc_solucion * t_years)

    # Splice: PCHIP (Corto) + Svensson (Largo)
    interp_proj_corta = PchipInterpolator(dias_proj, ln_desc_proj)
    
    def svensson(t, b0, b1, b2, b3, tau1, tau2):
        t = np.maximum(t, 1e-5)
        term1, term2 = t/tau1, t/tau2
        f1 = (1 - np.exp(-term1)) / term1
        return b0 + b1*f1 + b2*(f1 - np.exp(-term1)) + b3*(((1 - np.exp(-term2)) / term2) - np.exp(-term2))

    t_y_arr = np.array(dias_proj) / 360
    lim_sv = ([0.0, -1.0, -1.0, -1.0, 0.1, 0.1], [0.15, 1.0, 1.0, 1.0, 20.0, 20.0])
    p0_sv = [0.10, -0.02, 0.02, 0.02, 2.0, 5.0] 
    params_sv, _ = curve_fit(svensson, t_y_arr, np.array(tasas_cont_proj), p0=p0_sv, bounds=lim_sv)

    def tasa_proj_hibrida(tiempo_dias):
        if tiempo_dias <= 1095:
            return float(-interp_proj_corta(tiempo_dias) / (tiempo_dias/360))
        else:
            return float(svensson(tiempo_dias/360, *params_sv))
            
    print("[OK] Curva de Proyección (Híbrida) construida exitosamente.")
except Exception as e:
    print(f"[ERROR] No se pudo procesar la Curva de Proyección: {e}")


#MÓDULO FORWARD Y AJUSTE TIIE 

def proyeccion_tiie_legacy(dias_inicio, dias_fin):
    """Calcula la tasa forward implicita y aplica el ajuste regulatorio de +24 bps."""
    t1, t2 = dias_inicio / 360, dias_fin / 360
    
    # Extraemos factores de descuento de la curva 2 (Proyección)
    df1 = np.exp(-tasa_proj_hibrida(dias_inicio) * t1) if dias_inicio > 0 else 1.0
    df2 = np.exp(-tasa_proj_hibrida(dias_fin) * t2)
    
    # Tasa forward continua
    fwd_continua = -np.log(df2 / df1) / (t2 - t1)
    
    # Convertimos a tasa simple nominal (base 360) para el cupón
    dt_dias = dias_fin - dias_inicio
    tasa_simple = (np.exp(fwd_continua * (dt_dias/360)) - 1) / (dt_dias/360)
    
    # AJUSTE LEGACY BANXICO: TIIE + 24 bps (0.0024)
    tiie_legacy = tasa_simple + 0.0024 
    return tiie_legacy


#PRICER: VALUACIÓN DE SWAP (FIX vs FLOAT)

def valuar_irs_legacy(nocional, tasa_fija, plazo_total_dias):
    print(f"\n--- VALUACIÓN DE IRS TIIE LEGACY ({plazo_total_dias} DÍAS) ---")
    print(f"Nocional: ${nocional:,.2f} | Tasa Fija Pactada: {tasa_fija*100:.2f}%")
    
    cupones_dias = np.arange(28, plazo_total_dias + 1, 28)
    npv_fijo = 0
    npv_flotante = 0
    
    print(f"{'Día':<6} | {'TIIE Proyectada':<16} | {'Flujo Fijo':<12} | {'Flujo Variable':<14} | {'Factor OIS':<12}")
    print("-" * 70)
    
    for i, d_pago in enumerate(cupones_dias):
        d_inicio = cupones_dias[i-1] if i > 0 else 0
        
        # 1. Proyectamos la TIIE con Ajuste Legacy
        tiie_proyectada = proyeccion_tiie_legacy(d_inicio, d_pago)
        
        # 2. Calculamos los flujos (fracción de 28 días)
        flujo_fijo = nocional * tasa_fija * (28 / 360)
        flujo_flotante = nocional * tiie_proyectada * (28 / 360)
        
        # 3. Descontamos usando la curva OIS
        df_ois = factor_descuento_ois(d_pago)
        npv_fijo += flujo_fijo * df_ois
        npv_flotante += flujo_flotante * df_ois
        
        if i < 3 or i > len(cupones_dias) - 4: # Solo mostramos los primeros y últimos para no saturar
            print(f"{d_pago:<6} | {tiie_proyectada*100:>7.4f}% +24bps | \({flujo_fijo:<11,.2f} |\){flujo_flotante:<13,.2f} | {df_ois:.6f}")
        elif i == 3:
            print("...    | ...              | ...          | ...            | ...")

    npv_total = npv_flotante - npv_fijo # Asumiendo que Recibes Variable y Pagas Fijo
    
    print("-" * 70)
    print(f"VP Pata Fija (Pagas)    : -${npv_fijo:,.2f}")
    print(f"VP Pata Variable (Cobras): +${npv_flotante:,.2f}")
    print(f"VALOR DE MERCADO (MTM)  :  ${npv_total:,.2f}\n")

def valuar_portafolio(portafolio):
    """
    Recibe una lista de diccionarios con las características de varios swaps
    y devuelve un reporte consolidado.
    """
    print("="*90)
    print(" REPORTE CONSOLIDADO DE PORTAFOLIO - MTM (MARK-TO-MARKET)")
    print("="*90)
    
    resultados = []
    mtm_total_portafolio = 0
    
    for idx, swap in enumerate(portafolio):
        nocional = swap['nocional']
        tasa_fija = swap['tasa_fija']
        plazo = swap['plazo']
        # 'recibe_fija' es un booleano: True si el banco te paga la fija y tu pagas TIIE
        recibe_fija = swap.get('recibe_fija', False) 
        
        cupones_dias = np.arange(28, plazo + 1, 28)
        npv_fijo = 0
        npv_flotante = 0
        
        for i, d_pago in enumerate(cupones_dias):
            d_inicio = cupones_dias[i-1] if i > 0 else 0
            tiie_proyectada = proyeccion_tiie_legacy(d_inicio, d_pago)
            df_ois = factor_descuento_ois(d_pago)
            
            npv_fijo += nocional * tasa_fija * (28 / 360) * df_ois
            npv_flotante += nocional * tiie_proyectada * (28 / 360) * df_ois
            
        # Lógica direccional del derivado
        if recibe_fija:
            mtm_swap = npv_fijo - npv_flotante
            direccion = "Recibe Fija / Paga TIIE"
        else:
            mtm_swap = npv_flotante - npv_fijo
            direccion = "Paga Fija / Recibe TIIE"
            
        mtm_total_portafolio += mtm_swap
        
        # Guardamos resumen
        resultados.append({
            'ID': f"Swap_{idx+1}",
            'Plazo': f"{plazo}d",
            'Nocional': f"${nocional/1e6:.1f}M",
            'Tasa Fija': f"{tasa_fija*100:.2f}%",
            'Dirección': direccion,
            'MTM (Valor)': mtm_swap
        })

    # Imprimimos tabla estilo DataFrame
    df_reporte = pd.DataFrame(resultados)
    df_reporte['MTM (Valor)'] = df_reporte['MTM (Valor)'].apply(lambda x: f"${x:,.2f}")
    print(df_reporte.to_string(index=False))
    print("-" * 90)
    print(f"VALOR NETO DEL PORTAFOLIO (NPV): ${mtm_total_portafolio:,.2f}\n")



#GRÁFICA DE ANÁLISIS DE SWAP (P&L PROYECTADO)

def graficar_analisis_swap(tasa_fija_pactada, plazo_total_dias):
    """
    Gráfica analítica para decisiones de Trading. 
    Muestra la Tasa Fija vs la curva de TIIE proyectada en el tiempo.
    """
    cupones_dias = np.arange(28, plazo_total_dias + 1, 28)
    tasas_tiie_esperadas = []
    
    for i, d_pago in enumerate(cupones_dias):
        d_inicio = cupones_dias[i-1] if i > 0 else 0
        tasas_tiie_esperadas.append(proyeccion_tiie_legacy(d_inicio, d_pago) * 100)
        
    plt.figure(figsize=(10, 5))
    
    # 1. Curva de TIIE Proyectada (Lo que el mercado espera)
    plt.plot(cupones_dias, tasas_tiie_esperadas, marker='o', color='purple', linewidth=2, label='TIIE Legacy Proyectada (Curva Fwd)')
    
    # 2. Línea de Tasa Fija Pactada (El nivel de quiebre)
    plt.axhline(y=tasa_fija_pactada * 100, color='red', linestyle='--', linewidth=2, label=f'Tasa Fija Pactada ({tasa_fija_pactada*100:.2f}%)')
    
    # Sombreado de Ganancia / Pérdida visual (Asumiendo que Pagas Fijo y Recibes TIIE)
    plt.fill_between(cupones_dias, tasas_tiie_esperadas, tasa_fija_pactada * 100, 
                     where=(np.array(tasas_tiie_esperadas) > tasa_fija_pactada * 100), 
                     interpolate=True, color='green', alpha=0.2, label='Zona de Ganancia Acumulada')
    
    plt.fill_between(cupones_dias, tasas_tiie_esperadas, tasa_fija_pactada * 100, 
                     where=(np.array(tasas_tiie_esperadas) <= tasa_fija_pactada * 100), 
                     interpolate=True, color='red', alpha=0.2, label='Zona de Pérdida')
    
    plt.title(f'Perfil de Riesgo y Proyección: Swap a {plazo_total_dias} días', fontsize=12, fontweight='bold')
    plt.xlabel('Días hasta pago de cupón', fontsize=10)
    plt.ylabel('Tasa Nominal Anual (%)', fontsize=10)
    plt.legend(loc='best')
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.tight_layout()
    plt.show()


#EJECUCIÓN

# Creamos un portafolio de 3 Swaps con distintos tamaños y plazos
mi_portafolio = [
    {'nocional': 500, 'tasa_fija': 0.0820, 'plazo': 300, 'recibe_fija': True}, # Paga fija
    {'nocional': 100, 'tasa_fija': 0.0850, 'plazo': 400, 'recibe_fija': True},  # Recibe fija
    {'nocional': 1_000,  'tasa_fija': 0.1000, 'plazo': 500, 'recibe_fija': True}  # Paga fija
]

valuar_portafolio(mi_portafolio)

# Graficamos el análisis visual del primer Swap (a 1 año al 8.20%)
graficar_analisis_swap(tasa_fija_pactada=0.0750, plazo_total_dias=1000)



# COMPLEMENTO: ENCONTRAR DÍA DE CRUCE (BREAK-EVEN)

from scipy.optimize import fsolve

def encontrar_dia_cruce_tasa(tasa_fija_objetivo, limite_dias=3600):
    """
    Escanea la curva proyectada y encuentra el día exacto en el que 
    la TIIE a 28 días igualará a la tasa fija dada por el usuario.
    """
    print("\n" + "="*80)
    print(f" BUSCANDO PUNTO DE EQUILIBRIO: Tasa Variable == {tasa_fija_objetivo*100:.4f}%")
    print("="*80)
    
    # Función objetivo para fsolve: Queremos que la diferencia sea cero
    def diferencia_tasas(d_pago):
        if d_pago < 28:
            return 1.0 # Penalización para evitar buscar antes del primer cupón
        d_inicio = d_pago - 28
        # Evaluamos tu función original de proyección
        tasa_variable = proyeccion_tiie_legacy(d_inicio, d_pago)
        return tasa_variable - tasa_fija_objetivo

    # 1. Escaneo inicial por grilla (para detectar si la curva cruza múltiples veces)
    dias_test = np.arange(28, limite_dias + 1, 14) # Muestreo cada 14 días
    valores = [diferencia_tasas(d) for d in dias_test]
    
    cruces_detectados = []
    
    # Buscamos cambios de signo (donde la variable pasa de ser menor a mayor, o viceversa)
    for i in range(len(valores) - 1):
        if valores[i] * valores[i+1] <= 0:
            # 2. Usar fsolve para encontrar el día decimal exacto del cruce
            dia_cruce_exacto = fsolve(diferencia_tasas, x0=dias_test[i])[0]
            # Redondeamos ligeramente para evitar duplicados por tolerancia de fsolve
            if not any(abs(dia_cruce_exacto - c) < 1.0 for c in cruces_detectados):
                cruces_detectados.append(dia_cruce_exacto)
                
    if not cruces_detectados:
        print(f"No se encontró ningún cruce con la tasa del {tasa_fija_objetivo*100:.2f}% en los próximos {limite_dias} días.")
        print("La tasa objetivo está por encima del pico máximo o por debajo del mínimo de tu curva actual.")
    else:
        for idx, cruce in enumerate(cruces_detectados):
            tasa_comprobacion = proyeccion_tiie_legacy(cruce - 28, cruce)
            print(f"Cruce #{idx+1} detectado en el Día: {cruce:.1f} (Aprox. {cruce/360:.2f} años)")
            print(f" -> Comprobación matemática: TIIE Proyectada = {tasa_comprobacion*100:.4f}%")
    
    print("="*80 + "\n")
    return cruces_detectados


# EJECUCIÓN DEL COMPLENTO
dias_empate = encontrar_dia_cruce_tasa(tasa_fija_objetivo=0.0820)