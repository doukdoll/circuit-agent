# SPDM JSON 규칙 DB

입력은 고정 구조의 JSON만 받습니다. Python 3.12 권장, 추가 설치 패키지와 외부 API가 필요 없습니다.

```powershell
python -S .\inspect_json_rules.py "입력.json" --report .\local-output\inspection.json
python -S .\import_rules.py "입력.json" --db .\local-output\rules-json.sqlite --report .\local-output\import.json
python -S .\query_rules.py .\local-output\rules-json.sqlite --batch-id 1 --sec-code "실제 SEC" --output .\local-output\query.json
```

실제 출력의 batch_id와 입력에서 확인한 SEC를 사용합니다. 전체 설명은 JSON 전용 배포의 `SPDM_JSON_RUN.md`를 따릅니다.

현재 PC를 검증하려면 다음을 실행합니다. Windows가 아니면 Windows 검증 성공으로 기록하지 않습니다.

```powershell
python -S .\verify_environment.py --expect-windows --input "입력.json" --report .\local-output\environment.json
```

원본을 수정하지 않고 임시 경로에서 전체 저장·SEC 조회·타입/근거 보존·변경 입력·잘못된 입력·재실행을 검증합니다. 실제 데이터가 없으면 --input을 생략하여 가상 데이터만 확인할 수 있습니다.

스키마는 JSON 전용 v3입니다. 이전 DB는 변환하거나 덮어쓰지 않으며 새 DB 경로로 원본 JSON을 적재합니다. 세부 규칙은 SEC로 조회하고 `required_design_facts`는 필요한 회로 정보 목록으로 보존합니다. 실제 회로 사실이나 판정 결과를 생성하지 않습니다.
