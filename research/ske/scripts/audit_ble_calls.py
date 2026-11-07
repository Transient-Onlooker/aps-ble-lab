"""Audit all direct Android BLE references in one APK DEX without running the app."""

import argparse
import json
import zipfile
from pathlib import Path

from analyze_static import Dex


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--out", type=Path, help="Write the audit JSON to this file")
    args = parser.parse_args()
    apk_path = args.apk.resolve()
    with zipfile.ZipFile(apk_path) as apk:
        dex = Dex(apk.read("classes.dex"))

    callbacks = [
        item for item in dex.classes
        if item["super"] in {
            "Landroid/bluetooth/BluetoothGattCallback;",
            "Landroid/bluetooth/le/ScanCallback;",
        }
    ]
    calls = []
    for method_index, (offset, _) in dex.definitions.items():
        if not offset:
            continue
        for insn in dex.instructions(offset):
            target = insn.get("invoke", "")
            if target.startswith((
                "Landroid/bluetooth/BluetoothGatt;->",
                "Landroid/bluetooth/BluetoothDevice;->connectGatt",
                "Landroid/bluetooth/le/BluetoothLeScanner;->",
            )):
                calls.append({
                    "caller": dex.methods[method_index],
                    "code_off": offset,
                    "pc": insn["pc"],
                    "callee": target,
                })

    read_calls = [x for x in calls if "->readCharacteristic(" in x["callee"]]
    callback_methods = [
        dex.methods[i] for i in dex.definitions
        if any(dex.methods[i].startswith(x["name"] + "->") for x in callbacks)
        and any(key in dex.methods[i] for key in ("onCharacteristic", "onServices", "onDescriptor", "onConnection"))
    ]
    report = {
        "apk": str(apk_path),
        "defined_method_count": len(dex.definitions),
        "direct_ble_call_count": len(calls),
        "gatt_callback_classes": callbacks,
        "gatt_callback_methods": sorted(callback_methods),
        "readCharacteristic_direct_call_count": len(read_calls),
        "readCharacteristic_direct_calls": read_calls,
        "ble_calls": calls,
        "limitation": "Only direct invocations in classes.dex; reflection/native/dynamic code is not excluded.",
    }
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(data, encoding="utf-8")
        print(f"Saved {args.out}")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
