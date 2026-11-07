# SKE 공용리모컨 APK 정적 역공학

Google Play에서 사용자가 직접 설치·ADB 추출한 `kr.sktechnology.remote` **1.5 (versionCode 6)**의 독립 분석이다. 기존 G-EYE+ 분석을 재실행하지 않았다. [조사결과](조사결과.md), [BLE 프로토콜](ble_protocol.md), [통합 검증 기록](VALIDATION.md)을 함께 읽는다.

## 이 저장소에서 확인할 수 있는 것

- `AHG001+`·`BHG001+` 검색과 RSSI 필터, GATT 연결, UUID 생성 및 실제 참조.
- 위치안내·신호안내 쓰기 요청과 Notify의 명령 처리 결과. 명령 송신 도구는 포함하지 않는다.
- 해당 APK에서 실시간 보행 현시·잔여시간·횡단 방향·교차로 ID 파서가 발견되지 않았다는 정적 근거.
- `observer.html`은 별도 수신 실험 도구이며, 공식 앱을 실행하지 않는다. T-DATA는 별도의 서울시 HTTP 데이터 출처다. BLE 장치와 API 교차로 ID의 대응 관계는 미검증이다.

## 재현

저장소 루트에서 Python 3 표준 라이브러리만으로 실행한다.

```sh
python -B research/ske/scripts/verify_evidence.py
python -B -m unittest -v test_tdata_probe
```

첫 명령은 공개 JSON의 XOR 배열과 역변환을 검증한다. 자체 보유 APK까지 대조하려면 저장소 밖에 보관한 APK를 명시한다.

```sh
python -B research/ske/scripts/verify_evidence.py --apk /private/path/base.apk
python -B research/ske/scripts/audit_receive_paths.py /private/path/base.apk --compact
python -B research/ske/scripts/audit_ble_calls.py /private/path/base.apk
python -B research/ske/scripts/audit_passive_ble.py /private/path/base.apk
python -B research/ske/scripts/inspect_dex.py /private/path/base.apk 'LL0;-><clinit>'
```

`--apk`는 SHA-256, 원본 DEX 배열·복원 함수, 수신 경로 감사 JSON을 교차검증한다. `inspect_dex.py`와 `analyze_static.py`는 직접 작성한 부분 DEX/AXML 분석기이며 범용 디컴파일러가 아니다. 외부 의존성이나 BLE 통신이 없다. 감사 결과의 `pc`는 DEX 16비트 코드 단위, `code_off`는 `classes.dex` 내부 바이트 오프셋이다.

브라우저 모의 테스트는 `python -m pip install playwright`, `python -m playwright install chromium` 후 `python -B test_browser.py`, `python -B test_observer.py`로 실행한다. 실제 장치 연결 성공이나 라이브 API 커버리지를 입증하지 않는다.

## 공개 범위

직접 작성한 문서·스크립트와 선별한 증거 JSON만 포함했다. APK·DEX·SO·전체 디컴파일 소스·실장비 캡처·인증키·장치 고유 식별자는 포함하지 않는다. JSON의 개인 절대경로는 파일명으로 축약했다. 원본과 상세 비공개 증거는 로컬 분석 폴더에 보존한다. 공개 JSON은 분석 결과이며 실장비 패킷 캡처가 아니다.
