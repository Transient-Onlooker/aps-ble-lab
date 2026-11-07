# 통합 검증 기록

검증일: 2026-11-07. 기준 main: `6d4c8ada1a8f4963a4f91d3ab8f3481650e56c7e`.
기존 5개 커밋과 `index.html`을 보존한 별도 clone에서 작업했다. SKE 원본 분석 폴더는 변경하지 않았다.

## 실행 결과

| 검증 | 결과 | 입증 범위 |
| --- | --- | --- |
| `python -B -m unittest -v test_tdata_probe` | 13개 통과 | JSON 파싱, raw/null 보존, 문서 예시 밀리초 시각, 단일 지도 요청·캐시/CSV·중복·거리순·조회 제한, 429 무재시도, 빈 검색어, 키 누출 억제, 입력 범위, .env 및 환경변수 우선순위 |
| `python -B test_browser.py` | 통과 | 기존 기본 페이지의 모의 BLE 선택·광고·GATT Read·JSON·해제 |
| `python -B test_observer.py` | 통과 | 이름/서비스 필터, 수동 Read/Notify, DataView 오프셋, 수동 마커, 식별자 제외 JSON, 연결별 세션, 해제 후 콜백 정리·재연결 |
| `python -B research/ske/scripts/verify_evidence.py` | 6개 배열 통과 | 공개 XOR 배열·문자열·역변환 일치 |
| 같은 명령에 `--apk` 지정 | 통과 | 비공개 원본 APK SHA-256, 실제 DEX 배열 6개, XOR 리터럴, 수신경로 감사 JSON 전체 대조 |
| 원본 split 2개 포함 SHA-256 대조 | 3개 일치 | 공개 identity 목록과 비공개 추출본의 무결성 |

환경: Python 3.13.14, Node 26.13.0. 브라우저 테스트는 임시 Python 가상환경의 Playwright 1.64.1 / Chromium 156.0.8078.4에서 수행했다. 실제 블루투스를 대체한 모의 객체만 사용했다. 테스트용 값은 합성값이며 라이브 관측이 아니다.

Python 소스 전체 문법 검사와 `git diff --check`도 실행했다. `.env`는 `git check-ignore`로 제외를 확인했고 공개 파일에는 포함하지 않는다. 공개 후보에서 바이너리·전체 디컴파일·개인 절대경로를 점검했다. `.gitignore`만으로 모든 비밀 누출을 방지하는 것은 아니므로 향후 캡처·인증 응답을 추가할 때도 검토해야 한다.

## 공식 문서 대조

- [10121](https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10121): Map endpoint와 `apiKey` 등 요청 파라미터 및 위치 필드 확인. HTTPS 인증 호출은 미검증.
- [10381](https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10381): 실시간 endpoint, `apikey`, `itstId`, 페이징과 보행 필드·전송 시각 확인. 단위 표기는 문서 내 혼재하므로 raw를 유지.
- [이용안내](https://t-data.seoul.go.kr/userguide/guideopenapi.do): 활용신청·키 발급 필요 확인.

문서의 응답 예시를 이용한 파싱 테스트는 API 인증 호출 성공을 의미하지 않는다. T-DATA 가이드의 기존 종료 일정 안내는 이번 통합에서 별도로 재검증하지 않았다.

## 남은 실측

사용자가 로컬 `.env`에 키를 입력한 뒤 10381 인증 호출이 성공했다. 10121은 6시간 제한으로 중단하고 공식 10144 CSV의 2,779행에서 경찰병원후문 710·경찰병원후문(연등) 20710을 찾았다. 두 ID 모두 실제 보행 필드와 전송 시각을 3회씩 관측했으며 2초당 20 단위 감소는 해당 응답의 0.1초 단위와 일치한다. [실제 관측 요약](../tdata/validation_2026-11-07.json) 및 [T-DATA 가이드](../../TDATA.md) 참조. 키·기기 식별자·전체 CSV는 공개하지 않는다. 10121 성공 응답은 로컬에서 발견되지 않았으며 향후 성공분만 캐싱하도록 구현했다.

실제 횡단보도와 방향·색상/점멸의 대응 및 현장 표시등 대조는 아직 미검증이다. 서브에이전트 독립 검토는 기본 모델 미지원 오류로 실행되지 않아 주 에이전트가 공개 범위를 직접 검토했다.

허가된 시험장치에서의 READ 속성·자발적 Notify·실시간 BLE 현시 존재 여부도 미검증이다. 이 APK의 미발견을 장치 미지원 확정으로 바꾸지 않았다. GitHub Pages 실서비스 배포·Android 기기 BLE 실측·브라우저 API CORS도 검증하지 않았다. 키를 브라우저에 넣지 않고 서버에서 API를 호출하는 별도 연계가 필요하다.
