
# SiPM DDB Temperature Plotter

This is a standalone PyQt6 program for plotting DDB temperature versus event
number from `*_EVBdata.eve` files.

## Camera structure

- 16 CDMs
- 4 DDBs per CDM
- 64 DDBs total

The program therefore creates 16 plots. Each plot contains up to four curves:

- DDB # 0
- DDB # 1
- DDB # 2
- DDB # 3

The plot also displays the average temperature for that CDM.

## Install

Create/activate a virtual environment and run:

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Then either:

1. Select individual `*_EVBdata.eve` files, or
2. Select a folder. The program recursively searches for `*_EVBdata.eve`.

## Word 6 decoding

The DDB event-data packet format gives the exact bit positions used by this
program:

```text
bits  0..12  = Temperature (13 bits)
bits 16..17  = DDB ID (2 bits)
bits 18..22  = CDM ID (5 bits)
```

The corresponding extraction is:

```python
temperature = word6 & 0x1FFF
ddb_id = (word6 >> 16) & 0x03
cdm_id = (word6 >> 18) & 0x1F
```

Thus the program no longer uses the earlier provisional byte-based Word-6
layout.

## Average temperature

For each CDM, the displayed average is the arithmetic mean of all valid
temperature samples from its four DDBs.

## Design

```text
main.py
   |
   +-- PyQt6 GUI
   |
   +-- background reader thread
   |
   +-- 16 matplotlib plots
   |
   +-- evb_reader.py
          |
          +-- binary packet scan
          +-- event number
          +-- CDM/DDB/temperature extraction
```
