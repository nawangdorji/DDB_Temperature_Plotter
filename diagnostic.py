import struct

filename = "/home/skunkhen/Documents/SiPM-tools/s0534+2201_466_flashCAL_09032026_1_EVBdata.eve"

temperatures = {}

with open(filename, "rb") as f:

    for packet_no in range(1, 65):

        data = f.read(4)

        if len(data) != 4:
            print("Unexpected EOF")
            break

        word1 = struct.unpack("<I", data)[0]

        packet_words = word1 & 0xFFFF

        rest = f.read((packet_words - 1) * 4)

        if len(rest) != (packet_words - 1) * 4:
            print("Incomplete packet")
            break

        words = struct.unpack(
            f"<{packet_words - 1}I",
            rest
        )

        event_number = words[1]
        word6 = words[4]

        temperature_raw = word6 & 0x1FFF
        ddb_id = (word6 >> 16) & 0x03
        cdm_id = (word6 >> 18) & 0x1F

        temperature_c = temperature_raw / 16.0

        temperatures[(cdm_id, ddb_id)] = temperature_c

print()
print(f"Event number: {event_number}")
print()

print("             DDB 0    DDB 1    DDB 2    DDB 3")
print("           --------------------------------------")

for cdm in range(16):

    values = []

    for ddb in range(4):
        value = temperatures.get((cdm, ddb))

        if value is None:
            values.append("   MISSING")
        else:
            values.append(f"{value:8.4f}")

    print(
        f"CDM {cdm:2d}    "
        + "  ".join(values)
    )

print()
print(f"Total records: {len(temperatures)}")