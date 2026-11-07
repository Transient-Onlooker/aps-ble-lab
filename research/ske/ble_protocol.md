# SKE APK의 BLE 경로

대상 해시·한계는 [조사결과](조사결과.md)에 명시했다. 다음은 앱에서 확인한 구현이며 경찰청 규격 전체와의 적합성 인증이 아니다.

## 장치 탐색과 연결

```text
r3.k/n → r3.j → BluetoothLeScanner.startScan(null, LOW_LATENCY, q3)
  → q3.onScanResult → 이름 접두어/RSSI → o3.run → 발견 목록
장치 선택 → r3.i → BluetoothDevice.connectGatt(autoConnect=false, TRANSPORT_LE, n3)
  → n3.onConnectionStateChange → discoverServices
  → n3.onServicesDiscovered → k3.run → getService/getCharacteristic
  → setCharacteristicNotification → CCCD writeDescriptor
  → n3.onDescriptorWrite → E2.run → r3.f (메인) / r3.U (보조)
```

`startScan`에 `ScanFilter`는 없으며 `q3`가 `AHG001+`, `BHG001+`에 `startsWith`를 적용한다. Manufacturer/Service Data 필터는 발견되지 않았다. MAC 중복 제거, 최초 RSSI 임계값 기본 -85 dBm, 이후 0.7/0.3 EMA가 사용된다. `r3.h`는 최근 30초의 시작 4회 이상을 검사하고 `r3.n`은 지연 재개한다. `r3.k(false, …)`에는 10초 예약이 있다. 이 타이머는 연결 시간제한과 별개다.

일반 모드 `MainActivity.onStop`은 스캔과 연결 종료를 요청하고 `onStart`는 조건부 재개한다. Manifest에 앱 고유 BLE 백그라운드 서비스는 확인되지 않았다. 보조 연결은 `ya.run`의 두 번째 connectGatt 경로다. 실패·해제 콜백은 메인/보조 GATT를 구분해 정리한다. 이전 장치 MAC·경과시간·연결 상태에 따른 복구 분기도 있어 무조건 근접 자동 연결로 일반화할 수 없다.

## UUID와 속성

| 역할 | UUID | 실제 참조 |
| --- | --- | --- |
| 서비스 `L0.c` | `0003cdd0-0000-1000-8000-00805f9b0131` | `k3.run.getService` |
| Notify `L0.d` | `0003cdd1-0000-1000-8000-00805f9b0131` | `getCharacteristic`, 구독 및 수신 UUID 검사 |
| 앱 Write `L0.e` | `0003cdd2-0000-1000-8000-00805f9b0131` | `r3.o`, 보조 연결 쓰기 |
| CCCD `L0.f` | `00002902-0000-1000-8000-00805f9b34fb` | `getDescriptor`, Notify 설정 |

이 명칭은 **앱 관점**이다. 실제 장치의 Primary Service 선언·Characteristic READ/WRITE/NOTIFY/INDICATE 속성은 미실측이다. `r3.o`는 Properties의 WRITE 비트에 따라 쓰기 타입을 고르며 READ를 검증하지 않는다. 앱에 GATT Read 경로는 없고 Notify 구독은 존재한다. Indicate 전용 분기는 확인되지 않았다.

`L0.a(int[])`의 XOR 키는 `0x5A`; `<clinit>` `code_off=348960`, 배열 참조 `pc=5,10,15,20,25,30`. 정수 배열 원본과 복원값·역변환 결과는 [decoded_uuids.json](evidence/decoded_uuids.json)에 있다. 이 값들은 문자열에만 존재하는 것이 아니라 위 GATT 조회에서 사용된다.

## 안내 요청과 수신 처리

`K0`는 `POSITION_GUIDE`, `SIGNAL_GUIDE`, `VOICE_GUIDE`를 구별하고 `r3.o(K0)`에서 짧은 고정 길이 요청을 만든다. 위치/신호 요청의 차이는 명령 필드다. 해당 함수에 가변 길이 데이터·별도 체크섬 계산은 확인되지 않았다. 원본 구현을 분석한 사실과 별개로, 공개 자료에는 장치 작동용 전체 송신 바이트열이나 실행 도구를 포함하지 않는다. 앱 계층의 별도 인증 교환이나 제조사별 실시간 상태 프로토콜 분기는 확인되지 않았다.

```text
위치/신호 버튼 또는 자동 안내
  → MainActivity.G0 등 → r3.o(K0) → cdd2 writeCharacteristic
Notify cdd1 → n3.onCharacteristicChanged → Handler → m3.run
  → 메인 GATT/UUID 일치 검사 → I0 생성 → isAck → 명령 처리 완료/실패 UI
```

**수신 해석은 정확히 구별한다.** `m3.run`은 길이 3바이트 이상이고 첫 바이트가 `0x32`일 때만 응답으로 인정한다. 세 번째 바이트의 하위 nibble이 0이면 `isAck=true`, 상위 nibble은 `deviceSpecInfo`다. 두 번째 바이트의 의미는 이 파서에서 검사하지 않는다. 길이가 더 긴 수신값은 raw로 보관하므로 전체 프레임 길이가 반드시 3이라고 단정하지 않는다. 체크섬·수신 길이 필드 검사는 이 경로에서 발견되지 않았다. 실패 결과를 표시하지만 독립 NAK 패킷 정의까지 입증한 것은 아니다.

`deviceSpecInfo`의 nibble을 실제 제조사 ID나 보행 상태라고 해석할 근거는 없다. ACK UI 외 직접 소비가 발견되지 않았고, 미인식 패킷은 로그 후 반환한다. 보조 GATT Notify도 이 소비자에서는 메인 GATT 동일성 검사로 제외된다. `n3` `code_off=925632 pc=14`는 getValue, `m3` `code_off=917584 pc=58/65/91`은 생성/생성자/isAck 조회다.

## 구독 및 자동 송신 주의

`onDescriptorWrite`는 반환 status를 확인하지 않고 후속 처리한다. UI 연결 완료는 Notify 등록 성공을 증명하지 않는다. 자동 안내 `q0`는 기본 true이며 조건부 반복 콜백이 `r3.o`를 호출할 수 있다. 보조 CCCD 콜백도 `E2.run → r3.U → i3.run(case 8)` 쓰기로 이어질 수 있다. 공식 앱 연결은 수신 전용 시험이 아니다.

`observer.html`은 이 자동 요청을 구현하지 않는다. 허가된 시험 장치에서 속성을 조회하고 수동 구독할 수 있으나, 실제 READ 지원·자발적 Notify·실시간 보행 상태 존재 여부는 아직 미확인이다. 무응답만으로 장치 미지원이라고 판단하지 않는다.
