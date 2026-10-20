# Circuit Review SQLite 배포

**[배포 ZIP 다운로드](https://github.com/doukdoll/circuit-agent/raw/refs/heads/feat/circuit-review-sqlite/dist/circuit-review-sqlite.zip)**

압축을 새 폴더에 모두 풀고 setup_rules.py를 Python으로 실행합니다. 빈 DB만 만들거나 실제 원본 23컬럼 CSV와 대응 분석 JSON을 선택해 최초 적재합니다. 자세한 순서는 [실행 안내](../docs/CIRCUIT_REVIEW_RUN.md)를 따릅니다.

| 항목 | 내용 |
| --- | --- |
| 브랜치 | feat/circuit-review-sqlite |
| 스키마 | 14개 테이블·2개 트리거, 별도 DB 형식 버전 3 |
| 환경 | Python 3.10+, SQLite 3.31+ 및 JSON1, 표준 라이브러리 |
| ZIP 내용 | 코드·SQL·실행 안내·버전·체크섬 10개 파일 |
| 데이터 | 실제 CSV/JSON·DB·보고서·가상 데이터 생성기 미포함 |

현재 [소스](../tools/spdm_import)와 [이전 v7 보존 기록](../docs/SPDM_LEGACY_V7.md)을 확인할 수 있습니다. 이전 v7 DB는 자동 변환하지 않습니다. 최초 적재가 끝난 DB를 갱신하는 동기화 기능도 없습니다.

ZIP의 SHA-256은 circuit-review-sqlite.zip.sha256에 기록합니다. ZIP 안의 SHA256SUMS.txt는 압축 해제한 개별 파일의 체크섬입니다. Python 설치 프로그램은 포함하지 않습니다.

2026-10-20 형식 버전 3은 O열 savefolder를 checkpoints의 일반 TEXT 컬럼에 원본대로 저장하며 규칙 번호와의 일치 검사를 하지 않습니다. S~W열 LDRC 5개 값의 체크포인트별 저장은 유지합니다. 부품 공통 값의 실제 차이와 SQL 제약은 계속 검사합니다. 실행 폴더는 네 Python 파일이며 이전 실행 파일은 Git 이력으로 보존합니다.

최신 ZIP 전체를 새 폴더에 풀고 setup_rules.py에서 실제 CSV+JSON을 선택한 뒤 새 circuit_review_v3.db로 적재하세요. 이전 형식 버전 1/2의 DB는 비어 있어도 재사용하거나 자동 변환하지 않습니다. Linux 검사 18개는 통과했지만 실제 SPDM 전체 입력과 이번 수정의 Windows 실행은 아직 확인하지 않았습니다.

이전 게시 이력인 [PR #3](https://github.com/doukdoll/circuit-agent/pull/3)은 사용자 요청으로 닫힌 상태이며 다시 열지 않습니다. [이전 코드의 Windows 검증 결과](https://github.com/doukdoll/circuit-agent/actions/runs/39188935104): Python 3.10/3.12 × PowerShell 5.1/7 네 조합 각각 빈 스키마 테스트 10개 및 초기화 통과. 실제 CSV+JSON 적재와 GUI 직접 클릭은 미검증입니다.
