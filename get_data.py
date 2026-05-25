import requests
import os
import re
import psycopg2
import random
import time
import yfinance as yf
from bs4 import BeautifulSoup
from cleaning import (extract_cap_value, extract_frais_value)
from update_db import (update_etf_market_data, check_isin_etf_static)


def get_price_from_yfinance(ticker: str):

    t = yf.Ticker(ticker)
    prix_part = t.history(period="5d")["Close"].iloc[-1]
    prix_part = float(prix_part)
    if prix_part is None:
        print(f"⛔ Impossible de récupérer le prix pour {ticker}")
        return None

    return prix_part


def get_cap_from_justetf(isin: str):
    url = f"https://www.justetf.com/fr/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"⛔ Impossible de charger la page JustETF pour {isin}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    
    capitalisation_brute = soup.find("div", {"data-testid": "etf-profile-header_fund-size-value-wrapper"})
    if capitalisation_brute :
        capitalisation_brute = capitalisation_brute.get_text(strip=True)
        capitalisation = extract_cap_value(capitalisation_brute)
    else:
        capitalisation = None

    return capitalisation


def get_etf_static_from_justetf(isin):
    time.sleep(1 + random.uniform(0.4, 0.8))

    url = f"https://www.justetf.com/fr/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"⛔ Impossible de charger la page JustETF pour {isin}")

    soup = BeautifulSoup(r.text, "html.parser")

    # 1) Récupérer le nom
    nom_brut = soup.find("h1", {"data-testid":"etf-profile-header_etf-name"})
    if nom_brut:
        nom = nom_brut.get_text(strip=True)
    else:
        nom = None

    # 2) Récupérer l'année de lancement
    complete_launch_date_brut = soup.find("div", {"data-testid":"etf-profile-header_inception-date-value"})
    if complete_launch_date_brut:
        launch_date_brut = complete_launch_date_brut.get_text(strip=True)
        launch_date = int(launch_date_brut[-4:])
    else:
        launch_date = None

    # 3) Récupérer le type de réplication
    replication_type_brut = soup.find("div", {"data-testid":"etf-profile-header_replication-value"})
    if replication_type_brut:
        replication_type = replication_type_brut.get_text(strip=True)
    else:
        replication_type = None

    # 4) Récupérer la politique de dividendes
    pol_dividendes_brut = soup.find("div", {"data-testid":"etf-profile-header_distribution-policy-value"})
    if pol_dividendes_brut:
        pol_dividendes = pol_dividendes_brut.get_text(strip=True)
    else:
        pol_dividendes = None

    # 5) Récupérer l'éligibilité au PEA
    elig_PEA_brut = soup.find("span", {"data-testid":"etf-profile-controls_pea-label-text"})
    if elig_PEA_brut:
        elig_PEA = elig_PEA_brut.get_text(strip=True)
    else:
        elig_PEA = "Non éligible au PEA"

    return nom, launch_date, replication_type, pol_dividendes, elig_PEA


def refresh_etf(isin: str, ticker: str):

    # 1) Vérifier que l'ISIN existe dans etf_static
    if not check_isin_etf_static(isin):
        print(f"⛔ ISIN {isin} absent de etf_static : mise à jour annulée.")
        return

    # 2) Récupérer les données
    prix_part = get_price_from_yfinance(ticker)
    capitalisation = get_cap_from_justetf(isin)
    tracking_diff = get_tracking_diff(isin)
    hist_perf = get_hist_perf(isin)
    euronext = get_euronext_from_justetf(isin)
    frais_gestion = get_ter_from_justetf(isin)

    if prix_part != None and capitalisation != None and hist_perf != None and tracking_diff != None and euronext != None and frais_gestion != None:
        update_etf_market_data(isin, prix_part, capitalisation, hist_perf, tracking_diff, euronext, frais_gestion)
        return True
    else:
        return False


def get_current_geo_dict(isin):
    conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
    )

    cur = conn.cursor()

    current_geo = """
        SELECT pays, poids_pct
        FROM etf_geo
        WHERE isin = %s
    """
    cur.execute(current_geo, (isin,))
    current_geo_list = cur.fetchall()
    current_geo_dict = {pays: poids for pays, poids in current_geo_list}

    conn.commit()
    cur.close()
    conn.close()

    return current_geo_dict


def extract_countries_section_ExtraETF(html):

    soup = BeautifulSoup(html, "html.parser")

    # Trouver le h2 "Allocation par pays"
    start_h2 = soup.find("h2", string=lambda t: t and "Allocation par pays" in t)
    if not start_h2:
        return None

    # Remonter au conteneur <div class="card">
    card = start_h2.find_parent("div", class_="card")
    if not card:
        return None
    
    return BeautifulSoup(str(card), "html.parser")


def get_new_geo_dict(isin):
    url = f"https://extraetf.com/fr/etf-profile/{isin}?tab=components"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"⛔ Impossible de charger la page ExtraETF (actualisation géographique) pour {isin}")
    
    countries_section = extract_countries_section_ExtraETF(r.text)

    if countries_section is None:
        return {}
    
    countries = {}

    # Chaque pays est dans un bloc <div class="item ng-star-inserted">
    items = countries_section.find_all("div", class_="item")

    for item in items:
        # Nom du pays
        name_tag = item.find("span")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        # Pourcentage
        value_tag = item.find("div", class_="value-block")
        if not value_tag:
            continue

        value_text = value_tag.get_text(strip=True)
        value_text = value_text.replace("%", "").replace(",", ".")
        try:
            value = float(value_text)
        except ValueError:
            continue

        countries[name] = value

    return countries


def get_current_sect_dict(isin):
    conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
    )

    cur = conn.cursor()

    current_sect = """
        SELECT secteur, poids_pct
        FROM etf_sect
        WHERE isin = %s
    """
    cur.execute(current_sect, (isin,))
    current_sect_list = cur.fetchall()
    current_sect_dict = {pays: poids for pays, poids in current_sect_list}

    conn.commit()
    cur.close()
    conn.close()

    return current_sect_dict


def extract_sectors_section_ExtraETF(html):

    soup = BeautifulSoup(html, "html.parser")

    # Trouver le h2 "Secteurs d'activité"
    start_h2 = soup.find("h2", string=lambda t: t and "Secteurs d'activité" in t)
    if not start_h2:
        return None

    # Remonter au conteneur <div class="card">
    card = start_h2.find_parent("div", class_="card")
    if not card:
        return None
    
    return BeautifulSoup(str(card), "html.parser")


def get_new_sect_dict(isin):
    url = f"https://extraetf.com/fr/etf-profile/{isin}?tab=components"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"⛔ Impossible de charger la page ExtraETF (actualisation sectorielle) pour {isin}")
    
    sectors_section = extract_sectors_section_ExtraETF(r.text)

    if sectors_section is None:
        return {}
    
    sectors = {}

    # Chaque secteur est dans un bloc <div class="item ng-star-inserted">
    items = sectors_section.find_all("div", class_="item")

    if not items:
        return {}

    for item in items:
        # Secteurs
        name_tag = item.find("span")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        # Pourcentage
        value_tag = item.find("div", class_="value-block")
        if not value_tag:
            continue

        value_text = value_tag.get_text(strip=True)
        value_text = value_text.replace("%", "").replace(",", ".")
        try:
            value = float(value_text)
        except ValueError:
            continue

        sectors[name] = value

    return sectors


def page_exists_on_trackingdifferences(isin):
    url = f"https://www.trackingdifferences.com/ETF/ISIN/{isin}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return False

    # Vérifier que l'ISIN apparaît dans la page
    if isin not in r.text:
        return False
    
    return True


def get_tracking_diff(isin):
    url = f"https://trackingdifferences.com/ETF/ISIN/{isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200 or not page_exists_on_trackingdifferences(isin):
        print(f"⛔ Impossible de récupérer la Tracking Difference pour {isin}")
        return None

    # Trouver le texte "avg. TD" ou "durschschn. TD"
    match = re.search(r"name\s*:\s*'(avg\. TD|durchschn\. TD)'\s*,\s*data\s*:\s*\[([0-9\.,\-]+)\]", r.text, re.DOTALL)

    # Extraire la liste des valeurs
    if match != None:
        raw_values = match.group(2).split(",")

        # Filtrer les valeurs vides
        values = [float(v) for v in raw_values if v.strip()]

        if values:
            tracking_diff = values[0]
            return tracking_diff
    else:
        return None


def get_hist_perf(isin):
    url = f"https://extraetf.com/fr/etf-profile/{isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"⛔ Impossible de récupérer la parformance historique pour {isin}")
        return None
    
    pos = r.text.find("Depuis l'édition")
    if pos == -1:
        return None

    snippet = r.text[pos - 500 : pos + 2000]
    soup = BeautifulSoup(snippet, "html.parser")

    # 1) Trouver le label "Depuis l'édition"
    label = soup.find(text=re.compile("Depuis l'édition"))
    if not label:
        return None
    
    # 2) Trouver le span juste après
    hist_perf_brut = label.find_next("span", {"class":"perf-period-pa ng-star-inserted"})

    if not hist_perf_brut:
        return None
    
    if hist_perf_brut:
        hist_perf_str = hist_perf_brut.get_text(strip=True)
        hist_perf = extract_frais_value(hist_perf_str)
    else:
        hist_perf = None

    return hist_perf


def get_euronext_from_justetf(isin: str):
    time.sleep(1.5 + random.uniform(0.2, 0.8))

    url = f"https://www.justetf.com/fr/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"⛔ Impossible de savoir si l'ETF {isin} est coté sur Euronext")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    html_txt = soup.get_text().lower()
    
    if "euronext" in html_txt:
        return "Oui"
    else:
        return "Non"
    
def get_ter_from_justetf(isin):
    url = f"https://www.justetf.com/fr/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"⛔ Impossible de récupérer les frais de gestion pour l'ETF {isin}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    frais_brut = soup.find("div", {"data-testid":"etf-profile-header_ter-value"})
    if frais_brut:
        frais_brut = frais_brut.get_text(strip=True)
        frais_gestion = extract_frais_value(frais_brut)
    else:
        frais_gestion = None

    return frais_gestion