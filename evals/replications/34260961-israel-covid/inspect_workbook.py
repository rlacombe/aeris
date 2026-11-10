"""Print the public CBS locality workbook schema without external packages."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


WORKBOOK = Path(__file__).resolve().parent / "source_inputs" / "bycode2019.xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def cell_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def main() -> None:
    with ZipFile(WORKBOOK) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(item.itertext()) for item in shared.findall(f"{NS}si")]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str | None]] = []
    for row in sheet.findall(f".//{NS}row"):
        values: list[str | None] = []
        for cell in row.findall(f"{NS}c"):
            index = cell_index(cell.attrib["r"])
            values.extend([None] * (index + 1 - len(values)))
            raw = cell.findtext(f"{NS}v")
            values[index] = strings[int(raw)] if raw and cell.get("t") == "s" else raw
        rows.append(values)

    for index, value in enumerate(rows[0]):
        print(index, repr(value))
    for row in rows[1:4]:
        print(row)


if __name__ == "__main__":
    main()
