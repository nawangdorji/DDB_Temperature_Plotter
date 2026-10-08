from pathlib import Path

from evb_reader import EVBReader


path = Path(
    "/home/skunkhen/Documents/SiPM-tools/"
    "s0534+2201_466_flashCAL_09032026_1_EVBdata.eve"
)

reader = EVBReader()
data = reader.read_file(path)

print()
print("=" * 70)
print("CDM 15 — ALL FOUR DDB SERIES")
print("=" * 70)

for ddb_id in range(4):
    points = data[15][ddb_id]

    print()
    print(f"DDB {ddb_id}")
    print("-" * 70)
    print(f"Number of records : {len(points):,}")
    print(f"First event       : {points[0].event}")
    print(f"Last event        : {points[-1].event}")

    print()
    print("Selected events:")

    wanted = {1, 2, 3, 100, 500, 1000, 1500, 2000, 2100, 2200, 2300, 2400, 2500}

    for point in points:
        if point.event in wanted:
            print(
                f"  Event {point.event:5d} : "
                f"{point.temperature:8.4f} °C"
            )

print()
print("=" * 70)
print("END")
print("=" * 70)