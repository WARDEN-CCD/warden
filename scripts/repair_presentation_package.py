from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
ns = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", ns)

with ZipFile(source, "r") as zin:
    names = set(zin.namelist())
    root = ET.fromstring(zin.read("[Content_Types].xml"))
    for el in list(root):
        if el.tag == f"{{{ns}}}Override" and el.attrib.get("PartName", "").lstrip("/") not in names:
            root.remove(el)
    existing = {el.attrib.get("PartName") for el in root.findall(f"{{{ns}}}Override")}
    for name in sorted(names):
        if name.startswith("ppt/slideMasters/") and name.endswith(".xml"):
            part = f"/{name}"
            if part not in existing:
                ET.SubElement(root, f"{{{ns}}}Override", {
                    "PartName": part,
                    "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
                })
    content_types = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = content_types if item.filename == "[Content_Types].xml" else zin.read(item.filename)
            zout.writestr(item, data)

print(f"Repaired slide-master content-type declarations: {source} -> {target}")
