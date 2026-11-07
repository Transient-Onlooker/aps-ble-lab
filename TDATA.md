# 서울 T-DATA 10381 실시간 보행신호 API 실험

Python 표준 라이브러리로 서울시 **교차로 Map 10121**과 **실시간 신호·잔여시간 10381**을 읽기 전용으로 호출합니다.

공식 문서:
- https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10121
- https://t-data.seoul.go.kr/dataprovide/trafficdataviewopenapi.do?data_id=10381
- https://t-data.seoul.go.kr/userguide/guideopenapi.do

## 준비 및 실행

서울시 통합로그인 후 API 활용신청·인증키 발급이 필요합니다. Python 3만 있으면 됩니다.

    $env:TDATA_API_KEY = '발급받은_인증키'
    py -3 tdata_probe.py --pages 2 --rows 100 --radius 1200 --check 3 --output tdata-local-result.json
    Remove-Item Env:TDATA_API_KEY

교차로 ID가 알려졌으면 --itst-id 20386 옵션으로 10381만 호출할 수 있습니다. **20386은 경찰병원역의 ID가 아니라 공식 예시 ID**입니다.

기준 좌표 37.495750, 127.124320은 경찰병원역 부근 참고값입니다. --lat / --lon으로 변경할 수 있습니다. 첫 2페이지에서 주변 교차로가 검색되지 않으면 --pages를 늘려야 합니다. 기본값은 최대 2회 지도 호출과 최대 3회 신호 호출이며 자동 폴링하지 않습니다.

## 검증 기준

- 10121의 itstId, itstNm, mapCtptIntLat/mapCtptIntLot를 이용해 실제 교차로 후보 확인
- 10381의 *PdsgStatNm 및 *PdsgRmdrCs와 trsmUtcTime을 원본 그대로 기록
- 현시 필드 null은 신호의 적색·녹색 여부를 의미하지 않음
- RmdrCs는 문서에 센티초라는 명칭과 (1/10초)라는 설명이 동시에 있으므로 **초 단위로 변환하지 않음**
- 현재 경찰병원역 근처 실측 커버리지는 아직 검증되지 않음

서울시 공지에 따라 기존 신호 관련 API 3종은 2026-11-15 종료 예정이며 **새 실시간 API 10381을 사용**합니다. 개발자 계정은 안내상 1일 최대 1000회입니다.

인증키를 공개 GitHub Pages JavaScript에 하드코딩하지 마세요. 브라우저 직접 호출의 CORS 허용 여부도 아직 검증되지 않았습니다.

이 데이터는 연구 목적이며 **실제 횡단 안전 판단에 사용하면 안 됩니다.**
