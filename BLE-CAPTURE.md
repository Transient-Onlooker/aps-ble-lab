# BLE 광고 패킷 분석 실험 (연결·제어 명령 없음)

목표는 앞서 웹앱에서 `AHG001+` 장치를 찾지 못한 원인을 **광고 수신 단계**에서 분리하는 것입니다. 이 자료만으로 현장 기기의 제조사나 보행신호 상태를 확정하지 않습니다.

## 분석 근거

- [SKE 공용리모컨 APK 분석](research/ske/ble_protocol.md): 앱이 `AHG001+`·`BHG001+` 이름 접두어로 검색하며, UART GATT Service `0003cdd0-0000-1000-8000-00805f9b0131`에 연결을 시도함.
- [Android AOSP Bluetooth HCI snoop 안내](https://source.android.com/docs/core/connect/bluetooth/verifying_debugging)
- [Bluetooth SIG LE Advertising Report / Extended Advertising Report](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html)
- [Android AOSP btsnoop 구조·timestamp 기준](https://android.googlesource.com/platform/system/bt/+/sdk-release/hci/src/btsnoop.cc)

## 1. Android에서 로그 수집

1. 개발자 옵션에서 **Bluetooth HCI snoop log**를 활성화합니다. AOSP 안내에 따라 블루투스를 껐다 켜서 로깅을 적용합니다.
2. **안전한 인도**에서 블루투스 스캐너 앱을 열어 **스캔만** 실행합니다. 공공 음향신호기에 GATT 연결하거나 안내 요청·설정 명령을 보내지 않습니다. 블루투스의 active scanning이 Scan Request를 송신할 수 있으므로 RF 무송신 시험이라는 뜻은 아닙니다.
3. 컴퓨터로 bugreport를 받습니다.

```powershell
mkdir private -ErrorAction SilentlyContinue
adb devices
adb bugreport .\private\ble-bugreport.zip
```

4. bugreport ZIP을 열어 `btsnoop_hci.log`를 찾고 `private/btsnoop_hci.log`로 추출합니다. 기기/OS마다 위치가 다르며, 일부 단말은 bugreport 텍스트 안에 압축된 `BTSNOOZ` 자료만 제공합니다. 이 경우 AOSP 공식 `btsnooz.py` 도구로 별도 변환할 수 있습니다. 파일 자체가 없거나 필터링되어 있으면 HCI 로그만으로 단정할 수 없습니다.

일부 Android 버전에서는 다음 경로가 존재하지만, 일반적인 삼성 기기에서는 접근이 거부되거나 파일이 없을 수 있습니다.

```powershell
adb pull /sdcard/btsnoop_hci.log .\private\btsnoop_hci.log
```

## 2. 로컬 분석

Python 3 **표준 라이브러리만** 사용합니다. 앱과 BLE 기기에 접근하지 않으며 로컬 파일만 읽습니다.

```powershell
# 특정 이름 접두어 또는 광고 UUID가 있는 장치만
py -3 ble_adv_snoop.py .\private\btsnoop_hci.log --only-targets

# 탐지된 전체 BLE 광고의 익명화된 요약 (우선 추천)
py -3 ble_adv_snoop.py .\private\btsnoop_hci.log --output .\private\ble-advertisements.json

# 원본 광고 이름 확인: 개인정보 노출 가능, 로컬에서만
py -3 ble_adv_snoop.py .\private\btsnoop_hci.log --show-names
```

`*.log.gz`도 지원합니다. `--only-targets`는 `AHG001+`·`BHG001+` 접두어 또는 **광고에 UART Service UUID가 직접 실린 장치**를 표시합니다. 광고에 서비스 UUID가 없더라도 GATT에서 서비스를 제공할 수 있으므로 검색되지 않았다는 이유로 미지원으로 확정하지 마세요.

분석 결과에는 익명 `deviceId`, 광고 횟수, RSSI 범위, 스캔 응답 여부, Company ID, 16/128-bit Service UUID, 광고 payload 변형 수가 포함됩니다. 기본값은 **실제 BLE 주소·전체 이름·raw payload를 제외**하며 실행 때마다 익명 ID를 새로 생성합니다. 이를 통해 현장 BLE 광고가 계속 변하는지 조사할 수 있지만, 실제 신호 상태를 증명하지는 않습니다.

## 해석 기준

| 결과 | 해석 |
| --- | --- |
| `hciAdvertisingReports > 0` | Android 컨트롤러가 광고 보고 이벤트를 기록함. 웹앱의 실패 원인을 별도로 조사할 수 있음 |
| `matchedPrefixDeviceCount > 0` | SKE 앱의 이름 접두어에 해당하는 광고 존재. **실제 음향신호기라는 확인은 별도** |
| `uartServiceAdvertisedDevices > 0` | 알려진 128비트 GATT 서비스 UUID가 *광고 패킷*에 포함됨. 이후 GATT 접근 가능 여부는 별도 |
| 결과는 있으나 접두어/서비스 0 | 다른 장치명 또는 광고에 UUID 미포함 가능. 제조사나 무지원 결론 불가 |
| 보고 이벤트 0 | 스캔·로그 설정·기기 필터링·지원 여부부터 검토해야 함 |

**다음 단계:** 현장에서 수신한 결과(가급적 익명 요약)를 바탕으로 SKE 앱 검색 조건과 현장 광고를 비교하고, 필요할 때만 허가받은 시험 장치에서 GATT 속성/Notify를 테스트합니다.

**개인정보:** BTSnoop 원본에는 주변 사람의 기기 ID, 블루투스 연결 내역, 개인 데이터가 포함될 수 있습니다. **원본 bugreport, HCI 로그, 전체 광고명 출력은 GitHub에 올리거나 공개 공유하지 마세요.** `private/`는 gitignore되어 있으나 출력물을 옮길 때는 별도 주의가 필요합니다.

## 오프라인 검증

```powershell
py -3 -m unittest -v test_ble_adv_snoop
```

모의 광고 프레임 5개 항목(legacy·extended·128-bit UUID·익명화·형식 오류)을 검증합니다. 실제 현장 패킷 검증은 아직 하지 않았습니다.
