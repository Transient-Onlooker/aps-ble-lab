# APS BLE Lab — 시각장애인용 음향신호기 BLE/GATT 진단

경찰청 시각장애인용 음향신호기 BLE 식별 규칙을 활용한 연구용 정적 웹앱입니다. **보행 안전 판단용이 아닙니다.** 공공 신호기에 작동 명령이나 GATT 쓰기를 수행하지 않습니다.

## 기능 (v0.2)

- Android Chrome HTTPS에서 Web Bluetooth 장치 선택: 기본 이름 접두어 `AHG001+`, 필요 시 전체 기기 보기
- `requestDevice`에 `optionalServices`로 UART Service UUID를 추가해 **선택 이후** GATT 접근 권한 요청
- 실험적 `requestLEScan` 및 `watchAdvertisements`를 이용한 광고 관찰(RSSI, Manufacturer/Service Data)
- 사용자 명시적 조작 시 GATT 연결 → 표준 Service 확인 → Characteristic UUID/속성 표시 → **read 속성이 있는 값만 읽기** → 연결 해제
- 광고와 GATT 진단 결과를 브라우저 메모리에서 JSON으로 내려받기
- **지원하지 않음:** 명령 전송, GATT Write, Notify 등록, 적·녹색 신호 판정 및 잔여시간 해독

## BLE 표준 식별값

| 구분 | UUID / 접두어 |
| --- | --- |
| 이름 접두어 | `AHG001+` (R01 공개값, R03 현장 적용 여부 미검증) |
| UART Service | `0003cdd0-0000-1000-8000-00805f9b0131` |
| UART TX | `0003cdd1-0000-1000-8000-00805f9b0131` |
| UART RX | `0003cdd2-0000-1000-8000-00805f9b0131` |

이들 UUID로 **서비스를 발견하는 것과 보행신호 상태를 수신하는 것은 다릅니다.** 실제 장치가 현재 규격을 구현하는지 검증되지 않았습니다.

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
