# 서울 T-DATA 10381 실시간 보행신호 API 실험

Python 표준 라이브러리로 서울시 **교차로 MAP CSV 10144 / Map API 10121**과 **실시간 신호·잔여시간 10381**을 검증합니다. 위치 검색은 로컬 CSV·캐시를 우선하며 10121 자동 반복 호출은 하지 않습니다.

공식 문서:
- https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10121
- https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10381
- https://t-data.seoul.go.kr/userguide/guideopenapi.do
- https://t-data.seoul.go.kr/dataprovide/trafficdataviewfile.do?data_id=10144

## 준비 및 실행

서울시 통합로그인 후 API 활용신청·인증키 발급이 필요합니다. Python 3만 있으면 됩니다.

저장소 루트의 로컬 `.env`에서 `TDATA_API_KEY=` 뒤에 발급 키를 넣어도 됩니다. 파일이 없다면 `.env.example`을 `.env`로 복사하세요. 이 파일은 `.gitignore`로 제외되며, 스크립트가 자동으로 읽습니다. 키에 따옴표를 씌울 수 있지만 변수 확장·`export`·줄 끝 주석은 지원하지 않습니다. 환경변수에 값이 있으면 `.env`보다 우선합니다. `.env`를 GitHub Pages나 다른 서버의 공개 디렉터리에 배포하지 마세요.

    $env:TDATA_API_KEY = '발급받은_인증키'
    py -3 tdata_probe.py --itst-id 710 --output tdata-local-result.json
    Remove-Item Env:TDATA_API_KEY

교차로 ID가 알려졌으면 --itst-id 20386 옵션으로 10381만 호출할 수 있습니다. **20386은 경찰병원역의 ID가 아니라 공식 예시 ID**입니다.

기준 좌표 37.495750, 127.124320은 경찰병원역 부근 참고값이며 --lat / --lon으로 변경할 수 있습니다. 10121은 실제 오류 응답에서 **6시간 재호출 제한**이 확인됐습니다. `--pages`는 1만 허용합니다. CSV가 없더라도 지도 캐시를 자동 갱신하거나 다음 페이지를 호출하지 않습니다.

공식 [10144 페이지](https://t-data.seoul.go.kr/dataprovide/trafficdataviewfile.do?data_id=10144)에서 CSV를 내려받아 로컬 `private/`에 보관한 뒤 다음과 같이 실행합니다. CSV 위치 검색만 할 때는 인증키도 필요 없습니다.

    py -3 tdata_probe.py --map-csv private/v2xCrossroadMapInformation-10144.csv --check 0
    py -3 tdata_probe.py --map-csv private/v2xCrossroadMapInformation-10144.csv --check 3 --output tdata-local-result.json

CSV의 `ITST_ID`, `ITST_NM`, `MAP_CTPT_INT_LAT`, `MAP_CTPT_INT_LOT`를 API와 같은 필드로 변환합니다. 성공한 10121 JSON이 이미 있다면 `--map-cache FILE`로 재사용할 수 있습니다. 새로 받을 때만 명시적으로 `--fetch-map --rows 500`을 사용하세요. 이 옵션도 캐시가 있으면 네트워크를 호출하지 않으며, 캐시가 없을 때 1페이지 1회만 요청하여 성공 레코드를 `private/tdata-map-cache.json`에 저장합니다. 한 페이지의 캐시가 전체 지도라고 가정하지 않습니다. 에러·빈 응답은 성공 캐시로 저장하지 않습니다.

## 검증 기준

- 10121의 itstId, itstNm, mapCtptIntLat/mapCtptIntLot를 이용해 실제 교차로 후보 확인
- 10381의 *PdsgStatNm 및 *PdsgRmdrCs와 trsmUtcTime을 원본 그대로 기록
- 현시 필드 null은 신호의 적색·녹색 여부를 의미하지 않음
- RmdrCs는 문서에 센티초라는 명칭과 (1/10초)라는 설명이 동시에 있으므로 **초 단위로 변환하지 않음**
- 경찰병원역 인근 MAP ID 710·20710의 실제 10381 응답 확인. 현장 횡단보도·표시등과의 대조는 미실행

서울시 공지에 따라 기존 신호 관련 API 3종은 2026-11-15 종료 예정이며 **새 실시간 API 10381을 사용**합니다. 개발자 계정은 안내상 1일 최대 1000회입니다.

인증키를 공개 GitHub Pages JavaScript에 하드코딩하지 마세요. 브라우저 직접 호출의 CORS 허용 여부도 아직 검증되지 않았습니다.

## 2026-11-07 코드·공식 문서 대조

| 대상 | 코드와 문서의 대응 | 검증 상태 |
| --- | --- | --- |
| 10121 | `/tapi/v2xCrossroadMapInformation/1.0`, `apiKey`, `type`, `pageNo`, `numOfRows` | 요청 경로·대소문자 일치. 공식 샘플은 HTTP지만 코드는 인증키 보호를 위해 HTTPS 사용; 인증 호출은 미실행 |
| 위치 검색 | `itstId`, `itstNm`, 중심 위경도 기반 거리 또는 이름 포함 검색 | 모의 CLI 테스트로 단일 지도 요청·캐시 재사용·CSV 변환·중복 제거·거리순·조회 개수 제한 검증. 빈 키워드는 이름 검색 비활성화 |
| 10381 | `/tapi/v2xSignalPhaseTimingFusionCurrentInfo/1.0`, `apikey`, `itstId`, `type`, `pageNo`, `numOfRows` | 공식 문서 일치. 선택 파라미터 `sggCd`는 현재 사용하지 않음 |
| 수신값 | `*PdsgStatNm`, `*PdsgRmdrCs`, `trsmUtcTime` | null 보존·차량신호 제외·밀리초 예시 시각 파싱을 모의 응답으로 검증 |

위 표는 문서 대조와 오프라인 테스트 결과이며 API 성공 기록이 아닙니다. `trsmUtcTime`은 전송 시각이지 갱신 주기를 보장하지 않습니다. 실제 값이 오래됐거나 비어 있을 수 있습니다. HTTP 성공에 레코드가 없더라도 인증·권한·파라미터·서비스 오류 여부를 확인해야 하며 곧바로 미지원으로 판단하지 않습니다.

문서의 단위 표기가 혼재하므로 스크립트는 raw를 유지합니다. 아래 실제 시계열은 해당 응답의 **0.1초 단위와 일치**하지만 모든 장치·필드에 대한 보장은 아닙니다. 웹앱에 범용 초 변환이나 색상 표시를 추가하지 않았습니다.

브라우저와 연계할 때 키는 서버 측에 두고, 필요한 상태 필드와 전송 시각만 전달하는 구성을 검토할 수 있습니다. 현 단계의 정적 웹앱에는 키나 실시간 표시를 추가하지 않았습니다. API 방향 코드와 BLE 장치를 연결할 물리 횡단보도 매핑도 필요합니다.

## 실제 인증 호출 및 CSV 확인 (2026-11-07)

공식 10144에서 내려받은 `v2xCrossroadMapInformation.csv`는 **2,779행**이었다. SHA-256: `0f3e178a597dd05345ef0a9ef5d6ba1e317424f71ddff94f05c90fcf7a5248eb`. 원본 CSV는 로컬에 보관하고, 공개 저장소에는 관련 교차로와 키·기기 ID가 없는 관측 요약만 넣었다. 서울특별시 T-DATA 제공, 저작자표시(BY).

| MAP ID | CSV 교차로명 | 기준 좌표까지 거리 | 실제 10381 필드 / 값 |
| --- | --- | --- | --- |
| 710 | 경찰병원후문 | 124m | `sePdsgStatNm=permissive-Movement-Allowed`, `sePdsgRmdrCs=118 → 98 → 78` |
| 20710 | 경찰병원후문(연등) | 271m | `wtPdsgStatNm=permissive-Movement-Allowed`, `wtPdsgRmdrCs=121 → 101 → 81` |

두 ID를 3회씩 관측했다. 데이터 전송 시각은 2026-11-07 **10:59:16~10:59:20 KST**였고 수신 시각 대비 약 **3.6~4.0초** 전이었다. 같은 상태에서 전송 시각 약 2초당 20 단위 감소는 0.1초 단위와 일치한다. 이는 API 시계열 근거이며 현장 계측으로 확정한 지연·단위는 아니다. 방향 `se`, `wt`가 지칭하는 실제 횡단보도, 상태 코드의 현장 적색·녹색·점멸 대응은 추가 대조가 필요하다. null인 다른 방향을 적색이나 미지원으로 해석하지 않는다.

별도 인증 진단용 공식 예시 ID **20386**에서는 `stop-And-Remain → protected-Movement-Allowed` 변화를 관측했다. 이 ID는 경찰병원역으로 표시하지 않는다.

10121은 `HTTP 429 / V2X_REPEAT_CALL_LIMIT`, `limitSeconds=21600`, 다음 호출 가능 시각 `2026-11-07 16:55:05`를 반환했다(서버 본문 표기). 키 실패로 판정하지 않았다. 이 세션에서 로컬 10121 성공 응답은 발견되지 않았고 오류를 캐시하지 않았다. **추가 10121 호출은 중단**했으며 CSV로 대체했다.

실측 근거: [validation_2026-11-07.json](research/tdata/validation_2026-11-07.json). 키와 장비 ID를 제외한 파생 자료이며, 실제 수신 시점과 필드값을 테스트 합성값과 구분한다.

이 데이터는 연구 목적이며 **실제 횡단 안전 판단에 사용하면 안 됩니다.**
