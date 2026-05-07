import psycopg2
from datetime import datetime
import get_data
from dotenv import load_dotenv
import os


load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def check_isin_etf_static(isin):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM etf_static WHERE isin = %s LIMIT 1;", (isin,))
    exists = cur.fetchone() is not None

    cur.close()
    conn.close()
    return exists


def add_etf_static(isin: str):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    if not check_isin_etf_static(isin):    
        insert_etf = """
        INSERT INTO etf_static (isin, nom, launch_date, replication_type, pol_dividendes, pea)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        nom , launch_date, replication_type, pol_dividendes, pea = get_data.get_etf_static_from_justetf(isin)
        cur.execute(insert_etf, (isin, nom, launch_date, replication_type, pol_dividendes, pea))
        print(f"✅ ETF {isin} mis à jour dans etf_static.")

    else:
        print(f"➡️ L'ISIN {isin} existe déjà dans etf_static. Aucune modification réalisée.")
    
    conn.commit()
    cur.close()
    conn.close()


def update_etf_market_data(isin, prix_part, capitalisation_millions, hist_perf, tracking_diff, euronext, frais_gestion):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    if check_isin_etf_static:   
        insert_etf = """
            INSERT INTO etf_market_data (isin, prix_part, capitalisation_millions, hist_perf, last_update, tracking_diff, euronext, frais_gestion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (isin)
            DO UPDATE SET
                prix_part = EXCLUDED.prix_part,
                capitalisation_millions = EXCLUDED.capitalisation_millions,
                hist_perf = EXCLUDED.hist_perf,
                last_update = EXCLUDED.last_update,
                tracking_diff = EXCLUDED.tracking_diff,
                euronext = EXCLUDED.euronext,
                frais_gestion = EXCLUDED.frais_gestion;
        """
        cur.execute(insert_etf, (isin, prix_part, capitalisation_millions, hist_perf, datetime.now(), -tracking_diff, euronext, frais_gestion))
        print(f"✅ ETF {isin} mis à jour dans etf_market_data.")

    else:
        print(f"➡️  L'ISIN {isin} existe déjà dans etf_market_data. Aucune modification réalisée.")

    conn.commit()
    cur.close()
    conn.close()


def compare_geo(current_geo_dict, new_geo_dict):
    to_insert = []
    to_update = []
    to_delete = []

    # 1) Déterminer les insertions et les mises à jour
    for pays, new_weight in new_geo_dict.items():
        if pays not in current_geo_dict:
            to_insert.append((pays, new_weight))
        else:
            if current_geo_dict[pays] != new_weight:
                to_update.append((pays, new_weight))

    # 2) Déterminer les suppressions
    for pays in current_geo_dict:
        if pays not in new_geo_dict:
            to_delete.append(pays)

    return to_insert, to_update, to_delete


def update_geo_in_sql_db(isin, to_insert, to_update, to_delete):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    # 1) Insérer les nouveaux pays
    if to_insert:
        insert_geo = """
        INSERT INTO etf_geo(isin, pays, poids_pct, last_update)
        VALUES(%s, %s, %s, now())
        """
        for pays, poids_pct in to_insert:
            cur.execute(insert_geo, (isin, pays, poids_pct))

    # 2) Mettre à jour les pays déjà présents
    if to_update:
        update_geo = """
        UPDATE etf_geo
        SET poids_pct = %s, last_update = now()
        WHERE isin = %s AND pays = %s
        """
        for pays, poids_pct in to_update:
            cur.execute(update_geo, (poids_pct, isin, pays))

    # 3) Supprimer les pays plus présents
    if to_delete:
        delete_geo = """
        DELETE FROM etf_geo
        WHERE isin = %s AND pays = %s
        """
        for pays in to_delete:
            cur.execute(delete_geo, (isin, pays))

    print(f"✅ Données géographiques mises à jour pour {isin}.")

    conn.commit()
    cur.close()
    conn.close()


def compare_sect(current_sect_dict, new_sect_dict):
    to_insert = []
    to_update = []
    to_delete = []

    # 1) Déterminer les insertions et les mises à jour
    for secteur, new_weight in new_sect_dict.items():
        if secteur not in current_sect_dict:
            to_insert.append((secteur, new_weight))
        else:
            if current_sect_dict[secteur] != new_weight:
                to_update.append((secteur, new_weight))

    # 2) Déterminer les suppressions
    for secteur in current_sect_dict:
        if secteur not in new_sect_dict:
            to_delete.append(secteur)

    return to_insert, to_update, to_delete


def update_sect_in_sql_db(isin, to_insert, to_update, to_delete):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    # 1) Insérer les nouveaux secteurs
    if to_insert:
        insert_sect = """
        INSERT INTO etf_sect(isin, secteur, poids_pct, last_update)
        VALUES(%s, %s, %s, now())
        """
        for secteur, poids_pct in to_insert:
            cur.execute(insert_sect, (isin, secteur, poids_pct))

    # 2) Mettre à jour les secteurs déjà présents
    if to_update:
        update_sect = """
        UPDATE etf_sect
        SET poids_pct = %s, last_update = now()
        WHERE isin = %s AND secteur = %s
        """
        for secteur, poids_pct in to_update:
            cur.execute(update_sect, (poids_pct, isin, secteur))

    # 3) Supprimer les secteurs plus présents
    if to_delete:
        delete_sect = """
        DELETE FROM etf_sect
        WHERE isin = %s AND secteur = %s
        """
        for secteur in to_delete:
            cur.execute(delete_sect, (isin, secteur))

    print(f"✅ Données sectorielles mises à jour pour {isin}.")

    conn.commit()
    cur.close()
    conn.close()