import get_data
import update_db
from datetime import datetime
from pathlib import Path
import pandas as pd


base_dir = Path(__file__).resolve().parent
etf_list_path = base_dir / "etf_list5.xlsx"
df = pd.read_excel(etf_list_path)
NB_LINES_XLS_FILE = len(df)

début = datetime.now()

for index, row in df.iterrows():
    isin_str = str(row["ISIN"])
    ticker_str = str(row["Ticker"])

    NumETF = index + 1
    print(f"------ Traitement de l'ETF {NumETF}/{NB_LINES_XLS_FILE} ------")

    # Mise à jour de la table des données statiques
    update_db.add_etf_static(isin_str)

    # Mise à jour de la table des données dynamiques
    donnees_dispo = get_data.refresh_etf(isin_str, ticker_str)

    if donnees_dispo:
        # Mise à jour de la tables des données géographiques
        current_geo_dict = get_data.get_current_geo_dict(isin_str)
        new_geo_dict = get_data.get_new_geo_dict(isin_str)
        to_insert, to_update, to_delete = update_db.compare_geo(current_geo_dict, new_geo_dict)
        update_db.update_geo_in_sql_db(isin_str, to_insert, to_update, to_delete)

        # Mise à jour de la tables des données sectorielles
        current_sect_dict = get_data.get_current_sect_dict(isin_str)
        new_sect_dict = get_data.get_new_sect_dict(isin_str)
        to_insert, to_update, to_delete = update_db.compare_sect(current_sect_dict, new_sect_dict)
        update_db.update_sect_in_sql_db(isin_str, to_insert, to_update, to_delete)
    else:
        print(f"⛔ Donnée(s) manquante(s). Impossible de prendre en compte {isin_str}")
    
print("Mise à jour terminée ! ✅")
fin = datetime.now()
temps = fin - début
print("Temps écoulé : " + str(temps))