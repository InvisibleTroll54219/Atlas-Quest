#!/usr/bin/env python3
"""Add a deterministic set of GeoNames populated-place questions to the fact bank."""

import csv
import io
import json
import random
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "data" / "facts.json"
GEONAMES_BASE_URL = "https://download.geonames.org/export/dump/"
CONTINENTS = {
    "AF": (0, "Africa"),
    "AS": (1, "Asia"),
    "EU": (2, "Europe"),
    "NA": (3, "North America"),
    "SA": (4, "South America"),
    "OC": (5, "Oceania"),
}
CITY_FACTS_PER_CONTINENT = 792
WORLD_CITY_FACTS = 1584


def download(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def read_country_data():
    country_text = download(GEONAMES_BASE_URL + "countryInfo.txt").decode("utf-8")
    country_names = {}
    countries_by_continent = {}
    continents = {}
    for row in csv.reader(io.StringIO(country_text), delimiter="\t"):
        if not row or row[0].startswith("#"):
            continue
        code, country_name, continent = row[0], row[4], row[8]
        country_names[code] = country_name
        continents[code] = continent
        countries_by_continent.setdefault(continent, set()).add(country_name)

    admin_text = download(GEONAMES_BASE_URL + "admin1CodesASCII.txt").decode("utf-8")
    admin_names = {}
    for row in csv.reader(io.StringIO(admin_text), delimiter="\t"):
        if len(row) >= 2:
            admin_names[row[0]] = row[1]
    return country_names, countries_by_continent, continents, admin_names


def read_cities(country_names, continents):
    archive_data = download(GEONAMES_BASE_URL + "cities5000.zip")
    cities = []
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        with archive.open("cities5000.txt") as city_file:
            text = io.TextIOWrapper(city_file, encoding="utf-8")
            for row in csv.reader(text, delimiter="\t"):
                if len(row) < 19 or row[8] not in country_names:
                    continue
                continent = continents.get(row[8])
                if continent not in CONTINENTS:
                    continue
                try:
                    population = int(row[14])
                    geoname_id = int(row[0])
                except ValueError:
                    continue
                cities.append(
                    {
                        "geoname_id": geoname_id,
                        "name": row[1],
                        "country_code": row[8],
                        "admin_code": row[8] + "." + row[10] if row[10] else "",
                        "latitude": float(row[4]),
                        "longitude": float(row[5]),
                        "population": population,
                        "continent_code": continent,
                    }
                )
    return cities


def _ordered_cities(cities):
    return sorted(cities, key=lambda city: (-city["population"], city["geoname_id"]))


def _coordinates(value, positive, negative):
    hemisphere = positive if value >= 0 else negative
    return "{:.2f}°{}".format(abs(value), hemisphere)


def make_city_fact(city, level, continent, country_names, distractor_names, admin_names):
    country = country_names[city["country_code"]]
    region = admin_names.get(city["admin_code"])
    if region and region.casefold() == city["name"].casefold():
        region = None
    if region:
        prompt = "Which country is home to {}, in {}?".format(city["name"], region)
        location = region
    else:
        latitude = _coordinates(city["latitude"], "N", "S")
        longitude = _coordinates(city["longitude"], "E", "W")
        prompt = "Which country is home to {}, near {} {}?".format(
            city["name"], latitude, longitude
        )
        location = "near {} {}".format(latitude, longitude)

    choices = [name for name in distractor_names if name != country]
    rng = random.Random(city["geoname_id"])
    options = [country] + rng.sample(sorted(choices), 3)
    return {
        "id": "GN-{}".format(city["geoname_id"]),
        "level": level,
        "continent": continent,
        "name": "{} Explorer".format(continent),
        "region": continent,
        "icon": {
            "Africa": "🌍",
            "Asia": "🌏",
            "Europe": "🏰",
            "North America": "🗽",
            "South America": "🌎",
            "Oceania": "🏝️",
            "World": "🌐",
        }[continent],
        "prompt": prompt,
        "options": options,
        "answer_index": 0,
        "explanation": "{} is a populated place in {}, {}.".format(
            city["name"], location, country
        ),
        "source": "GeoNames",
        "geoname_id": city["geoname_id"],
    }


def build_facts(existing_facts, cities, country_names, countries_by_continent, admin_names):
    authored_facts = [fact for fact in existing_facts if fact.get("source") != "GeoNames"]
    cities_by_continent = {}
    for city in cities:
        cities_by_continent.setdefault(city["continent_code"], []).append(city)

    selected = []
    selected_ids = set()
    for code, (level, continent) in CONTINENTS.items():
        choices = _ordered_cities(cities_by_continent.get(code, []))
        if len(choices) < CITY_FACTS_PER_CONTINENT:
            raise ValueError(
                "GeoNames only supplied {} eligible {} places; {} are required.".format(
                    len(choices), continent, CITY_FACTS_PER_CONTINENT
                )
            )
        continent_countries = countries_by_continent[code]
        if len(continent_countries) < 4:
            raise ValueError("At least four country choices are required for {}.".format(continent))
        selected.extend(
            make_city_fact(
                city,
                level,
                continent,
                country_names,
                continent_countries,
                admin_names,
            )
            for city in choices[:CITY_FACTS_PER_CONTINENT]
        )
        selected_ids.update(city["geoname_id"] for city in choices[:CITY_FACTS_PER_CONTINENT])

    world_countries = set(country_names.values())
    remaining_cities = _ordered_cities(
        [city for city in cities if city["geoname_id"] not in selected_ids]
    )
    if len(remaining_cities) < WORLD_CITY_FACTS:
        raise ValueError(
            "GeoNames only supplied {} additional places for the World Challenge; {} are required.".format(
                len(remaining_cities), WORLD_CITY_FACTS
            )
        )
    selected.extend(
        make_city_fact(
            city,
            7,
            "World",
            country_names,
            world_countries,
            admin_names,
        )
        for city in remaining_cities[:WORLD_CITY_FACTS]
    )
    result = authored_facts + selected
    if len(result) != 6400 or len({fact["id"] for fact in result}) != 6400:
        raise ValueError("The imported fact bank must contain exactly 6,400 distinct facts.")
    return result


def main():
    existing_facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    country_names, countries_by_continent, continents, admin_names = read_country_data()
    cities = read_cities(country_names, continents)
    facts = build_facts(
        existing_facts,
        cities,
        country_names,
        countries_by_continent,
        admin_names,
    )
    FACTS_PATH.write_text(
        "[\n  "
        + ",\n  ".join(
            json.dumps(fact, ensure_ascii=False, separators=(",", ":"))
            for fact in facts
        )
        + "\n]\n",
        encoding="utf-8",
    )
    print("Wrote {:,} distinct facts to {}".format(len(facts), FACTS_PATH))


if __name__ == "__main__":
    main()
