"""Verify published XOR evidence; optionally cross-check a privately held APK.

No networking, APK execution, Bluetooth access or output files.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent.parent / 'evidence'
    data = json.loads((evidence / 'decoded_uuids.json').read_text(encoding='utf-8'))
    expected = {
        'service': '0003cdd0-0000-1000-8000-00805f9b0131',
        'notify': '0003cdd1-0000-1000-8000-00805f9b0131',
        'app_write': '0003cdd2-0000-1000-8000-00805f9b0131',
        'cccd': '00002902-0000-1000-8000-00805f9b34fb',
        'ahg_name_prefix': 'AHG001+', 'bhg_name_prefix': 'BHG001+',
    }
    assert {x['role'] for x in data['items']} == set(expected)
    for row in data['items']:
        raw = bytes.fromhex(row['raw_32le_hex'])
        values = struct.unpack('<' + 'I' * (len(raw) // 4), raw)
        restored = bytes((v ^ 0x5A) & 255 for v in values).decode('utf-8')
        assert restored == row['restored'] == expected[row['role']]
        rebuilt = b''.join(struct.pack('<I', v ^ 0x5A) for v in restored.encode('utf-8'))
        assert rebuilt == raw
    if args.apk:
        from analyze_static import Dex
        from inspect_dex import decode
        from audit_receive_paths import audit, compact_evidence
        assert hashlib.sha256(args.apk.read_bytes()).hexdigest() == data['sha256'], 'APK SHA mismatch'
        with zipfile.ZipFile(args.apk) as archive:
            dex = Dex(archive.read('classes.dex'))
        init = next(i for i in dex.definitions if dex.methods[i].startswith('LL0;-><clinit>('))
        assert dex.definitions[init][0] == data['initializer_code_off']
        arrays = {x['pc']: x for x in decode(dex, init) if 'array_hex' in x}
        for row in data['items']:
            assert arrays[row['pc']]['array_width'] == 4
            assert arrays[row['pc']]['array_hex'] == row['raw_32le_hex']
        decoder = next(i for i in dex.definitions if dex.methods[i].startswith('LL0;->a([I)'))
        instructions = decode(dex, decoder)
        assert any((x['opcode'] == '0xdf' and int(x['raw'][1], 16) >> 8 == 0x5A)
                   or (x['opcode'] == '0xd7' and int(x['raw'][1], 16) == 0x5A)
                   for x in instructions), 'XOR literal not found'
        actual = compact_evidence(audit(args.apk))
        actual['apk'] = args.apk.name
        saved = json.loads((evidence / 'receive_path_audit.json').read_text(encoding='utf-8'))
        assert actual == saved, 'Receive-path audit differs from published evidence'
    print(json.dumps({'xor_arrays_verified': len(data['items']),
                      'apk_cross_checked': args.apk is not None,
                      'hardware_or_live_api_verified': False}))


if __name__ == '__main__':
    main()
