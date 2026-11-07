"""Read-only audit of BLE advertisement inputs and passive data-receive APIs.

Usage: py -3 scripts/audit_passive_ble.py path/to/base.apk --out evidence/passive_ble_audit.json
Does not execute Android code, connect to devices, or transmit packets.
"""

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from analyze_static import Dex


SCAN_INPUTS = (
    "Landroid/bluetooth/le/ScanRecord;->",
    "Landroid/bluetooth/le/ScanResult;->",
    "Landroid/bluetooth/le/ScanFilter;->",
    "Landroid/bluetooth/le/ScanFilter$Builder;->",
)
PASSIVE_RECEIVE = (
    "Landroid/bluetooth/BluetoothGatt;->readCharacteristic(",
    "Landroid/bluetooth/BluetoothGatt;->readDescriptor(",
    "Landroid/bluetooth/BluetoothGatt;->readRemoteRssi(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getValue(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getStringValue(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getIntValue(",
    "Landroid/bluetooth/BluetoothGattCharacteristic;->getFloatValue(",
    "Landroid/bluetooth/BluetoothGattDescriptor;->getValue(",
)
LOADING = (
    "Ldalvik/system/DexClassLoader;->",
    "Ldalvik/system/InMemoryDexClassLoader;->",
    "Ldalvik/system/PathClassLoader;->",
    "Ljava/lang/System;->load(",
    "Ljava/lang/System;->loadLibrary(",
    "Ljava/lang/Runtime;->load(",
    "Ljava/lang/Runtime;->loadLibrary(",
)
REFLECT = (
    "Ljava/lang/Class;->forName(",
    "Ljava/lang/ClassLoader;->loadClass(",
    "Ljava/lang/reflect/Method;->invoke(",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.apk) as source:
        dex = Dex(source.read("classes.dex"))

    results = defaultdict(list)
    owners = ("Lq3;->", "Ln3;->", "Lr3;->", "Lm3;->", "Lk3;->",
              "Lya;->", "Lo3;->", "Lcom/company/audioguide/MainActivity;->")
    for index, (code_off, _) in dex.definitions.items():
        if not code_off:
            continue
        caller = dex.methods[index]
        for ins in dex.instructions(code_off):
            callee = ins.get("invoke", "")
            group = None
            if callee.startswith(SCAN_INPUTS):
                group = "scan_input_calls"
            elif callee.startswith(PASSIVE_RECEIVE):
                group = "passive_receive_calls"
            elif callee.startswith(LOADING):
                group = "dynamic_code_loading_calls"
            elif callee.startswith(REFLECT):
                group = "reflection_calls"
            if group:
                results[group].append({"caller": caller, "code_off": code_off,
                                       "pc": ins["pc"], "callee": callee})

    callbacks = sorted(
        {dex.methods[index] for index in dex.definitions
         if any(dex.methods[index].startswith(owner) for owner in ("Ln3;->", "Lq3;->"))
         and any(s in dex.methods[index] for s in
                 ("->onCharacteristic", "->onDescriptor", "->onReadRemoteRssi",
                  "->onScanResult", "->onBatchScanResults", "->onScanFailed"))}
    )
    result = {
        "apk": str(args.apk.resolve()),
        "defined_methods_checked": len(dex.definitions),
        "scan_input_calls": results["scan_input_calls"],
        "passive_receive_calls": results["passive_receive_calls"],
        "dynamic_code_loading_calls": results["dynamic_code_loading_calls"],
        "reflection_counts": {
            "total": len(results["reflection_calls"]),
            "ble_app_classes": sum(1 for x in results["reflection_calls"]
                                   if x["caller"].startswith(owners)),
        },
        "ble_app_reflection_calls": [x for x in results["reflection_calls"]
                                     if x["caller"].startswith(owners)],
        "callback_definitions": callbacks,
        "scope_limit": "Direct instructions in classes.dex only; reflection, OS internals, and peripheral capabilities not ruled out.",
    }
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
        print(f"saved: {args.out}")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
