import pandas as pd
import matplotlib.pyplot as plt

def procesar_csv(path, semaforo_id):
    df = pd.read_csv(path)
    # Filtrar por el semáforo específico
    df = df[df['semaforo_id'] == semaforo_id]

    tiempo_acumulado = []
    tiempo_actual = 0

    for duracion in df['duracion_verde']:
        tiempo_acumulado.append(tiempo_actual)
        tiempo_actual += duracion + 3  # fase verde + amarillo

    df['tiempo'] = tiempo_acumulado
    df['minuto'] = (df['tiempo'] // 600).astype(int)  # Cambio de 600 a 60 para que sea minutos reales
    agrupado = df.groupby('minuto')['num_vehiculos'].mean()
    return agrupado

# Especificar el semáforo a analizar
semaforo_objetivo = '2496228891'  # Asegúrate de que sea string si en tu CSV aparece como string

# Cargar y procesar los datos
fuzzy = procesar_csv('datos_semaforos.csv', semaforo_objetivo)
baseline = procesar_csv('datos_semaforos_normal.csv', semaforo_objetivo)

# Graficar
plt.figure(figsize=(10, 6))
plt.plot(fuzzy.index, fuzzy.values, label='Lógica Difusa', marker='o')
plt.plot(baseline.index, baseline.values, label='Control Base', marker='x')

plt.xlabel('Tiempo (minutos)')
plt.ylabel('Vehículos controlados por fase')
plt.title(f'Comparación del Control de Vehículos - Semáforo {semaforo_objetivo}')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
