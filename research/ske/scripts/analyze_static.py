"""Offline, read-only Android APK/DEX structural survey.

Usage: py analyze_static.py <apk_dir> <evidence_dir>
No device, Bluetooth API, or network access is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


def u16(buf, off):
    return struct.unpack_from('<H', buf, off)[0]


def u32(buf, off):
    return struct.unpack_from('<I', buf, off)[0]


def leb(buf, off):
    value = 0
    for i in range(5):
        n = buf[off + i]
        value |= (n & 0x7f) << (7 * i)
        if not n & 0x80:
            return value, off + i + 1
    raise ValueError('Invalid ULEB128')


def pool_len8(buf, off):
    length = buf[off]
    off += 1
    if length & 0x80:
        length = ((length & 0x7f) << 8) | buf[off]
        off += 1
    return length, off


def pool_len16(buf, off):
    length = u16(buf, off)
    off += 2
    if length & 0x8000:
        length = ((length & 0x7fff) << 16) | u16(buf, off)
        off += 2
    return length, off


def string_pool(buf, off):
    count = u32(buf, off + 8)
    flags = u32(buf, off + 16)
    data_off = off + u32(buf, off + 20)
    offsets = [u32(buf, off + 28 + i * 4) for i in range(count)]
    strings = []
    for offset in offsets:
        p = data_off + offset
        if flags & 0x100:
            _, p = pool_len8(buf, p)
            n, p = pool_len8(buf, p)
            strings.append(buf[p:p + n].decode('utf-8', errors='replace'))
        else:
            n, p = pool_len16(buf, p)
            strings.append(buf[p:p + n * 2].decode('utf-16-le', errors='replace'))
    return strings


def parse_axml(data):
    strings = []
    tags = []
    namespaces = {}
    off = u16(data, 2)
    while off + 8 <= len(data):
        chunk_type, hdr, size = struct.unpack_from('<HHI', data, off)
        if size < 8 or off + size > len(data):
            break
        if chunk_type == 0x1:
            strings = string_pool(data, off)
        elif chunk_type == 0x0100:
            prefix_idx, uri_idx = u32(data, off + 16), u32(data, off + 20)
            if prefix_idx < len(strings) and uri_idx < len(strings):
                namespaces[strings[uri_idx]] = strings[prefix_idx]
        elif chunk_type == 0x0102:
            name_idx = u32(data, off + 20)
            name = strings[name_idx] if name_idx < len(strings) else f'@{name_idx}'
            attr_start, attr_size, count = struct.unpack_from('<HHH', data, off + 24)
            attrs = {}
            for i in range(count):
                a = off + 16 + attr_start + attr_size * i
                ns, key_idx, raw_idx = struct.unpack_from('<III', data, a)
                value_type = data[a + 15]
                value_data = u32(data, a + 16)
                key = strings[key_idx] if key_idx < len(strings) else f'@{key_idx}'
                if ns < len(strings):
                    prefix = namespaces.get(strings[ns], strings[ns].rsplit('/', 1)[-1])
                    key = f'{prefix}:{key}'
                if raw_idx < len(strings):
                    value = strings[raw_idx]
                elif value_type == 3 and value_data < len(strings):
                    value = strings[value_data]
                elif value_type == 0x12:
                    value = bool(value_data)
                else:
                    value = f'0x{value_data:08x}' if value_type in (1, 2) else value_data
                attrs[key] = value
            tags.append({'tag': name, 'attrs': attrs, 'line': u32(data, off + 8)})
        off += size
    return tags


SIZE3 = set([0x03, 0x06, 0x09, 0x14, 0x17, 0x1b, 0x24, 0x25, 0x26,
             0x2a, 0x2b, 0x2c, 0xfc, 0xfd]) | set(range(0x6e, 0x73)) | set(range(0x74, 0x79))
SIZE2 = set([0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1a, 0x1c,
             0x1f, 0x20, 0x22, 0x23, 0x29, 0xfe, 0xff])
SIZE2 |= set(range(0x2d, 0x3e)) | set(range(0x44, 0x6e)) | set(range(0x90, 0xb0)) | set(range(0xd0, 0xe3))


class Dex:
    def __init__(self, data):
        self.b = data
        h = data
        n, o = u32(h, 0x38), u32(h, 0x3c)
        self.strings = []
        for i in range(n):
            p = u32(h, o + i * 4)
            _, p = leb(data, p)
            end = data.index(0, p)
            self.strings.append(data[p:end].decode('utf-8', errors='replace'))
        n, o = u32(h, 0x40), u32(h, 0x44)
        self.types = [self.strings[u32(h, o + i * 4)] for i in range(n)]
        n, o = u32(h, 0x48), u32(h, 0x4c)
        self.protos = []
        for i in range(n):
            _, ret, params = struct.unpack_from('<III', h, o + i * 12)
            args = [] if params == 0 else [self.types[u16(h, params + 4 + j * 2)] for j in range(u32(h, params))]
            self.protos.append('(' + ','.join(args) + ')->' + self.types[ret])
        n, o = u32(h, 0x50), u32(h, 0x54)
        self.fields = []
        for i in range(n):
            owner, typ, name = struct.unpack_from('<HHI', h, o + i * 8)
            self.fields.append(self.types[owner] + '->' + self.strings[name] + ':' + self.types[typ])
        n, o = u32(h, 0x58), u32(h, 0x5c)
        self.methods = []
        for i in range(n):
            owner, proto, name = struct.unpack_from('<HHI', h, o + i * 8)
            self.methods.append(self.types[owner] + '->' + self.strings[name] + self.protos[proto])
        self.definitions = {}
        n, o = u32(h, 0x60), u32(h, 0x64)
        self.classes = []
        for i in range(n):
            klass, flags, parent, interfaces, source, annots, classdata, values = struct.unpack_from('<IIIIIIII', h, o + i * 32)
            self.classes.append({'name': self.types[klass], 'super': self.types[parent] if parent < len(self.types) else None,
                                 'source': self.strings[source] if source < len(self.strings) else None})
            if not classdata:
                continue
            f_s, p = leb(h, classdata)
            f_i, p = leb(h, p)
            m_d, p = leb(h, p)
            m_v, p = leb(h, p)
            for count in (f_s, f_i):
                for _ in range(count):
                    _, p = leb(h, p)
                    _, p = leb(h, p)
            for count in (m_d, m_v):
                prev = 0
                for _ in range(count):
                    delta, p = leb(h, p)
                    prev += delta
                    access, p = leb(h, p)
                    code_off, p = leb(h, p)
                    self.definitions[prev] = (code_off, access)

    def instructions(self, code_off):
        if not code_off:
            return []
        b = self.b
        registers, ins, outs, tries, debug, count = struct.unpack_from('<HHHHII', b, code_off)
        data = list(struct.unpack_from(f'<{count}H', b, code_off + 16))
        out = []
        pc = 0
        while pc < len(data):
            word = data[pc]
            op = word & 0xff
            sz = 1
            if op == 0x00 and word >> 8 in (1, 2, 3) and pc + 4 < len(data):
                kind = word >> 8
                num = data[pc + 1]
                if kind == 1:
                    sz = 4 + 2 * num
                elif kind == 2:
                    sz = 2 + 4 * num
                else:
                    item_bytes = data[pc + 2] | (data[pc + 3] << 16)
                    sz = 4 + (num * item_bytes + 1) // 2
            elif op == 0x18:
                sz = 5
            elif op in (0xfa, 0xfb):
                sz = 4
            elif op in SIZE3:
                sz = 3
            elif op in SIZE2:
                sz = 2
            if pc + sz > len(data):
                break
            item = {'pc': pc, 'opcode': f'0x{op:02x}'}
            if op in (0x1a, 0x1b):
                idx = data[pc + 1] | ((data[pc + 2] << 16) if op == 0x1b else 0)
                if idx < len(self.strings):
                    item['string'] = self.strings[idx]
            elif op == 0x1c or op == 0x22:
                idx = data[pc + 1]
                if idx < len(self.types):
                    item['type'] = self.types[idx]
            elif op in range(0x52, 0x6e):
                idx = data[pc + 1]
                if idx < len(self.fields):
                    item['field'] = self.fields[idx]
            elif op in list(range(0x6e, 0x73)) + list(range(0x74, 0x79)):
                idx = data[pc + 1]
                if idx < len(self.methods):
                    item['invoke'] = self.methods[idx]
            out.append(item)
            pc += sz
        return out

    def survey(self):
        terms = re.compile('bluetooth|gatt|scan|uuid|device|rssi|remote|nordic|uart|AHG001|BHG001|cdd2|packet|notify|characteristic|location|signal', re.I)
        entries = []
        for idx, (off, access) in self.definitions.items():
            name = self.methods[idx]
            insns = self.instructions(off)
            calls = [x for x in insns if 'invoke' in x]
            matching_calls = [x for x in calls if terms.search(x['invoke'])]
            literals = [x for x in insns if 'string' in x]
            matching_literals = [x for x in literals if terms.search(x['string'])]
            if terms.search(name) or matching_calls or matching_literals:
                entries.append({'name': name, 'code_off': off, 'access': access,
                                'calls': calls, 'literals': literals,
                                'fields': [x for x in insns if 'field' in x],
                                'matching_call_count': len(matching_calls),
                                'matching_literal_count': len(matching_literals)})
        return {'dex_classes': self.classes, 'all_method_refs': len(self.methods),
                'defined_methods': len(self.definitions), 'interesting_methods': entries,
                'matching_dex_strings': [{'idx': i, 'value': s} for i, s in enumerate(self.strings) if terms.search(s)]}


def main(apkdir, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    files = sorted(apkdir.glob('*.apk'))
    inv = {'input_dir': str(apkdir), 'files': [], 'manifest_by_file': {}}
    surveys = []
    for path in files:
        raw = path.read_bytes()
        with zipfile.ZipFile(path) as apk:
            names = apk.namelist()
            entries = [{'name': name, 'size': apk.getinfo(name).file_size} for name in names
                       if name.endswith(('.dex', '.so')) or name.startswith('lib/')]
            inv['files'].append({'name': path.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                 'entries': entries, 'zip_entries': len(names)})
            inv['manifest_by_file'][path.name] = parse_axml(apk.read('AndroidManifest.xml'))
            for dexname in names:
                if dexname.endswith('.dex'):
                    dex = Dex(apk.read(dexname))
                    surveys.append({'apk': path.name, 'dex': dexname, **dex.survey()})
    for name, obj in [('apk_inventory.json', inv), ('dex_ble_survey.json', surveys)]:
        (evidence / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    print('APKs:', [(item['name'], item['sha256']) for item in inv['files']])
    for apk, tags in inv['manifest_by_file'].items():
        print('MANIFEST', apk, 'tags', len(tags))
        for tag in tags:
            if tag['tag'] in ('manifest', 'uses-sdk', 'uses-permission', 'activity', 'service', 'receiver', 'provider', 'application'):
                print(json.dumps(tag, ensure_ascii=False)[:450])
    for entry in surveys:
        print('DEX', entry['apk'], entry['dex'], 'classes', len(entry['dex_classes']), 'methods', entry['defined_methods'],
              'interesting methods', len(entry['interesting_methods']))
        for method in entry['interesting_methods']:
            matchcalls = [c['invoke'] for c in method['calls'] if re.search('bluetooth|gatt|scan|uuid|rssi|characteristic', c['invoke'], re.I)]
            if matchcalls:
                print(' ', method['name'][:130], '->', '; '.join(matchcalls[:5])[:350])


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
