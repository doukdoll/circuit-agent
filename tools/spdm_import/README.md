# SPDM JSON 규칙 DB

입력은 고정 구조의 JSON만 받습니다. Python 3.12 권장, 추가 설치 패키지와 외부 API가 필요 없습니다.

```powershell
python -S .\inspect_json_rules.py "입력.json" --report .\local-output\inspection.json
python -S .\import_rules.py "입력.json" --db .\local-output\rules-v7.sqlite --report .\local-output\import.json
python -S .\query_rules.py .\local-output\rules-v7.sqlite --sec-code "실제 SEC" --output .\local-output\query.json
```

입력에서 확인한 SEC로 최신 규칙을 조회합니다. 전체 설명은 JSON 전용 배포의 `SPDM_JSON_RUN.md`를 따릅니다.

현재 PC를 검증하려면 다음을 실행합니다. Windows가 아니면 Windows 검증 성공으로 기록하지 않습니다.

```powershell
python -S .\verify_environment.py --expect-windows --input "입력.json" --report .\local-output\environment.json
```

원본을 수정하지 않고 임시 경로에서 전체 저장·SEC 조회·타입/근거 보존·변경 입력·잘못된 입력·재실행을 검증합니다. 실제 데이터가 없으면 --input을 생략하여 가상 데이터만 확인할 수 있습니다.

스키마는 최신 규칙 전용 v7이며 checkpoints/rules 두 테이블입니다. 가져오기 이력은 없습니다. 매번 최신 전체 JSON으로 기존 규칙을 교체하며 빠진 규칙은 제거됩니다. 같은 파일도 replaced로 처리하고 행을 누적하지 않습니다. 오류 시 기존 데이터로 롤백합니다. 이전 v1/v2/v3/v4/v5/v6 DB는 변환하거나 덮어쓰지 않으며 새 DB 경로로 원본 JSON을 적재합니다. 세부 규칙은 SEC로 조회하고 `required_design_facts`는 필요한 회로 정보 목록으로 보존합니다. 실제 회로 사실이나 판정 결과를 생성하지 않습니다.

SEC는 비어 있지 않은 문자열이면 길이·하이픈 유무에 관계없이 허용합니다. 하이픈·선행 0·대소문자·공백을 자동 변경하지 않으며 조회는 원문 기준입니다. 빈값·공백만 있는 값·null·숫자 타입은 거부합니다.

적용 범위 applicability:null과 최상위 선택 error 필드를 보존합니다. null은 적용 범위 미제공, error는 원본 분석 오류 정보이며 PASS 판정으로 바꾸지 않습니다. 검사 실패는 environment.json의 failed_step.inspection.issues에서 확인합니다.

두 테이블의 id는 INTEGER PRIMARY KEY AUTOINCREMENT입니다. 같은 DB 파일에서 커밋한 번호를 재사용하지 않으며 최신 규칙 교체 시 부모 연결도 새 ID에 맞춰 생성합니다. SQLite 내부 테이블 sqlite_sequence는 번호 관리용입니다.
