from datetime import datetime
import pathlib
from collections import defaultdict

import requests
import os
import json
from dataclasses import dataclass, asdict, field
import redis

cache_host = os.getenv("REDIS_URL", "localhost")
cache = redis.StrictRedis(host=cache_host, port=6379)


@dataclass
class MTGJSONVersion:
    date: str  # When all files were last completely built. (All data is updated)
    pricesDate: str  # When card prices were updated on cards. (Prices data is updated)
    version: str  # What version all files are on. (Updates with pricesDate)


@dataclass
class PWR9Version:
    server: str
    client: str
    mtg_json: MTGJSONVersion = field(default_factory=MTGJSONVersion)


def get_version():
    try:
        res = requests.get(MTGJSON.VERSION_URL)
        if res.ok:
            response = MTGJSONVersion(**res.json())
            return response
    except (requests.exceptions.Timeout, requests.exceptions.RetryError):
        print(f"MTGJSON timed out; will try again tomorrow")
    except Exception as e:
        print(e)
    return None


def get_cached_version():
    try:
        cached_version = cache.get("sets_version")
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as ce:
        print(f"error connecting to cache: {ce}")
        return None
    except redis.exceptions.AuthenticationError as ae:
        print(f"unable to authenticate with cache: {ae}")
        return None
    except redis.exceptions.RedisError as re:
        print(f"redis error: {re}")
        return None
    except Exception as e:
        print(f"exception during version retrieval: {e}")
        return None
    finally:
        cache.close()

    if not cached_version:
        return None

    try:
        version_info = json.loads(cached_version.decode("utf-8"))
        return PWR9Version(
            mtg_json=MTGJSONVersion(**version_info.get("mtg_json", {})),
            client=version_info.get("client"),
            server=version_info.get("server"),
        )
    except json.JSONDecodeError:
        print(f'Error decoding cached redis json: {cached_version.decode("utf-8")}')
        return None
    except Exception as e:
        print(f"exception during version retrieval: {e}")
        return None


@dataclass
class MTGJSON:
    BASE_URL: str = "https://www.mtgjson.com"
    VERSION_URL: str = f"{BASE_URL}/files/version.json"
    SETS_URL: str = f"{BASE_URL}/files/AllPrintings.json"
    SET_URL: str = f"{BASE_URL}/json/{id}.json"
    BOOSTER_GEN_URL: str = f"{BASE_URL}/sets/{{set_id}}/booster"


PWR9 = dict(BASE_URL="localhost:8002", REDIS_URL="localhost:6379")


def update_to_mtg_json_version(version: MTGJSONVersion):
    server_version = "0.1.0"  # TODO: reach out to server for version
    client_version = "0.1.0"  # TODO: reach out to client for version

    new_version = PWR9Version(
        mtg_json=version, server=server_version, client=client_version
    )

    try:
        cache.set("version", json.dumps(asdict(new_version)))
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as ce:
        print(f"error connecting to cache: {ce}")
        return None
    except redis.exceptions.AuthenticationError as ae:
        print(f"unable to authenticate with cache: {ae}")
        return None
    except redis.exceptions.RedisError as re:
        print(f"redis error: {re}")
        return None
    except Exception as e:
        print(f"exception during version retrieval: {e}")
        return None
    finally:
        cache.close()


def download_new_mtg_sets():
    try:
        res = requests.get(MTGJSON.SETS_URL)
        if res.ok:
            sets = res.json()
            set_blocks = defaultdict(list)
            for set_id, set_info in sets.items():
                block = set_info.get("block", "Extras")
                set_blocks[block].append(
                    dict(
                        name=set_info.get("name"),
                        id=set_id,
                        cards=set_info.get("cards"),
                    )
                )
            return set_blocks
    except (requests.exceptions.Timeout, requests.exceptions.RetryError):
        print(f"MTGJSON timed out; will try again tomorrow")
    except Exception as e:
        print(e)
    return None


def cache_data(key: str, json_data: dict):
    try:
        cache.set(key, json.dumps(json_data))
        print(f"Updated {key} cache")
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as ce:
        print(f"error connecting to cache: {ce}")
        return None
    except redis.exceptions.AuthenticationError as ae:
        print(f"unable to authenticate with cache: {ae}")
        return None
    except redis.exceptions.RedisError as re:
        print(f"redis error: {re}")
        return None
    except Exception as e:
        print(f"exception during version retrieval: {e}")
        return None
    finally:
        cache.close()


def download_set_cards(sets: dict):
    set_cards = {}
    for set_boosters in sets.values():
        for booster in set_boosters:
            booster_id = booster.get("id")
            try:
                res = requests.get(MTGJSON.SET_URL.format(id=booster_id))
                if res.ok:
                    set_cards[booster_id] = res.json().get("cards")
            except (requests.exceptions.Timeout, requests.exceptions.RetryError):
                print(f"MTGJSON timed out; will try again tomorrow")
                break
            except Exception as e:
                print(e)
                break
    return set_cards


mtg_version = get_version()
# mtg_set_data = download_new_mtg_sets()
#
# with open(
#     pathlib.Path("data").joinpath(
#         f"sets-{datetime.now().isoformat()}-{mtg_version.version}.json"
#     ),
#     "w",
# ) as sets_file:
#     sets_file.write(json.dumps(mtg_set_data))

# for set, blocks in mtg_set_data.items():
#     for i, block in enumerate(blocks):
#         cache_data(f"set_{block.get('id').lower()}", block.get("cards"))
#         del mtg_set_data[set][i]["cards"]
#
# cache_data("sets", mtg_set_data)


cache_data("sets_version", asdict(mtg_version))

with open(pathlib.Path("data").joinpath("cubes.json"), "r") as cubes_file:
    cache_data("cubes", json.load(cubes_file))
