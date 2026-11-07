# APS BLE Lab — 시각장애인용 음향신호기 BLE/GATT 진단

경찰청 시각장애인용 음향신호기 BLE 식별 규칙을 활용한 연구용 정적 웹앱입니다. **보행 안전 판단용이 아닙니다.** 공공 신호기에 작동 명령이나 GATT 쓰기를 수행하지 않습니다.

## 기능 (v0.3)

- Android Chrome HTTPS에서 Web Bluetooth 장치 선택: 기본 이름 접두어 `AHG001+`, 필요 시 전체 기기 보기
- `requestDevice`에 `optionalServices`로 UART Service UUID를 추가해 **선택 이후** GATT 접근 권한 요청
- 실험적 `requestLEScan` 및 `watchAdvertisements`를 이용한 광고 관찰(RSSI, Manufacturer/Service Data)
- 사용자 명시적 조작 시 GATT 연결 → 표준 Service 확인 → Characteristic UUID/속성 표시 → **read 속성이 있는 값만 읽기** → 연결 해제
- 광고와 GATT 진단 결과를 브라우저 메모리에서 JSON으로 내려받기
- **기본 탐지 페이지:** 제어 명령 전송·GATT Write·Notify 구독 없이 장치 및 GATT 속성 탐지
- **별도 `observer.html` 실험 페이지:** 허가된 시험 장치에서 GATT Notify/Indicate 구독 및 수동 Read, 타임스탬프와 원시 HEX·ASCII 저장, 적색/녹색 전환 시점 수동 표시, JSON 내보내기
- **아직 지원하지 않음:** 적·녹색 자동 판정, 잔여시간 자동 해독, 음향신호기 제어 명령 송신

## BLE 표준 식별값

| 구분 | UUID / 접두어 |
| --- | --- |
| 이름 접두어 | `AHG001+` (R01 공개값, R03 현장 적용 여부 미검증) |
| UART Service | `0003cdd0-0000-1000-8000-00805f9b0131` |
| UART TX | `0003cdd1-0000-1000-8000-00805f9b0131` |
| UART RX | `0003cdd2-0000-1000-8000-00805f9b0131` |

이들 UUID로 **서비스를 발견하는 것과 보행신호 상태를 수신하는 것은 다릅니다.** 실제 장치가 현재 규격을 구현하는지 검증되지 않았습니다.

## 실시간 수신 실험 (검증 전)

1. HTTPS 주소에서 [`observer.html`](observer.html)을 열고, `AHG001+` 또는 `BHG001+` 장치를 선택합니다.
2. 허가받은 시험 장치에서만 `GATT 연결·UUID 조회`를 누릅니다.
3. Notify/Indicate 속성이 확인되면 **수동으로** 구독을 시작하고 원시 바이트의 수신 여부를 확인합니다.
4. 신호 변화가 관찰된다면 안전한 위치에서 적색·녹색 수동 마커를 기록하고 JSON을 내려받아 비교합니다.
5. **수신이 없다는 이유만으로 상태 데이터가 없다고 결론 내릴 수 없습니다.** 장치가 제어 명령 이후에만 응답하는 프로토콜일 수도 있습니다. 이 웹앱은 제어 명령을 보내지 않습니다.

Notify/Indicate 구독 시 BLE 스택이 CCCD 설정을 갱신할 수 있습니다. 즉 이 실험은 완전한 수동 광고 수신이 아니며, 사용 권한이 있는 장치에서만 진행해야 합니다.

## 사용

1. GitHub Pages 등 HTTPS에서 열고 Android Chrome으로 접속합니다.
2. `장치 선택하기 (기본)`을 눌러 일치하는 기기를 선택합니다. 검색되지 않으면 `기본 장치 선택에서 이름 조건 없이 전체 기기 보기`를 선택하고 다시 시도합니다. 임의의 주변 기기를 신호기로 오인하지 마세요.
3. **본인 소유 또는 시험 허가를 받은 장치에서만** `GATT 연결 · 속성 조회`를 눌러 서비스·Characteristic 목록을 확인합니다.
4. 결과가 `표준 UART 서비스를 찾을 수 없음`이면 BLE 비활성화, UUID 변경, 서비스 접근 제한 등 다양한 원인이 가능하며 하나로 단정하지 않습니다.
5. `GATT 연결 해제`를 누르고, 필요한 경우 `JSON 내보내기`로 기록을 저장합니다.

연속 스캔 API는 브라우저별 지원 차이가 크며 Chrome 실험 기능 활성화가 필요할 수 있습니다. Android Chrome 기기 실측·GitHub Pages 실제 반영 여부는 별도 확인해야 합니다.

## 안전/개인정보

- GATT 연결은 광고 수신과 달리 실제 기기와 통신합니다. 허가된 테스트 장치에서만 사용하세요.
- 앱은 `writeValue`, `startNotifications`, 조작 패킷 송신 기능을 구현하지 않습니다.
- 내보낸 JSON에는 장치 이름/브라우저 기기 ID/수신 기록이 포함되므로 공유 전에 점검하세요.
- 수신값을 횡단 안전 판단에 사용하지 마세요.

## 근거와 한계

- [경찰청 2026-02-20 R03 표준규격 공지](https://www.police.go.kr/user/bbs/BD_selectBbs.do?q_bbsCode=1001&q_bbscttSn=20260220173906774) — 2026-09-01 시행 공지. 이 구현의 서비스 UUID와 현장 장비의 일치 여부는 미검증.
- [경찰청 R01 관련 조달 규격](https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK00719829&bidPbancOrd=000&fileSeq=4&fileType=)
- [SafeLight 개발 문서](https://github.com/hanmango-o/SafeLight-README/blob/master/DOCS.md)
- [MDN Web Bluetooth](https://developer.mozilla.org/en-US/docs/Web/API/Bluetooth/requestDevice)

## 테스트

`python test_browser.py` (Playwright/Chromium 필요)은 Web Bluetooth **모의 객체**를 사용합니다. 실제 신호기 연결 성공을 의미하지 않습니다.

## 서울 T-DATA 실시간 보행신호 검증

새 실시간 API 10381의 보행신호 상태·잔여시간과 경찰병원역 주변 교차로 커버리지를 인증키로 검증하는 로컬 도구: [T-DATA 가이드](TDATA.md) / [Python 스크립트](tdata_probe.py). API 키는 GitHub Pages에 올리지 않습니다. 실제 라이브 데이터 검증 전에는 보행신호 표시 기능으로 간주하지 않습니다.
