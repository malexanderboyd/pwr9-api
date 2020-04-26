import requests


res = requests.get("http://localhost:8002/sets")

sets = res.json()

missing = set()
there = set()

for set in sets:
    print(set)
    booster_types = sets[set]
    for booster_info in booster_types:
        bid = booster_info.get("id").lower()
        print(bid)
        x = requests.get(f"http://localhost:8002/set/{bid}/pack")
        if not x.ok:
            missing.add(bid)
        else:
            try:
                z = x.json()
                there.add(bid)
            except Exception as e:
                pass


print(f"{missing=}")
print(f"{there=}")
