import math
import re
import unicodedata

POLISH_TRANSLATION = str.maketrans({
    "ą": "a",
    "ć": "c",
    "ę": "e",
    "ł": "l",
    "ń": "n",
    "ó": "o",
    "ś": "s",
    "ź": "z",
    "ż": "z",
    "Ą": "a",
    "Ć": "c",
    "Ę": "e",
    "Ł": "l",
    "Ń": "n",
    "Ó": "o",
    "Ś": "s",
    "Ź": "z",
    "Ż": "z",
})


def normalize_location(value):
    if not value:
        return ""

    text = str(value).strip().translate(POLISH_TRANSLATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


PROVINCES = {
    "dolnoslaskie": "dolnośląskie",
    "kujawsko pomorskie": "kujawsko-pomorskie",
    "lubelskie": "lubelskie",
    "lubuskie": "lubuskie",
    "lodzkie": "łódzkie",
    "malopolskie": "małopolskie",
    "mazowieckie": "mazowieckie",
    "opolskie": "opolskie",
    "podkarpackie": "podkarpackie",
    "podlaskie": "podlaskie",
    "pomorskie": "pomorskie",
    "slaskie": "śląskie",
    "swietokrzyskie": "świętokrzyskie",
    "warminsko mazurskie": "warmińsko-mazurskie",
    "wielkopolskie": "wielkopolskie",
    "zachodniopomorskie": "zachodniopomorskie",
}


CITY_DATA = {
    "warszawa": {"city": "Warszawa", "latitude": 52.2297, "longitude": 21.0122, "province": "mazowieckie", "region": "warszawski"},
    "krakow": {"city": "Kraków", "latitude": 50.0647, "longitude": 19.9450, "province": "małopolskie", "region": "krakowski"},
    "wroclaw": {"city": "Wrocław", "latitude": 51.1079, "longitude": 17.0385, "province": "dolnośląskie", "region": "wrocławski"},
    "poznan": {"city": "Poznań", "latitude": 52.4064, "longitude": 16.9252, "province": "wielkopolskie", "region": "poznański"},
    "gdansk": {"city": "Gdańsk", "latitude": 54.3520, "longitude": 18.6466, "province": "pomorskie", "region": "trójmiejski"},
    "gdynia": {"city": "Gdynia", "latitude": 54.5189, "longitude": 18.5305, "province": "pomorskie", "region": "trójmiejski"},
    "sopot": {"city": "Sopot", "latitude": 54.4416, "longitude": 18.5601, "province": "pomorskie", "region": "trójmiejski"},
    "lodz": {"city": "Łódź", "latitude": 51.7592, "longitude": 19.4560, "province": "łódzkie", "region": "łódzki"},
    "katowice": {"city": "Katowice", "latitude": 50.2649, "longitude": 19.0238, "province": "śląskie", "region": "górnośląski"},
    "chorzow": {"city": "Chorzów", "latitude": 50.2975, "longitude": 18.9546, "province": "śląskie", "region": "górnośląski"},
    "tychy": {"city": "Tychy", "latitude": 50.1218, "longitude": 19.0200, "province": "śląskie", "region": "górnośląski"},
    "sosnowiec": {"city": "Sosnowiec", "latitude": 50.2863, "longitude": 19.1041, "province": "śląskie", "region": "zagłębiowski"},
    "gliwice": {"city": "Gliwice", "latitude": 50.2945, "longitude": 18.6714, "province": "śląskie", "region": "górnośląski"},
    "zabrze": {"city": "Zabrze", "latitude": 50.3249, "longitude": 18.7857, "province": "śląskie", "region": "górnośląski"},
    "bytom": {"city": "Bytom", "latitude": 50.3480, "longitude": 18.9328, "province": "śląskie", "region": "górnośląski"},
    "ruda slaska": {"city": "Ruda Śląska", "latitude": 50.2558, "longitude": 18.8556, "province": "śląskie", "region": "górnośląski"},
    "bielsko biala": {"city": "Bielsko-Biała", "latitude": 49.8224, "longitude": 19.0584, "province": "śląskie", "region": "beskidzki"},
    "czestochowa": {"city": "Częstochowa", "latitude": 50.8118, "longitude": 19.1203, "province": "śląskie", "region": "częstochowski"},
    "lublin": {"city": "Lublin", "latitude": 51.2465, "longitude": 22.5684, "province": "lubelskie", "region": "lubelski"},
    "rzeszow": {"city": "Rzeszów", "latitude": 50.0413, "longitude": 21.9990, "province": "podkarpackie", "region": "rzeszowski"},
    "kielce": {"city": "Kielce", "latitude": 50.8661, "longitude": 20.6286, "province": "świętokrzyskie", "region": "kielecki"},
    "bialystok": {"city": "Białystok", "latitude": 53.1325, "longitude": 23.1688, "province": "podlaskie", "region": "białostocki"},
    "szczecin": {"city": "Szczecin", "latitude": 53.4285, "longitude": 14.5528, "province": "zachodniopomorskie", "region": "szczeciński"},
    "torun": {"city": "Toruń", "latitude": 53.0138, "longitude": 18.5984, "province": "kujawsko-pomorskie", "region": "toruński"},
    "bydgoszcz": {"city": "Bydgoszcz", "latitude": 53.1235, "longitude": 18.0084, "province": "kujawsko-pomorskie", "region": "bydgoski"},
    "olsztyn": {"city": "Olsztyn", "latitude": 53.7784, "longitude": 20.4801, "province": "warmińsko-mazurskie", "region": "olsztyński"},
    "zielona gora": {"city": "Zielona Góra", "latitude": 51.9356, "longitude": 15.5062, "province": "lubuskie", "region": "zielonogórski"},
    "gorzow wielkopolski": {"city": "Gorzów Wielkopolski", "latitude": 52.7368, "longitude": 15.2288, "province": "lubuskie", "region": "gorzowski"},
    "opole": {"city": "Opole", "latitude": 50.6751, "longitude": 17.9213, "province": "opolskie", "region": "opolski"},
    "radom": {"city": "Radom", "latitude": 51.4027, "longitude": 21.1471, "province": "mazowieckie", "region": "radomski"},
    "tarnow": {"city": "Tarnów", "latitude": 50.0121, "longitude": 20.9858, "province": "małopolskie", "region": "tarnowski"},
    "rybnik": {"city": "Rybnik", "latitude": 50.1022, "longitude": 18.5463, "province": "śląskie", "region": "rybnicki"},
    "dabrowa gornicza": {"city": "Dąbrowa Górnicza", "latitude": 50.3217, "longitude": 19.1949, "province": "śląskie", "region": "zagłębiowski"},
}


def normalize_province(value):
    normalized = normalize_location(value)
    return PROVINCES.get(normalized, normalized)


def get_city_info(value):
    normalized = normalize_location(value)
    if not normalized:
        return None
    if normalized in CITY_DATA:
        return CITY_DATA[normalized]

    for city_key, info in CITY_DATA.items():
        if normalized in city_key or city_key in normalized:
            return info
    return None


def enrich_location(value):
    normalized = normalize_location(value)
    info = get_city_info(value) or {}
    return {
        "location_normalized": normalized,
        "latitude": info.get("latitude"),
        "longitude": info.get("longitude"),
        "region": info.get("region"),
        "province": info.get("province"),
    }


def distance_km(lat1, lon1, lat2, lon2):
    if None in {lat1, lon1, lat2, lon2}:
        return None

    radius = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)
