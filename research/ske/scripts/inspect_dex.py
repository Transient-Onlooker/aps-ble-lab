"""Disassemble narrowly selected DEX methods; no code execution or BLE activity.

Usage: py inspect_dex.py base.apk 'Lq3;->onScanResult'
"""

import json
import struct
import sys
import zipfile
from pathlib import Path

from analyze_static import Dex


def signed(val, bits):
    return val - (1 << bits) if val & (1 << (bits - 1)) else val


def decode(dex, idx):
    off, _ = dex.definitions[idx]
    if not off:
        return []
    raw = dex.b
    count = struct.unpack_from('<I', raw, off + 12)[0]
    codes = struct.unpack_from(f'<{count}H', raw, off + 16)
    refs = {x['pc']: x for x in dex.instructions(off)}
    pcs = sorted(refs)
    out = []
    for i, pc in enumerate(pcs):
        next_pc = pcs[i + 1] if i + 1 < len(pcs) else count
        w = codes[pc:next_pc]
        op = w[0] & 255
        data = {'pc': pc, 'opcode': f'0x{op:02x}', 'raw': [f'{x:04x}' for x in w[:5]]}
        item = refs[pc]
        for key in ('invoke', 'string', 'field', 'type'):
            if key in item:
                data[key] = item[key]
        if op == 0x12:
            data['const'] = signed((w[0] >> 12) & 15, 4)
            data['register'] = (w[0] >> 8) & 15
        elif op in (0x13, 0x16):
            data['const'] = signed(w[1], 16)
            data['register'] = w[0] >> 8
        elif op == 0x14:
            data['const'] = signed(w[1] | (w[2] << 16), 32)
            data['register'] = w[0] >> 8
        elif op == 0x15:
            data['const'] = signed(w[1], 16) << 16
            data['register'] = w[0] >> 8
        elif op in (0x19,):
            data['const'] = signed(w[1], 16) << 48
        elif op in (0x1a, 0x1b):
            data['register'] = w[0] >> 8
        elif op in list(range(0x6e, 0x73)) + [0x24]:
            count_args = (w[0] >> 12) & 15
            regs = [w[2] & 15, (w[2] >> 4) & 15, (w[2] >> 8) & 15, (w[2] >> 12) & 15, (w[0] >> 8) & 15]
            data['registers'] = regs[:count_args]
        elif op in list(range(0x74, 0x79)) + [0x25]:
            data['registers'] = list(range(w[2], w[2] + (w[0] >> 8)))
        elif op == 0x26 and len(w) >= 3:
            delta = signed(w[1] | (w[2] << 16), 32)
            pos = pc + delta
            if pos + 4 <= count and codes[pos] == 0x0300:
                width = codes[pos + 1]
                size = codes[pos + 2] | (codes[pos + 3] << 16)
                byte_len = width * size
                arr = struct.pack('<' + 'H' * ((byte_len + 1) // 2), *codes[pos + 4:pos + 4 + (byte_len + 1) // 2])[:byte_len]
                data['array_width'] = width
                data['array_count'] = size
                data['array_hex'] = arr.hex()
                if width in (1, 2, 4) and size < 200:
                    fmt = {1: 'B', 2: 'H', 4: 'I'}[width]
                    data['array_unsigned'] = list(struct.unpack('<' + fmt * size, arr))
        out.append(data)
    return out


def main():
    apk = Path(sys.argv[1])
    pattern = sys.argv[2]
    with zipfile.ZipFile(apk) as zipped:
        d = Dex(zipped.read('classes.dex'))
    matches = []
    for idx in d.definitions:
        if pattern in d.methods[idx]:
            matches.append({'method': d.methods[idx], 'code_off': d.definitions[idx][0], 'instructions': decode(d, idx)})
    print(json.dumps(matches, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
