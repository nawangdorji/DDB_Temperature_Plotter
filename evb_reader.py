"""
evb_reader.py
-------------
Sequential reader for SiPM camera *_EVBdata.eve files.

Packet structure used here:
    Word 1 : upper 16 bits = start-frame ID, lower 16 bits = packet size
             (packet size is in 32-bit words)
    Word 3 : event number
    Word 6 : temperature + DDB ID + CDM ID

Word 6 bit fields:
    bits  0..12 : Temperature (13 bits)
    bits 16..17 : DDB ID (2 bits)
    bits 18..22 : CDM ID (5 bits)

For the currently inspected EVB files:
    start-frame ID = 0xFBDA
    end-frame ID   = 0xEDAC

The temperature conversion is kept in one place:
    temperature_C = raw / TEMPERATURE_SCALE

The /16 conversion matches the observed EVB values (for example,
raw=503 -> 31.4375 C). If the final hardware documentation specifies
a different conversion, change only TEMPERATURE_SCALE.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import mmap
from pathlib import Path
import struct
from typing import Callable, DefaultDict


WORD_SIZE = 4

CDM_COUNT = 16
DDB_COUNT = 4

START_FRAME_ID = 0xFBDA
END_FRAME_ID = 0xEDAC

TEMPERATURE_SCALE = 16.0
MAX_TEMPERATURE_C = 100.0


@dataclass(frozen=True)
class TemperaturePoint:
    event: int
    temperature: float


TemperatureData = DefaultDict[int, DefaultDict[int, list[TemperaturePoint]]]


class EVBFormatError(RuntimeError):
    """Raised when an EVB file cannot be interpreted safely."""


def decode_word6(word6: int) -> tuple[int, int, float]:
    """
    Return (cdm_id, ddb_id, temperature_C) from Word 6.

    Exact bit positions:
        bits  0..12 -> temperature raw value
        bits 16..17 -> DDB ID
        bits 18..22 -> CDM ID
    """
    temperature_raw = word6 & 0x1FFF
    ddb_id = (word6 >> 16) & 0x03
    cdm_id = (word6 >> 18) & 0x1F

    temperature_c = temperature_raw / TEMPERATURE_SCALE
    return cdm_id, ddb_id, temperature_c


class EVBReader:
    """Read DDB temperature records from EVB files."""

    def __init__(
        self,
        max_temperature: float = MAX_TEMPERATURE_C,
        require_frame_ids: bool = True,
    ) -> None:
        self.max_temperature = max_temperature
        self.require_frame_ids = require_frame_ids

    def read_file(
        self,
        filename: str | Path,
        progress_callback: Callable[[int], None] | None = None,
    ) -> TemperatureData:
        """
        Read all valid temperature packets from one EVB file.

        Returns:
            data[cdm_id][ddb_id] -> list[TemperaturePoint]
        """
        path = Path(filename)
        if not path.is_file():
            raise FileNotFoundError(path)

        data: TemperatureData = defaultdict(lambda: defaultdict(list))

        with path.open("rb") as fp:
            mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                self._read_mapped_file(mm, data, progress_callback)
            finally:
                mm.close()

        return data

    def _read_mapped_file(
        self,
        mm: mmap.mmap,
        data: TemperatureData,
        progress_callback: Callable[[int], None] | None,
    ) -> None:
        size = len(mm)

        if size < WORD_SIZE:
            raise EVBFormatError("File is too small to contain an EVB packet.")

        pos = 0
        packet_count = 0

        while pos + WORD_SIZE <= size:
            word1 = struct.unpack_from("<I", mm, pos)[0]

            frame_id = (word1 >> 16) & 0xFFFF
            packet_words = word1 & 0xFFFF
            packet_bytes = packet_words * WORD_SIZE

            if packet_words < 7:
                raise EVBFormatError(
                    f"Invalid packet size at byte offset {pos}: "
                    f"{packet_words} words."
                )

            packet_end = pos + packet_bytes
            if packet_end > size:
                raise EVBFormatError(
                    f"Packet at byte offset {pos} extends beyond the file: "
                    f"{packet_words} words."
                )

            if self.require_frame_ids and frame_id != START_FRAME_ID:
                raise EVBFormatError(
                    f"Unexpected start-frame ID 0x{frame_id:04X} "
                    f"at byte offset {pos}; expected 0x{START_FRAME_ID:04X}."
                )

            # Read only the header words needed for temperature extraction.
            words = struct.unpack_from("<7I", mm, pos)
            event_number = words[2]
            word6 = words[5]

            cdm_id, ddb_id, temperature = decode_word6(word6)

            # The last word contains the end-frame ID and packet size.
            end_word = struct.unpack_from("<I", mm, packet_end - WORD_SIZE)[0]
            end_frame_id = (end_word >> 16) & 0xFFFF
            end_packet_words = end_word & 0xFFFF

            if self.require_frame_ids:
                if end_frame_id != END_FRAME_ID:
                    raise EVBFormatError(
                        f"Unexpected end-frame ID 0x{end_frame_id:04X} "
                        f"at byte offset {packet_end - WORD_SIZE}; "
                        f"expected 0x{END_FRAME_ID:04X}."
                    )

                if end_packet_words != packet_words:
                    raise EVBFormatError(
                        f"Packet-size mismatch at byte offset {pos}: "
                        f"header={packet_words}, end={end_packet_words}."
                    )

            if (
                0 <= cdm_id < CDM_COUNT
                and 0 <= ddb_id < DDB_COUNT
                and 0.0 <= temperature <= self.max_temperature
            ):
                data[cdm_id][ddb_id].append(
                    TemperaturePoint(
                        event=event_number,
                        temperature=temperature,
                    )
                )

            packet_count += 1
            pos = packet_end

            if progress_callback is not None:
                progress_callback(int(pos * 100 / size))

        if pos != size:
            raise EVBFormatError(
                f"Unexpected trailing bytes: stopped at {pos} of {size}."
            )

        if packet_count == 0:
            raise EVBFormatError("No EVB packets were found.")

    @staticmethod
    def merge(
        destination: TemperatureData,
        source: TemperatureData,
    ) -> None:
        """Merge one reader result into an existing result."""
        for cdm_id, ddbs in source.items():
            for ddb_id, points in ddbs.items():
                destination[cdm_id][ddb_id].extend(points)

    @staticmethod
    def sort_data(data: TemperatureData) -> None:
        """Sort each DDB series by event number."""
        for ddbs in data.values():
            for points in ddbs.values():
                points.sort(key=lambda p: p.event)

    @staticmethod
    def statistics_for_cdm(
        data: TemperatureData,
        cdm_id: int,
    ) -> tuple[float | None, int]:
        """
        Return (average_temperature, number_of_points) for all four DDBs
        belonging to one CDM.
        """
        values = []
        for ddb_id in range(DDB_COUNT):
            values.extend(
                p.temperature
                for p in data.get(cdm_id, {}).get(ddb_id, [])
            )

        if not values:
            return None, 0

        return sum(values) / len(values), len(values)

    @staticmethod
    def total_points(data: TemperatureData) -> int:
        return sum(
            len(points)
            for ddbs in data.values()
            for points in ddbs.values()
        )

    @staticmethod
    def find_evb_files(root: str | Path) -> list[Path]:
        """Recursively find files ending exactly in *_EVBdata.eve."""
        root = Path(root)
        return sorted(
            p for p in root.rglob("*_EVBdata.eve")
            if p.is_file()
        )
