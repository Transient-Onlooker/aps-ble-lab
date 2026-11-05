# APS BLE Lab — 한국 음향신호기 BLE 읽기 전용 탐색기

## 개요

경찰청 「시각장애인용 음향신호기 표준규격 R01」(2024-02-29) 및 SafeLight 공개 개발 문서의 BLE 식별 규칙을 바탕으로 만든 모바일 웹 시제품입니다.

- 기본 검색 접두어: `AHG001+` (R01 규격 및 SafeLight 문서에 명시)
- 참고 GATT UART Service UUID: `0003cdd0-0000-1000-8000-00805f9b0131` **참고 표시용이며 이 웹앱은 GATT 연결/읽기/쓰기를 수행하지 않음**
- 버전: `v0.1`, 연구용
- 구현: HTML/CSS/바닐라 JS, 외부 패키지/서버 전송 없음
- 범위: 이름 기반 탐색, 실험적 광고 패킷 수신, 광고 이벤트 타임라인 최대 800개 메모리 저장 및 로컬 JSON 내보내기
- **미구현**: 실제 적색/녹색 판단, 보행 잔여시간, 신호기 작동 요청/제어, GATT 연결 및 쓰기, GPS

## 실행

Web Bluetooth는 대체로 **HTTPS 혹은 localhost**에서만 동작합니다. 휴대폰에서 다운로드한 `file://` URL이나 일반 `http://` 서버에서는 작동하지 않을 수 있습니다.

1. `index.html`을 정적 웹 호스팅(GitHub Pages, Cloudflare Pages, Netlify 등)에 그대로 배포합니다.
2. **Android Chrome**에서 HTTPS 배포 주소로 접속합니다. 일반 Android WebView나 iOS Safari에서는 작동하지 않습니다.
3. `장치 선택하기 (기본)` 클릭 → `AHG001+`로 시작하는 BLE 광고 장치 선택 → 이름/브라우저 ID 확인. 이 동작은 연결을 수행하지 않습니다.
4. 광고 데이터가 필요하다면 Chrome의 `chrome://flags/#enable-experimental-web-platform-features`를 `Enabled`로 설정하고 재시작한 다음, `광고 연속 스캔 (실험)` 또는 `선택 장치 광고 관찰`을 시도합니다. Chrome/기기 버전에 따라 두 기능은 **지원되지 않을 수 있습니다.**
5. 스캔 결과는 탭 메모리에만 저장되며 `JSON 내보내기`로 공유 가능합니다. 앱은 어떤 서버에도 데이터를 업로드하지 않습니다.

GitHub Pages는 리포지토리의 Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/ (root)` 선택 후 사용할 수 있습니다. 웹 호스팅 또는 기기별 정상 동작은 별도 확인이 필요합니다.

## 검사 방법

- 브라우저에서 HTTPS 여부, Web Bluetooth 및 실험 스캔 API 지원 여부가 색상 배지로 표시됩니다.
- 기본 `requestDevice` 경로가 **장치 선택만 하고 `gatt.connect()` 호출하지 않는지** 확인합니다.
- 실험 스캔 시 `advertisementreceived` 이벤트가 들어오면 장치명, RSSI, UUID, ManufacturerData 등을 표시합니다.
- Chrome 실험 스캔 API가 없으면 `광고 연속 스캔` 버튼이 비활성화됩니다. 기본 장치 선택 모드는 별도로 동작합니다.
- 검색 결과가 0개여도 해당 교차로에 BLE 장치가 없다고 단정할 수 없습니다. 선택 창에서 보이지 않는 비연결 광고/브라우저 권한/현장 BLE 모듈 미설치 등의 가능성이 있습니다.

## 보안 / 안전

- **공공시설을 대상으로 쓰기·명령 전송을 하지 않습니다.** `navigator.bluetooth.requestDevice()`, `requestLEScan()`, `watchAdvertisements()` 및 UI 표시 기능만 사용합니다.
- 웹앱의 출력은 보행 안전 결정에 사용하면 안 됩니다.
- 공유 전 JSON 파일의 기기 식별자/주변 사람의 장치 정보 등을 검토해야 합니다.
- R01에서 확인된 식별값을 2026년 R03 설치 장비에도 적용한다고 **가정하지 않습니다.**

## 근거

1. 경찰청 시각장애인용 음향신호기 표준규격 R01(2024-02-29), VII. 부가장치(인쇄본 25~28쪽): https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK00719829&bidPbancOrd=000&fileSeq=4&fileType=
2. SafeLight BLE 구현 문서: https://github.com/hanmango-o/SafeLight-README/blob/master/DOCS.md
3. Web Bluetooth MDN: https://developer.mozilla.org/en-US/docs/Web/API/Bluetooth/requestDevice
4. Chrome 개발 문서: https://developer.chrome.com/articles/bluetooth
5. 웹 블루투스 구현 상태: https://github.com/whatwg/bluetooth/blob/main/implementation-status.md

## 개발 환경 검증

`python test_browser.py` (Python Playwright 및 Chromium 필요)로 장치 선택, 광고 이벤트 핸들링, 출력, JSON 다운로드, 중지, 필터를 모의 시험할 수 있습니다. 실제 Android Chrome 및 BLE 장치 실측 테스트를 대신하지 않습니다.