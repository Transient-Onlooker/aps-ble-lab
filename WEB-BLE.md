# BLE 웹 스캔 먼저 해보기 (HCI 로그 없이)

[APS BLE Lab 브라우저 실험실](https://transient-onlooker.github.io/aps-ble-lab/)은 Android Chrome의 Web Bluetooth API로 실험합니다. 공개 페이지를 열 수 없다면 같은 저장소의 `index.html`을 HTTPS로 호스팅해야 합니다.

## 빠른 순서

1. Android Chrome으로 HTTPS 페이지를 엽니다. 블루투스를 켜고 사이트 접근 요청을 허용합니다.
2. **장치 선택하기 (기본)**을 누릅니다. 기본 이름 필터는 `AHG001+`, `BHG001+` **두 개(OR 조건)**입니다. 장치 선택만으로 GATT에 연결되거나 SKE 안내 명령이 실행되지는 않습니다.
3. 검색되지 않으면 **기본 장치 선택에서 이름 조건 없이 전체 기기 보기**를 체크해 다시 실행해 봅니다. 이 방식에서도 브라우저는 전체 탐지 결과, MAC 주소, RSSI를 페이지에 제공하지 않으며, 사용자가 선택한 장치만 반환합니다. BLE 광고 이름이 없을 수도 있습니다.
4. **광고 연속 스캔 (실험)** 버튼을 쓸 수 있다면 이를 먼저 활용합니다. 필터를 기본으로 두면 두 SKE 접두어만, **모든 광고 보기**를 체크하면 더 다양한 광고를 수집합니다. 출력에서 이름·RSSI·UUID·제조사 데이터·서비스 데이터를 살펴볼 수 있습니다.
5. 전송은 자동으로 일어나지 않으며 **JSON 내보내기**를 통해 이 탭의 결과를 로컬 파일로 저장합니다. 공개 공유할 때는 장치 이름과 브라우저별 ID가 포함돼 있는지 확인하세요.

## 실험적 연속 스캔 지원

Chrome의 공식 [Web Bluetooth 스캔 예제](https://googlechrome.github.io/samples/web-bluetooth/scan.html)는 `requestLEScan()`에 실험적 플랫폼 기능이 필요하다고 안내합니다. Android Chrome 주소창에 `chrome://flags/#enable-experimental-web-platform-features`를 입력해 활성화한 뒤 앱을 완전히 재실행할 수 있습니다. 그러나 현재 Android 버전·Chrome 빌드·제조사 정책에 따라 기능이 **여전히 없거나 오류가 날 수 있습니다.** 강제로 사용 가능한 API는 아닙니다.

기본 `requestDevice()`는 별도 실험 플래그 없이도 Android Chrome에서 사용할 수 있는 일반 경로입니다. [MDN `requestDevice()`](https://developer.mozilla.org/en-US/docs/Web/API/Bluetooth/requestDevice) / [Web Bluetooth 구현 현황](https://github.com/whatwg/bluetooth/blob/main/implementation-status.md)

## 브라우저에서 가능한 정보와 제한

| 동작 | 확인 가능 | 확인 불가/주의 |
| --- | --- | --- |
| 기본 장치 선택 `requestDevice` | 사용자가 선택한 장치의 이름, 브라우저 내부 ID | 주변 장치 전체 목록, RSSI, 광고 원시값, MAC, 서비스 세부속성 |
| 실험적 `requestLEScan` | 브라우저가 노출한 RSSI·txPower·광고 UUID·제조사/서비스 데이터 | 실제 HCI 전체 패킷, BLE 주소, GATT 내부 값 |
| 실험적 `watchAdvertisements` | 사용자가 선택한 장치의 광고 이벤트(지원되는 경우) | 다른 장치의 모든 광고 |
| GATT 연결·Read/Notify | 연결·서비스·수신 Characteristic, 수신 원시값 | 연결 없이 확인 불가, 보행신호 색상·시간은 해석 근거 필요 |

브라우저는 권한 모델상 *모든 주변 기기의 MAC 주소나 패킷*을 보여주는 도구가 아닙니다. `requestLEScan`이 지원되지 않으면 Android BLE 스캐너 앱 또는 HCI 로그가 필요한 경우가 생길 수 있습니다.

## 결과 해석

- 기본 선택 창에 `AHG001+` 또는 `BHG001+`가 나온다면 **해당 이름을 가진 BLE 장치가 검색되었다**는 근거입니다. 실제 음향신호기나 교차로와의 연결은 별도 검증입니다.
- 기본 선택 창에 안 나온다고 **음향신호기에서 BLE를 안 쓴다**는 결론은 아닙니다. 해당 이름이 아니거나 스캔 조건·기기·펌웨어가 다를 수 있습니다.
- 장치를 선택한 뒤 GATT/Notify까지 시험하려면 **허가된 시험 장치**에서만 수행하세요. GATT 연결·Notify 구독은 단순 광고 수신과 달리 주변 장치에 설정/통신 요청을 전송할 수 있습니다.
- 이 프로젝트는 보행 안전 판단용이 아니며, 실제 보행신호 색상/잔여시간을 BLE로 확인한 적은 없습니다.

사용자 진단은 먼저 **브라우저의 지원 여부 배지 + 기본 장치 선택 결과**부터 시작하고, 실험적 스캔 지원 시에만 광고 데이터를 모읍니다. HCI 로그는 마지막 수단입니다.
