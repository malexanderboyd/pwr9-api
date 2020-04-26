import json
import os
import random
import re
import secrets
import socket
from collections import defaultdict
from collections import namedtuple
from contextlib import closing
from dataclasses import dataclass

import redis
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

SortedSet = namedtuple(
    "SortedSet", ["basic", "common", "uncommon", "rare", "mythic", "special", "size"]
)


def make_app():
    flask_app = Flask(__name__)
    return flask_app


app = make_app()
CORS(app)

cache_host = "redis" if os.getenv("ENV") == "docker" else os.getenv("REDIS_URL", "")
cache = redis.StrictRedis(host=cache_host, port=6379)


@dataclass
class MTGJSON:
    BASE_URL: str = "https://api.magicthegathering.io/v1"
    VERSION_URL: str = f"{BASE_URL}/files/version.json"
    SETS_URL: str = f"{BASE_URL}/sets"
    BOOSTER_GEN_URL: str = f"{BASE_URL}/sets/{{set_id}}/booster"


@dataclass(init=False)
class MagicCard:
    name: str
    cmc: float
    colors: list
    type: str
    types: list
    rarity: str
    set: str
    text: str
    imageUrl: str = None
    manaCost: str = None

    def __init__(
        self,
        name,
        cmc,
        colors,
        type,
        types,
        rarity,
        set,
        text,
        imageUrl=None,
        manaCost=None,
        **kwargs,
    ):
        self.name = name
        self.manaCost = manaCost
        self.cmc = cmc
        self.colors = colors
        self.type = type
        self.types = types
        self.rarity = rarity
        self.set = set
        self.text = text
        self.imageUrl = imageUrl


@app.route("/cubes")
def cubes():
    try:
        cached_cubes = cache.get("cubes")
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

    cubes = json.loads(cached_cubes.decode("utf-8"))

    return jsonify(cubes)


@app.route("/set/<string:identifier>/pack")
def set_booster(identifier):
    try:

        numPacks = request.args.get("n")

        if numPacks:
            try:
                numPacks = int(numPacks)
            except ValueError:
                numPacks = 1

        packs = []
        for i in range(numPacks or 1):
            res = cache.get(f"set_{identifier.lower()}")
            set = json.loads(res.decode("utf-8"))

            def _is_basic_land(card_typeline) -> bool:
                if not card_typeline:
                    return False
                return "basic land" in card_typeline.lower()

            def is_english_card(card_lang) -> bool:
                return card_lang.lower() == "en" if card_lang else True

            def sort_set(set: list) -> SortedSet:

                _sorted_set = defaultdict(list)
                for card in set:
                    if not _is_basic_land(
                        card.get("type", card.get("type_line"))
                    ) and is_english_card(card.get("lang")):
                        _sorted_set[card.get("rarity")].append(card)

                return SortedSet(
                    basic=_sorted_set.get("basic"),
                    common=_sorted_set.get("common"),
                    uncommon=_sorted_set.get("uncommon"),
                    rare=_sorted_set.get("rare"),
                    mythic=_sorted_set.get("mythic"),
                    special=_sorted_set.get("special"),
                    size=len(set),
                )

            sorted_set = sort_set(set)
            if not sorted_set.rare:
                sorted_set = sorted_set._replace(rare=sorted_set.uncommon)

            # 11 commons, 3 uncommons, either 1 rare (7 / 8 chance) or 1 mythic rare
            pack = [] + random.choices(sorted_set.uncommon, k=3)
            pack = pack + random.choices(sorted_set.common, k=11)
            if random.randint(0, 8) == 0 and len(sorted_set.mythic) > 0:
                pack = pack + random.choices(sorted_set.mythic, k=1)
            else:
                pack = pack + random.choices(sorted_set.rare, k=1)

            while len(pack) < 15:
                pack = pack + random.choices(sorted_set.common, k=1)
            packs.append(pack)
        return jsonify(dict(packs=packs))
    except Exception as e:
        abort(500, str(e))


@app.route("/sets")
def sets():
    try:
        cached_sets = cache.get("sets")
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

    set_blocks = json.loads(cached_sets.decode("utf-8"))

    return jsonify(set_blocks)


@app.route("/game/<string:game_id>")
def game_info(game_id):
    try:
        cached_game_options = cache.get(f"game_{game_id}")
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

    if cached_game_options is None:
        abort(404)

    game_options = json.loads(cached_game_options.decode("utf-8"))

    return jsonify(game_options)


def store_game_info(game_id, game_port, game_options):
    game_options["port"] = game_port
    game_options["gameId"] = game_id
    try:
        cache.lpush(f"game_queue", json.dumps(game_options))
        cache.set(f"game_{game_id}", json.dumps(game_options))
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
    return True


@app.route("/game", methods=["POST"])
def create_game():
    if request.is_json:
        game_options = request.get_json()
        print(f"Starting new game: {game_options}")
        game_id = secrets.token_urlsafe(4)
        game_port = find_available_port()
        if store_game_info(game_id, game_port, game_options):
            return jsonify(dict(url=f"/draft/g/{game_id}"))
        else:
            abort(400, "Unable to start game")
    else:
        abort(400, "Must send JSON")


def find_available_port():
    next_port = cache.get("next_port").decode("utf-8")
    cache.incr("next_port")
    return next_port


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv("PORT", 8002))
