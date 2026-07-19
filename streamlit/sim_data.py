import pandas as pd
import numpy as np

# 1. Define dimensions
dates = pd.date_range(start='2026-07-12', end='2026-07-19', freq='D')
printers = ['L1', 'L31', 'L32']
shifts = ['5AM-5PM', '5PM-5AM']
hours = [
    "5 a 6", "6 a 7", "7 a 8", "8 a 9", "9 a 10", "10 a 11", 
    "11 a 12", "12 a 1", "1 a 2", "2 a 3", "3 a 4", "4 a 5"
]

# 2. Baseline profiles mapped directly from your provided example image
base_prod = [45000, 55000, 58000, 60000, 61200, 59800, 60500, 56400, 60100, 61500, 59700, 60400]
base_retrac = [23, 0, 2, 5, 3, 5, 4, 35, 10, 11, 6, 6]
base_blow = [23, 3, 4, 6, 7, 4, 22, 12, 5, 7, 8, 3]

rows = []
np.random.seed(42)  # Ensures reproducibility

# 3. Generate individual row records
for date in dates:
    date_str = date.strftime('%Y-%m-%d')
    for printer in printers:
        for shift in shifts:
            for i, hour in enumerate(hours):
                # Introduce minor realistic variation per run
                prod_variation = int(np.random.normal(0, 1200))
                prod = max(0, base_prod[i] + prod_variation)
                
                retrac_variation = np.random.randint(-2, 4)
                retrac = max(0, base_retrac[i] + retrac_variation)
                
                blow_variation = np.random.randint(-2, 3)
                blow = max(0, base_blow[i] + blow_variation)
                
                rows.append({
                    'Fecha': date_str,
                    'Printer': printer,
                    'Shift': shift,
                    'Hora': hour,
                    'Producción x hora': prod,
                    'Retrac-x-hora': retrac,
                    'Blow of': blow
                })

# 4. Construct DataFrame
df = pd.DataFrame(rows)

# 5. Programmatically compute cumulative columns per unique printer shift instance
df['Producción acumulada'] = df.groupby(['Fecha', 'Printer', 'Shift'])['Producción x hora'].cumsum()
df['Retrac acumulado'] = df.groupby(['Fecha', 'Printer', 'Shift'])['Retrac-x-hora'].cumsum()

# 6. Arrange columns cleanly
column_order = [
    'Fecha', 'Printer', 'Shift', 'Hora', 
    'Producción x hora', 'Producción acumulada', 
    'Retrac-x-hora', 'Retrac acumulado', 'Blow of'
]
df = df[column_order]

# 7. Save the data to a CSV file
df.to_csv("simulated_1week_data_printer.csv", index=False)