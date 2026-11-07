"""Static, read-only audit of the SKE APK's response consumers and alternate code paths.

Usage: py -3 audit_receive_paths.py path/to/base.apk [--out path/to/result.json]
The default output is JSON on stdout; no app or device is executed.
"""

import argparse
import json
import zipfile
from pathlib import Path

from analyze_static import Dex


RESPONSE_PREFIX = "LI0;->"
GATT_FIELDS = {
    "Lr3;->M:Landroid/bluetooth/BluetoothGatt;",  # short-lived secondary connection
    "Lr3;->v:Landroid/bluetooth/BluetoothGatt;",  # primary connection
    "Lr3;->R:Landroid/bluetooth/BluetoothGattCharacteristic;",
    "Lr3;->w:Landroid/bluetooth/BluetoothGattCharacteristic;",
    "Lr3;->W:Ln3;",  # callback object for both connections
}
REFLECTION_PREFIXES = (
    "Ljava/lang/Class;->forName(",
    "Ljava/lang/ClassLoader;->loadClass(",
    "Ljava/lang/reflect/",
    "Ldalvik/system/",
    "Ljava/lang/System;->load",
    "Ljava/lang/Runtime;->load",
)
OTHER_DATA_APIS = (
    "Landroid/bluetooth/BluetoothGatt;->readCharacteristic(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getValue(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getProperties(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getDescriptors(",
    "Landroid/bluetooth/BluetoothGatt;->readDescriptor(",
    "Landroid/bluetooth/BluetoothGatt;->readRemoteRssi(",
    "Landroid/bluetooth/BluetoothGatt;->setCharacteristicNotification(",
    "Landroid/bluetooth/BluetoothDevice;->connectGatt(",
)
PAIRING_APIS = (
    "Landroid/bluetooth/BluetoothDevice;->createBond(",
    "Landroid/bluetooth/BluetoothDevice;->getBondState(",
    "Landroid/bluetooth/BluetoothDevice;->setPin(",
    "Landroid/bluetooth/BluetoothAdapter;->getBondedDevices(",
    "Landroid/bluetooth/BluetoothDevice;->setPairingConfirmation(",
)


def audit(apk_path):
    with zipfile.ZipFile(apk_path) as archive:
        dex_bytes = archive.read("classes.dex")
        native = [
            {"name": e.filename, "size": e.file_size}
            for e in archive.infolist()
            if e.filename.startswith("lib/") and e.filename.endswith(".so")
        ]
        extra_code = [
            e.filename for e in archive.infolist()
            if e.filename.endswith((".dex", ".jar", ".apk")) and e.filename != "classes.dex"
        ]
    dex = Dex(dex_bytes)
    refs = {"response_fields": [], "response_methods": [], "response_type": [],
            "gatt_owner_fields": [], "reflection_and_loading": [],
            "other_data_apis": [], "pairing_apis": []}
    code_writers = []
    for idx, (offset, _) in dex.definitions.items():
        if not offset:
            continue
        caller = dex.methods[idx]
        if caller.startswith(RESPONSE_PREFIX):
            code_writers.append({"method": caller, "code_off": offset})
        for instruction in dex.instructions(offset):
            target = instruction.get("invoke")
            field = instruction.get("field")
            typ = instruction.get("type")
            val = None
            group = None
            if field and field.startswith(RESPONSE_PREFIX):
                group, val = "response_fields", field
            elif field in GATT_FIELDS:
                group, val = "gatt_owner_fields", field
            elif target and target.startswith(RESPONSE_PREFIX):
                group, val = "response_methods", target
            elif typ == "LI0;":
                group, val = "response_type", typ
            elif target and target.startswith(REFLECTION_PREFIXES):
                group, val = "reflection_and_loading", target
            elif target and target.startswith(OTHER_DATA_APIS):
                group, val = "other_data_apis", target
            elif target and target.startswith(PAIRING_APIS):
                group, val = "pairing_apis", target
            if group:
                refs[group].append({"caller": caller, "code_off": offset,
                                    "pc": instruction["pc"], "opcode": instruction["opcode"],
                                    "target": val})
    # Android GATT callback subclasses are the app's ordinary direct receive entry points.
    callbacks = [
        item for item in dex.classes
        if item["super"] in ("Landroid/bluetooth/BluetoothGattCallback;",
                             "Landroid/bluetooth/le/ScanCallback;")
    ]
    return {
        "apk": str(apk_path.resolve()),
        "scope": {"defined_methods": len(dex.definitions),
                  "dex_members_in_base": 1 + len([x for x in extra_code if x.endswith(".dex")]),
                  "other_potential_code_entries": extra_code,
                  "native_libraries": native,
                  "direct_callback_subclasses": callbacks},
        "AhgResponse_definition": code_writers,
        "references": refs,
        "limitation": "Direct DEX references only. Native libraries, reflective calls, external code, and device capabilities require separate inspection.",
    }


def compact_evidence(result):
    refs = result["references"]
    return {
        "apk": result["apk"],
        "scope": result["scope"],
        "AhgResponse_definition": result["AhgResponse_definition"],
        "reference_counts": {name: len(rows) for name, rows in refs.items()},
        "response_external_consumers": [
            row for group in ("response_fields", "response_methods", "response_type")
            for row in refs[group] if not row["caller"].startswith(RESPONSE_PREFIX)
        ],
        "gatt_field_callers": {
            caller: sorted({row["target"] for row in refs["gatt_owner_fields"]
                            if row["caller"] == caller})
            for caller in sorted({row["caller"] for row in refs["gatt_owner_fields"]})
        },
        "other_data_apis": refs["other_data_apis"],
        "pairing_apis": refs["pairing_apis"],
        "reflection_loading_targets": sorted({
            row["target"] for row in refs["reflection_and_loading"]
            if row["target"].startswith(("Ljava/lang/Class;->forName(",
                                           "Ljava/lang/ClassLoader;->loadClass(",
                                           "Ldalvik/system/", "Ljava/lang/System;->load",
                                           "Ljava/lang/Runtime;->load"))
        }),
        "limitation": result["limitation"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--compact", action="store_true",
                        help="Summarize the full reference inventory for evidence review")
    options = parser.parse_args()
    result = audit(options.apk)
    if options.compact:
        result = compact_evidence(result)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if options.out:
        options.out.write_text(serialized, encoding="utf-8")
        print(options.out)
    else:
        print(serialized, end="")
