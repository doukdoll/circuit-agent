# SPDM 로컬 점검·SQLite 저장 도구 — 사내 반입용

이미 병합/정제된 SPDM xlsx에서 설정으로 선택한 컬럼을 점검하고 전체 행을 로컬 SQLite에 저장합니다. BOM에서 확인한 SEC 코드로 특정 가져오기 버전의 규칙 목록을 조회할 수 있습니다. 원본 파일은 변경하지 않으며 서버·외부 API·인터넷 연결을 사용하지 않습니다. DRM 해제와 QCV/BOM 파싱·자동 검증은 포함하지 않습니다.

## 준비

이 폴더의 코드·설정·테스트를 반입하고, 폴더에서 PowerShell을 엽니다. Python 3와 사내 환경에 설치된 `openpyxl`이 필요합니다.

```powershell
python -c "import openpyxl; print(openpyxl.__version__)"
```

의존성이 없으면 사내 승인된 설치 경로를 사용합니다. `requirements.txt`는 필요한 패키지 명세이며 이 배포에는 패키지 자체나 Python 실행 파일이 포함되지 않습니다.

## 실제 파일 없이 먼저 검증

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

테스트는 임시 폴더에 가상 Excel과 SQLite를 만들고 실행 후 제거합니다. 실제 회사 파일과 인터넷 연결이 필요하지 않습니다. 25개 테스트가 통과하는지 확인합니다. 이 결과는 실제 SPDM 파일이나 DRM 접근의 성공을 의미하지 않습니다.

## 사내 실제 파일 점검

```powershell
python .\inspect_rules.py `
  "C:\Users\d7983.lee\Downloads\Data\spdm_checkpoint_merged_20261012_160751.xlsx" `
  --report .\local-output\inspection.json `
  --preview 20

$LASTEXITCODE
```

실제 파일 경로가 다르면 첫 인수를 바꿉니다. `--mapping .\my_mapping.json`으로 별도 컬럼 설정을 사용할 수 있습니다. `mapping.json`의 기본 13개 컬럼 선택은 제공된 명세 기반의 초기 제안입니다. 정제 결과 컬럼 이름이 확정되면 해당 필드의 `header`와 필요시 `column`을 수정합니다. 고유 헤더는 `column`을 생략하고 선택할 수 있습니다.

출력 JSON의 `preview`에서 선택된 `raw`와 `selected`를 나란히 비교하고, `issues`와 `duplicate_candidates`를 확인합니다. `--preview 0`은 원문 미리보기만 끄며 전체 행 점검은 유지합니다. 보고서에는 파일명·헤더·문제 위치 정보가 남으므로 이 옵션을 외부 공유용 익명화로 간주하지 않습니다.

종료 코드 0은 변환 오류 없이 점검 완료, 2는 변환 오류 또는 입력/설정 오류입니다. 경고·중복 후보는 자동 삭제하지 않습니다. 데이터 변환 오류가 있으면 보고서를 만들지만 입력 파일·시트·헤더를 읽지 못하면 만들지 않습니다. 이번 실행의 종료 코드를 확인하고 이전 보고서와 혼동하지 않습니다.

## SQLite에 저장

```powershell
python .\import_rules.py `
  "C:\Users\d7983.lee\Downloads\Data\spdm_checkpoint_merged_20261012_160751.xlsx" `
  --db .\local-output\rules.sqlite `
  --report .\local-output\import-result.json `
  --preview 20

$LASTEXITCODE
```

출력의 `batch_id`를 기록합니다. 미리보기 수와 관계없이 완전히 빈 행을 제외한 모든 데이터 행을 저장합니다. 중복 후보·빈 Checkpoint·분류 경고도 보존합니다. 선택 컬럼에 변환 오류가 있거나 저장 중 오류가 발생하면 이번 적재는 전부 취소하고 기존 데이터는 유지합니다. 처음 실패한 경우 내용 없는 DB 파일이 남을 수 있습니다.

같은 파일 바이트·매핑 설정·파서/적재 버전이면 `skipped`와 기존 `batch_id`를 반환합니다. 파일이나 설정이 바뀌면 새 가져오기로 보관하며 기존 규칙은 덮어쓰지 않습니다. 재실행 시에도 현재 파일 이름과 `--preview` 기준으로 점검 보고서를 만듭니다.

기본 13개 필드는 SQLite 컬럼으로, 매핑에 추가한 필드는 `selected_json`으로 저장합니다. 선택된 원문은 `raw_json`, 정제값은 `selected_json`에 모두 보존하며, 입력 파일의 모든 비선택 컬럼을 복사하지는 않습니다. 가져오기에는 파일/설정 해시, 설정 내용, UTC 실행 시각, 행 수와 점검 보고서가 저장됩니다. DB용 매핑에는 `sec_code` 이름과 `sec_code` 타입이 필요합니다.

## BOM에서 찾은 SEC 코드로 규칙 조회

아래 `--batch-id 1`은 예시입니다. 적재 결과로 받은 ID를 사용합니다.

```powershell
python .\query_rules.py .\local-output\rules.sqlite `
  --batch-id 1 `
  --sec-code "03438806" `
  --output .\local-output\matched-rules.json
```

지정한 가져오기에서 해당 SEC의 전체 규칙을 조회합니다. 결과에는 규칙 ID, 원본 행 번호, 규칙 문장·설계치·핀 표현·참조문서, 선택된 원문/정제값, 경고·중복 후보가 포함됩니다. 조회 전용으로 DB를 열고 `--output`을 생략하면 JSON을 출력합니다. 종료 코드 0은 `MATCHED`, 3은 `NOT_FOUND`, 2는 조회 오류입니다. `NOT_FOUND`는 PASS 판정이 아닙니다.

QCV의 참조번호와 BOM을 연결해 찾은 부품 코드를 이 조회 함수에 전달하는 연동은 후속 작업입니다. 현재 조회 코드는 대시 없는 8자리 원본 SEC만 받으며 다른 코드 형식을 임의로 변환하지 않습니다. 부품 참조번호·보드별 실제 값·검증 결과는 규칙 DB에 섞어 저장하지 않습니다. 규칙의 `design_value`는 규칙에 기록된 값이며 실제 회로 관측값이 아닙니다.

적재의 `--report`는 선택 사항입니다. 보고서를 쓸 때는 `status`, `batch_id`, `stored_rows`, `inspection`을 포함합니다. 검증 오류 시 `rejected`와 오류 보고서를 쓰고 종료 코드 2를 반환합니다. 파일/DB 입출력 등 처리 실패에서는 보고서를 만들지 못할 수 있습니다. DB 커밋 후 보고서 파일 쓰기만 실패하면 DB 적재 완료 여부와 `batch_id`를 오류 메시지로 알립니다.

## 반출 없이 개발·검증하는 흐름

외부에서는 제공된 구조 명세와 가상 데이터로 구현하고, 사내에서는 실제 파일로 실행하여 매핑·정제 결과를 확인합니다. 실제 xlsx, SQLite, 점검/조회 보고서, 원문을 포함한 로그는 사내에 유지합니다. 반출 승인이 없는 정보는 가져올 필요가 없습니다. 후속 수정은 공개 가능한 일반적인 증상이나 가상 재현 사례로 검증할 수 있습니다.

`openpyxl`이 파일을 읽지 못하면 사내 Python 실행 환경에서 DRM 보호 파일을 읽을 수 있는지 먼저 확인합니다. 이 도구가 DRM 보호를 해제하거나 우회하지는 않습니다.
