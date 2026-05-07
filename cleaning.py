import re

def extract_cap_value(valeur_brute: str):
    if valeur_brute is None:
        return None
    
    valeur_digits_only = re.sub(r"\D", "", valeur_brute)
    return valeur_digits_only

def extract_frais_value(valeur_brute: str):
    if valeur_brute is None:
        return None
    
    valeur_num_only_str = re.search(r"([\d.,]+)\s*%", valeur_brute).group(1)
    valeur_num_only = valeur_num_only_str.replace(',','.')
    return valeur_num_only