"""Synthetic offline HCI/LE advertising tests; no actual BLE devices."""
import gzip
import struct
import tempfile
import unittest
from pathlib import Path
import ble_adv_snoop as m


def advertising_data(name=None, company=0x1234):
    fields = [bytes([3, 0xff, company & 255, company >> 8])]
    if name is not None:
        raw = name.encode('utf-8')
        fields.append(bytes([len(raw) + 1, 9]) + raw)
    return b''.join(fields)


def legacy(addr, data, rssi=-64, kind=0):
    body = bytes([0x02, 1, kind, 1]) + addr + bytes([len(data)]) + data + bytes([rssi & 255])
    return bytes([4, 0x3e, len(body)]) + body


def extended(addr, data, rssi=-47):
    item = (struct.pack('<H', 0x10) + bytes([1]) + addr +
            bytes([1, 0, 0xff, 0xff, rssi & 255]) +
            b'\x00\x00' + bytes([0xff]) + b'\x00' * 6 + bytes([len(data)]) + data)
    body = bytes([0x0d, 1]) + item
    return bytes([4, 0x3e, len(body)]) + body


def make_snoop(packets):
    content = b'btsnoop\x00' + struct.pack('>II', 1, 1002)
    for i, packet in enumerate(packets):
        content += struct.pack('>IIIIQ', len(packet), len(packet), 1, 0,
                               m.EPOCH_DELTA + (1794016756 + i) * 1000000) + packet
    return content


class SnoopTests(unittest.TestCase):
    def test_legacy_report_and_scan_response(self):
        addr = b'123456'
        packet = legacy(addr, advertising_data('AHG001+secret'))
        report = m.parse_hci_event(packet)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0][2], -64)
        self.assertEqual(report[0][4], 'legacy')
        self.assertEqual(m.parse_ad(report[0][3])['name'], 'AHG001+secret')
        self.assertEqual(m.parse_ad(report[0][3])['companyIds'], {'0x1234'})
        self.assertTrue(m.parse_hci_event(legacy(addr, advertising_data(), kind=4))[0][5])
        # Two reports in one LE Meta Event are supported.
        repeated = packet[5:]
        body = bytes([0x02, 2]) + repeated + repeated
        self.assertEqual(len(m.parse_hci_event(bytes([4, 0x3e, len(body)]) + body)), 2)

    def test_extended_report(self):
        report = m.parse_hci_event(extended(b'abcdef', advertising_data('BHG001+hidden')))
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0][2], -47)
        self.assertEqual(report[0][4], 'extended')

    def test_uart_advertised_service128(self):
        little_endian_uuid = bytes.fromhex(m.UART_SERVICE.replace('-', ''))[::-1]
        info = m.parse_ad(bytes([17, 7]) + little_endian_uuid)
        self.assertIn(m.UART_SERVICE, info['service128'])

    def test_summary_privacy_and_gzip(self):
        packets = [legacy(b'123456', advertising_data('AHG001+private-mac')),
                   legacy(b'123456', advertising_data(), rssi=-50),
                   extended(b'abcdef', advertising_data('OTHER-PRIVATE'), rssi=-69)]
        with tempfile.TemporaryDirectory() as directory:
            fn = Path(directory) / 'btsnoop_hci.log'
            fn.write_bytes(make_snoop(packets))
            result = m.summarize(fn)
            self.assertEqual(result['hciAdvertisingReports'], 3)
            self.assertEqual(result['matchedPrefixDeviceCount'], 1)
            self.assertEqual(len(result['devices']), 2)
            self.assertEqual(result['devices'][0]['rssiMax'], -50)
            self.assertNotIn('private-mac', str(result))
            self.assertNotIn('123456', str(result))
            self.assertEqual(result['devices'][0]['adPayloadVariants'], 2)
            limited = m.summarize(fn, only_targets=True)
            self.assertEqual(len(limited['devices']), 1)
            self.assertEqual(limited['devices'][0]['matchedPrefix'], 'AHG001+')
            explicit = m.summarize(fn, show_names=True)
            self.assertIn('AHG001+private-mac', str(explicit))
            zipped = Path(directory) / 'btsnoop_hci.log.gz'
            zipped.write_bytes(gzip.compress(fn.read_bytes()))
            self.assertEqual(m.summarize(zipped)['hciAdvertisingReports'], 3)

    def test_truncated_input_rejected_and_malformed_hci_ignored(self):
        self.assertEqual(m.parse_hci_event(b'\x04\x3e\x10\x02\x01'), [])
        self.assertEqual(list(m.extract_reports(b'\x0d\x01\x00')), [])
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'truncated'
            file.write_bytes(b'btsnoop\x00' + struct.pack('>II', 1, 1002) + b'\x00')
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                list(m.load_snoop(file))
            file.write_bytes(b'wrong header')
            with self.assertRaisesRegex(ValueError, 'Expected'):
                list(m.load_snoop(file))


if __name__ == '__main__':
    unittest.main()
