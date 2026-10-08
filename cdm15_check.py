import mmap
import struct
from pathlib import Path

path = Path(
    "/home/skunkhen/Documents/SiPM-tools/"
    "s0534+2201_466_flashCAL_09032026_1_EVBdata.eve"
)

TARGET_CDM = 15
TARGET_DDB = 0

events = []
temperatures = []

with path.open("rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    file_size = len(mm)
    pos = 0
    packets = 0

    while pos + 24 <= file_size:
        # Word 1
        word1 = struct.unpack_from("<I", mm, pos)[0]

        # Lower 16 bits = packet size in words
        packet_words = word1 & 0xFFFF

        if packet_words < 6:
            print("Invalid packet size:", packet_words)
            break

        packet_bytes = packet_words * 4

        if pos + packet_bytes > file_size:
            print("Packet extends beyond end of file.")
            break

        # Word 3 = event number
        event_number = struct.unpack_from(
            "<I", mm, pos + 8
        )[0]

        # Word 6
        word6 = struct.unpack_from(
            "<I", mm, pos + 20
        )[0]

        # Exact bit fields
        temperature_raw = word6 & 0x1FFF
        ddb_id = (word6 >> 16) & 0x03
        cdm_id = (word6 >> 18) & 0x1F

        if cdm_id == TARGET_CDM and ddb_id == TARGET_DDB:
            temperature_c = temperature_raw / 16.0

            events.append(event_number)
            temperatures.append(temperature_c)

        packets += 1
        pos += packet_bytes

    mm.close()


print()
print("=" * 60)
print("RAW EVB CHECK: CDM 15 / DDB 0")
print("=" * 60)

print(f"File size       : {file_size:,} bytes")
print(f"Packets scanned : {packets:,}")
print(f"Records found   : {len(events):,}")

if not events:
    print()
    print("NO CDM 15 / DDB 0 RECORDS FOUND.")
    raise SystemExit

print(f"First event     : {events[0]}")
print(f"Last event      : {events[-1]}")

print()
print("First 10 records:")
for event, temp in list(zip(events, temperatures))[:10]:
    print(f"  Event {event:5d} : {temp:8.4f} °C")

print()
print("Last 10 records:")
for event, temp in list(zip(events, temperatures))[-10:]:
    print(f"  Event {event:5d} : {temp:8.4f} °C")

print()
print("Selected events:")

for target in [
    1,
    100,
    500,
    1000,
    1500,
    2000,
    2100,
    2200,
    2300,
    2400,
    2500,
]:
    found = [
        temp
        for event, temp in zip(events, temperatures)
        if event == target
    ]

    if found:
        print(f"  Event {target:5d} : {found[0]:8.4f} °C")
    else:
        print(f"  Event {target:5d} : MISSING")

print()
print("=" * 60)