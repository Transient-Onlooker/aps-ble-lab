#!/usr/bin/env python3
"""Offline Android BTSnoop advertising analyzer: NO connection or commands.

Supports HCI UART/H4 BTSnoop v1; LE Advertising Report 0x02 and
LE Extended Advertising Report 0x0D. Does not prove device identity.
Defaults to redacted device names and ephemeral pseudonymous addresses.
"""
import argparse
import gzip
import hashlib
import hmac
import json
import secrets
import struct
from datetime import datetime, timezone
from pathlib import Path

HEADER = b'btsnoop\x00'
EPOCH_DELTA = 0x00dcddb30f2f8000
MAX_SIZE = 128 * 1024 * 1024
PREFIXES = ('AHG001+', 'BHG001+')
UART_SERVICE = '0003cdd0-0000-1000-8000-00805f9b0131'


def signed_byte(value):
    return value - 256 if value >= 128 else value


def parse_ad(data):
    """Bluetooth advertising structures (length, AD type, payload)."""
    info = {'name': None, 'companyIds': set(), 'service16': set(), 'service128': set()}
    pos = 0
    while pos < len(data):
        size = data[pos]
        pos += 1
        if not size:
            break
        if pos + size > len(data):
            break
        kind, value = data[pos], data[pos + 1:pos + size]
        pos += size
        if kind in (0x08, 0x09):
            name = value.decode('utf-8', errors='replace').strip('\x00')
            if name and (info['name'] is None or kind == 0x09):
                info['name'] = name
        elif kind == 0xff and len(value) >= 2:
            info['companyIds'].add(f'0x{int.from_bytes(value[:2], "little"):04X}')
        elif kind in (0x06, 0x07):
            for k in range(0, len(value) - 15, 16):
                part = value[k:k + 16][::-1].hex()
                info['service128'].add(f'{part[:8]}-{part[8:12]}-{part[12:16]}-{part[16:20]}-{part[20:]}')
        elif kind in (0x02, 0x03):
            for k in range(0, len(value) - 1, 2):
                info['service16'].add(f'0x{int.from_bytes(value[k:k + 2], "little"):04X}')
    return info


def extract_reports(params):
    """Yield (address_type, raw_address, RSSI, AD, format, scan_response)."""
    if len(params) < 2:
        return
    subevent, count = params[0], params[1]
    if count > 50:
        return
    pos = 2
    for _ in range(count):
        if subevent == 0x02:  # LE legacy advertising report
            if pos + 9 > len(params):
                break
            kind, address_type = params[pos], params[pos + 1]
            address = params[pos + 2:pos + 8]
            length = params[pos + 8]
            if pos + 10 + length > len(params):
                break
            ad = params[pos + 9:pos + 9 + length]
            rssi = signed_byte(params[pos + 9 + length])
            pos += 10 + length
            yield address_type, address, rssi, ad, 'legacy', kind == 0x04
        elif subevent == 0x0d:  # LE extended advertising report
            if pos + 24 > len(params):
                break
            flags = int.from_bytes(params[pos:pos + 2], 'little')
            address_type = params[pos + 2]
            address = params[pos + 3:pos + 9]
            rssi = signed_byte(params[pos + 13])
            length = params[pos + 23]
            if pos + 24 + length > len(params):
                break
            ad = params[pos + 24:pos + 24 + length]
            pos += 24 + length
            yield address_type, address, rssi, ad, 'extended', bool(flags & 8)
        else:
            return


def parse_hci_event(packet):
    if len(packet) < 4 or packet[0] != 0x04 or packet[1] != 0x3e:
        return []
    size = packet[2]
    if 3 + size > len(packet):
        return []
    return list(extract_reports(packet[3:3 + size]))


def load_snoop(path):
    path = Path(path)
    if path.stat().st_size > MAX_SIZE:
        raise ValueError('Input too large (>128 MiB)')
    data = path.read_bytes()
    if data.startswith(b'\x1f\x8b'):
        with gzip.open(path, 'rb') as stream:
            data = stream.read(MAX_SIZE + 1)
        if len(data) > MAX_SIZE:
            raise ValueError('Decompressed input too large')
    if len(data) < 16 or data[:8] != HEADER:
        raise ValueError('Expected btsnoop_hci.log / .log.gz, not bugreport ZIP or text')
    version, datalink = struct.unpack_from('>II', data, 8)
    if version != 1 or datalink != 1002:
        raise ValueError(f'Unsupported BTSnoop version={version}, datalink={datalink}; need H4/1002')
    pos = 16
    while pos < len(data):
        if pos + 24 > len(data):
            raise ValueError('Truncated BTSnoop record header')
        original, included, _flags, _drops, stamp = struct.unpack_from('>IIIIQ', data, pos)
        pos += 24
        if included > MAX_SIZE or included > original or pos + included > len(data):
            raise ValueError('Invalid or truncated BTSnoop record length')
        packet = data[pos:pos + included]
        pos += included
        seconds = (stamp - EPOCH_DELTA) / 1_000_000 if stamp >= EPOCH_DELTA else None
        yield seconds, packet


def summarize(path, *, show_names=False, only_targets=False):
    salt = secrets.token_bytes(32)
    devices = {}
    event_count = total = 0
    format_counts = {'legacy': 0, 'extended': 0}
    for seconds, packet in load_snoop(path):
        reports = parse_hci_event(packet)
        event_count += bool(reports)
        for address_type, address, rssi, ad, style, scan_response in reports:
            total += 1
            format_counts[style] += 1
            device_id = hmac.new(salt, bytes([address_type]) + address, hashlib.sha256).hexdigest()[:12]
            if device_id not in devices:
                devices[device_id] = {'deviceId': device_id, 'name': None, 'namePresent': False,
                                      'matchedPrefix': None, 'packets': 0, 'rssiMin': None, 'rssiMax': None,
                                      'companyIds': set(), 'service16': set(), 'service128': set(),
                                      'uartServiceAdvertised': False, 'adPayloadVariants': set(),
                                      'scanResponses': 0, 'firstUTC': None, 'lastUTC': None,
                                      'legacy': 0, 'extended': 0}
            row = devices[device_id]
            row['packets'] += 1
            row[style] += 1
            row['scanResponses'] += int(scan_response)
            if rssi != 127:  # unavailable in HCI
                row['rssiMin'] = min(rssi, row['rssiMin']) if row['rssiMin'] is not None else rssi
                row['rssiMax'] = max(rssi, row['rssiMax']) if row['rssiMax'] is not None else rssi
            if seconds is not None:
                try:
                    iso = datetime.fromtimestamp(seconds, timezone.utc).isoformat()
                    row['firstUTC'] = min(iso, row['firstUTC']) if row['firstUTC'] else iso
                    row['lastUTC'] = max(iso, row['lastUTC']) if row['lastUTC'] else iso
                except (OverflowError, OSError, ValueError):
                    pass
            decoded = parse_ad(ad)
            name = decoded['name']
            if name:
                row['namePresent'] = True
                if show_names:
                    row['name'] = name
                for prefix in PREFIXES:
                    if name.startswith(prefix):
                        row['matchedPrefix'] = prefix
            row['adPayloadVariants'].add(hmac.new(salt, ad, hashlib.sha256).hexdigest()[:16])
            for field in ('companyIds', 'service16', 'service128'):
                row[field].update(decoded[field])
            if UART_SERVICE in decoded['service128']:
                row['uartServiceAdvertised'] = True
    result = []
    for row in devices.values():
        if only_targets and not (row['matchedPrefix'] or row['uartServiceAdvertised']):
            continue
        for field in ('companyIds', 'service16', 'service128'):
            row[field] = sorted(row[field])
        row['adPayloadVariants'] = len(row['adPayloadVariants'])
        if not show_names:
            del row['name']
        result.append(row)
    result.sort(key=lambda r: (not bool(r['matchedPrefix'] or r['uartServiceAdvertised']),
                               -(r['rssiMax'] if r['rssiMax'] is not None else -127),
                               -r['packets']))
    return {'input': Path(path).name, 'hciAdvertisingEvents': event_count,
            'hciAdvertisingReports': total, 'reportFormats': format_counts,
            'distinctAddressesInCapture': len(devices),
            'matchedPrefixDeviceCount': sum(bool(r['matchedPrefix']) for r in devices.values()),
            'uartServiceAdvertisedDevices': sum(bool(r['uartServiceAdvertised']) for r in devices.values()),
            'privacy': 'Addresses pseudonymized with per-run random salt. Names hidden by default. Never publish the original log.',
            'limitations': ['Advertisement match alone does not prove this is a pedestrian signal',
                            'Private BLE address rotation may create multiple IDs per device',
                            'Missing advertisements do not prove the device lacks BLE',
                            'Android HCI logs may be filtered or incomplete',
                            'No connection, GATT, signal-color or remaining-time decoding'],
            'devices': result}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline BLE HCI advertising report analyzer')
    parser.add_argument('file', type=Path, help='btsnoop_hci.log or .log.gz')
    parser.add_argument('--show-names', action='store_true', help='Print local full names; may expose serial/device IDs')
    parser.add_argument('--only-targets', action='store_true', help='Only AHG001+/BHG001+ or advertised UART service')
    parser.add_argument('--output', type=Path, help='Save report locally, not to a public repository')
    args = parser.parse_args(argv)
    try:
        result = summarize(args.file, show_names=args.show_names, only_targets=args.only_targets)
        data = json.dumps(result, ensure_ascii=False, indent=2)
        print(data)
        if args.output:
            args.output.write_text(data, encoding='utf-8')
    except (OSError, ValueError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
