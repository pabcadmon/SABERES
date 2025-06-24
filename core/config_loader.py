import pandas as pd

def cargar_configuracion(path="config.csv"):
    df = pd.read_csv(path)
    return df