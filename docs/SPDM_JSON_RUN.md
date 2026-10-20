# 전처리 analysis.json → SQLite 규칙 DB 실행 방법

> 이전 JSON 전용 v7의 보존 문서입니다. 원본 코드는 [보존 기록의 Git 링크](SPDM_LEGACY_V7.md)에 있으며 현재 버전은 [CSV+JSON/14테이블 안내](CIRCUIT_REVIEW_RUN.md)를 따릅니다.

작성일: 2026-10-15

2026-10-19 추가: 명령 입력 대신 파일 선택 창으로 사용할 수 있는 setup_rules.py를 추가했다. [Python 실행 안내](SPDM_PYTHON_START.md)를 참고한다. 이 실행기를 포함한 최신 배포본의 테스트는 34개이며 아래 과거 Windows CI의 25개와 구분한다.

## 1. 이번 버전의 범위

```text
analysis.json → 고정 구조 검사 → 체크포인트/세부 규칙 저장
                                 ↓
                         SEC별 최신 규칙 조회
                                 ↓
                     QCV/BOM·Gemini 검증 단계에서 사용
```

입력은 **고정 구조의 JSON만** 받는다. Python 3.12를 권장하며 표준 라이브러리만 사용한다. 추가 패키지·DB 서버·외부 API·Gemini 호출이 필요 없다.

현재 담당 범위는 Rule 파싱·저장·조회다. QCV/BOM에서 실제 회로 사실을 추출하거나 Gemini로 PASS/FAIL을 판정하는 연동은 후속 작업이다.

## 2. 실제 필드와 저장 의미

고정 구조는 코드와 동봉한 `analysis.schema.json`에 정의했다. 해당 파일은 외부에서 다운로드하지 않고 로컬에서 읽는다.

```text
최상위 배열
└── checkpoint_id / row_uid / sec_code / status / error(선택)
    └── analysis
        ├── summary
        ├── issues[]: code / description
        └── checks[]
            ├── requirement_id / sec_code / requirement
            ├── target_description / target_kind
            ├── applicability / level
            ├── required_design_facts[]
            ├── parameters[]: name / qualifier / role / unit / value
            └── evidence[]: field / quote
```

| 입력 | 저장·표시 | 의미 |
| --- | --- | --- |
| `analysis.summary` | `summary`, `checkpoint`, 표시용 `checkPoint` | 보완해서 만든 체크포인트 내용 |
| `requirement` | `specification` 및 조회의 `requirement` | 실제 키는 단수형. `requirements`로 바꾸지 않음 |
| `required_design_facts` | 배열 그대로 저장, 표시용 `설계치` | **앞으로 확인해야 할 설계 정보 목록**. 실제 관측값이 아니므로 `design_value`는 null |
| `target_description` | TEXT | LLM이 대상을 찾는 설명/탐색어. 유일 키가 아님 |
| `target_kind` | TEXT | `power_pin`, `circuit` 등 검사 대상 유형. 저항/커패시터 종류로 추측하지 않음 |
| `parameters` | JSON 배열 | 숫자·문자열·수식·범위·null·단위·연산자를 보존. 수식을 실행하지 않음 |
| `evidence` | JSON 배열 | 출처 필드와 인용문 보존 |
| `analysis.issues` | 부모 체크포인트와 조회 결과에 보존 | 모호함·모순을 해결된 것으로 바꾸거나 삭제하지 않음 |
| `applicability` | TEXT 또는 SQL NULL | 적용 범위 미제공(null)은 그대로 저장하고 경고로 표시 |
| 최상위 `error`(선택) | 부모 raw_json 및 조회의 source_error | 분석 실패 정보 원문 보존. 다른 error 데이터 유형도 JSON 그대로 보존 |

**첨부 데이터에는 독립된 원문 `checkPoint`가 없다.** `original_checkpoint`/`original_checkPoint`는 null이다. `evidence`의 일부 인용문을 합쳐 원문 전체를 만들지 않는다. 원문이 필요하면 별도 원본과 연결해야 한다.

SEC는 비어 있지 않은 문자열이면 길이·숫자·영문·하이픈 유무와 관계없이 허용한다. 8자리·10자리·하이픈 포함 코드를 모두 받을 수 있다. 빈값·공백만 있는 값·null·숫자 타입은 거부한다. 선행 0·하이픈·대소문자·앞뒤 공백을 원문 그대로 저장·조회하며 자동 변환하지 않는다. `1234-567890`과 `1234567890`은 다른 코드다. 부모와 하위 규칙의 SEC도 원문이 같아야 한다.

## 3. Python과 새 ZIP 준비

반입할 파일은 **`spdm-json-v7.zip`**과 이 Markdown이다. 실제 `analysis.json`은 별도로 사내 로컬에 둔다. 코드 ZIP에 실제 입력·DB·보고서는 포함하지 않는다. 이전 배포와 섞지 않고 새 폴더에 푼다.

Python이 없으면 사내 승인 경로 또는 https://www.python.org/downloads/windows/ 의 정식 Windows 설치 프로그램을 사용한다. Python 3.12.x 설치 프로그램이 있는 버전 예시는 https://www.python.org/downloads/release/python-31210/ 이다. 설치 이후 프로그램 실행에 인터넷은 필요 없다.

PowerShell에서 작업 폴더를 만들고 ZIP과 입력을 넣는다.

```powershell
$SpdmRoot = Join-Path $env:USERPROFILE "SpdmJson"
New-Item -ItemType Directory -Path $SpdmRoot -Force | Out-Null
```

```text
C:\Users\<사용자>\SpdmJson\
├── spdm-json-v7.zip
└── data\analysis.json
```

입력을 기존 사내 위치에 두어도 된다. 다음 `$SpdmInput`만 실제 경로로 바꾼다.

```powershell
Expand-Archive `
  -LiteralPath (Join-Path $SpdmRoot "spdm-json-v7.zip") `
  -DestinationPath (Join-Path $SpdmRoot "app")

$SpdmApp = Join-Path $SpdmRoot "app\spdm_json"
$SpdmInput = Join-Path $SpdmRoot "data\analysis.json"
$SpdmOutput = Join-Path $SpdmRoot "local-output"
New-Item -ItemType Directory -Path $SpdmOutput -Force | Out-Null

# 다른 위치에 설치했다면 실제 python.exe 경로로 바꾼다.
$SpdmPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $SpdmPython)) { throw "Python 실행 파일 경로를 확인하세요." }
if (-not (Test-Path $SpdmInput)) { throw "실제 JSON 경로를 지정하세요." }
& $SpdmPython --version
& $SpdmPython -c "import json, sqlite3; print('JSON/SQLite: OK')"
Set-Location $SpdmApp
Get-ChildItem
```

`Activate.ps1`이나 PowerShell 실행 정책 변경은 필요 없다. 이미 압축을 풀었다면 `Expand-Archive`를 반복하지 않는다. 백틱 뒤에는 공백을 붙이지 않는다.

ZIP에는 다음 10개 파일이 있다.

```text
sqlite_store.py
json_rules.py
analysis.schema.json
inspect_json_rules.py
import_rules.py
query_rules.py
test_json_rules.py
verify_environment.py
SPDM_JSON_RUN.md
schema_v7.sql
```

`schema_v7.sql`은 스키마 참조용이다. 직접 실행하지 않아도 프로그램이 DB를 생성한다.

## 4. 실제 입력 없이 테스트

```powershell
& $SpdmPython -m unittest discover -s $SpdmApp -p "test_json_rules.py" -v
if ($LASTEXITCODE -ne 0) { throw "테스트 실패. 반입 파일과 Python을 확인하세요." }
```

기대 결과는 최신 실행기 포함 배포본에서 테스트 34개 통과다. 실행기 추가 이전 배포본은 25개다. 가상 JSON과 임시 DB만 사용한다. 한글·공백 경로, 외부 연결 차단, 원문·타입 보존, 재실행, 실패 시 롤백도 포함한다.

### 네 Windows PC에서 실제 실행 환경을 검증하려면

```powershell
& $SpdmPython -S .\verify_environment.py `
  --expect-windows --input $SpdmInput `
  --report (Join-Path $SpdmOutput "environment.json")
if ($LASTEXITCODE -ne 0) { throw "환경 검증 실패. environment.json을 확인하세요." }
```

성공 시 `status=passed`, `system=Windows`, `windows_verified=true`가 나온다. Linux에서는 이 옵션으로 성공하지 않는다. 원본 JSON을 수정하지 않고 임시 한글/공백 경로에서 전체 규칙 저장·모든 SEC 조회·파라미터/근거 보존·내용 변경·잘못된 입력·재실행을 점검한다. 실제 파일이 없으면 `--input`을 생략한다. 보고서에는 실행 OS와 Python/SQLite 버전, 항목별 결과가 남는다.

환경 보고서가 `inspect_json_rules.py: 종료 2`로 실패하면 실제 입력 검사 결과를 먼저 확인한다. 가상 테스트 통과와 실제 파일의 구조/값 검사는 별개다. 최신 환경 점검기는 `failed_step.stdout`, `failed_step.stderr`, `failed_step.inspection.issues`에 오류 경로와 사유를 남기며 원문 미리보기는 포함하지 않는다. 이전 버전에서 사유가 빈 문자열로 보이면 아래 명령으로 별도 진단한다. 데이터나 판정 조건을 임의로 완화하지 않는다.

```powershell
$SpdmCheck = Join-Path $SpdmOutput ("input-check_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
& $SpdmPython -S .\inspect_json_rules.py $SpdmInput --report $SpdmCheck --preview 0
if (Test-Path $SpdmCheck) {
    $r = Get-Content -LiteralPath $SpdmCheck -Raw -Encoding UTF8 | ConvertFrom-Json
    $r.issues | Where-Object { $_.severity -eq "error" } | Select-Object -First 10 path, reason | Format-List
}
```

## 5. JSON 구조 점검

```powershell
$SpdmStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SpdmInspectionReport = Join-Path $SpdmOutput "inspection_$SpdmStamp.json"
$SpdmImportReport = Join-Path $SpdmOutput "import_$SpdmStamp.json"
$SpdmQueryReport = Join-Path $SpdmOutput "query_$SpdmStamp.json"
$SpdmDb = Join-Path $SpdmOutput "rules-v7.sqlite"

& $SpdmPython .\inspect_json_rules.py $SpdmInput `
  --report $SpdmInspectionReport --preview 3

$SpdmExit = $LASTEXITCODE
if (Test-Path $SpdmInspectionReport) {
    $SpdmInspection = Get-Content -LiteralPath $SpdmInspectionReport -Raw -Encoding UTF8 | ConvertFrom-Json
    $SpdmInspection | Format-List checkpoint_count, data_rows, valid_unique_sec_codes, errors, warnings, source_issue_count
    $SpdmInspection.issues | Format-Table path, severity, code, reason -AutoSize
}
if ($SpdmExit -ne 0) { throw "구조 오류. 이번 보고서의 path/reason을 확인하세요." }
```

이번 첨부본은 **10체크포인트 / 35세부 규칙 / 3SEC / 구조 오류 0개 / 원본 분석 이슈 11개**로 확인했다. 새 파일에서 건수가 달라지는 것은 정상이며 이 숫자를 고정 조건으로 강제하지 않는다.

고정 필드 누락·새 필드·타입 오류·중복 JSON 키·비유한 숫자·부모/하위 SEC 불일치는 오류다. 원본 분석 이슈, 빈 설명, normalized 이외 상태, 중복 requirement_id는 보존하며 경고로 표시한다. `analysis`가 null이거나 checks가 비어 있으면 체크포인트 객체만 저장할 수 있다.

UTF-8과 UTF-8 BOM을 지원한다. `--preview`는 보고서 예제 수이며 전체 검사·저장 수에 영향을 주지 않는다. 원본 파일을 수정하거나 경고 항목을 자동 삭제하지 않는다.

## 6. DB 저장

```powershell
& $SpdmPython .\import_rules.py $SpdmInput `
  --db $SpdmDb --report $SpdmImportReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "적재 실패. 콘솔과 이번 보고서를 확인하세요." }

$SpdmImport = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImport | Format-List status, stored_checkpoints, stored_rows
```

입력을 JSON으로만 해석한다. 입력 형식 선택이나 컬럼 매핑 옵션은 없다. 동봉된 `analysis.schema.json`의 고정 계약을 사용한다.

첫 적재는 imported다. 초기 부분 샘플은 10체크포인트/35규칙이며 사용자가 확인한 사내 입력은 1,000체크포인트/2,572규칙이다. 실제 파일에 따라 출력 건수가 달라진다. 이후 저장은 같은 파일도 `replaced`이며 현재 JSON 전체로 기존 규칙을 교체한다. 이전 규칙이나 가져오기 이력을 누적하지 않는다. 35개에서 36개로 바꾸면 DB에는 36개만 남는다.

**매번 DB에 남길 최신 전체 JSON을 넣는다.** 새 파일에 없는 체크포인트·규칙·SEC는 제거된다. 부분 파일을 추가 업로드해 기존 규칙과 합치는 방식이 아니다. 지금 제공한 부분 샘플을 넣으면 그 부분만 현재 DB에 남는다.

구조 검사는 DB를 열기 전에 수행한다. 기존 규칙 삭제와 새 규칙 삽입은 하나의 트랜잭션으로 실행하며 SQL 오류가 나면 삭제까지 롤백하여 기존 데이터를 유지한다. DB 커밋 후 보고서 쓰기만 실패하면 콘솔에 최신 규칙 반영은 완료됐다고 알려준다. 기존 DB를 삭제하지 말고 출력 경로를 수정해 재실행한다.

## 7. SEC별 규칙 조회

첫 조회는 실제 저장된 미리보기의 SEC를 사용한다.

```powershell
$SpdmSecCode = [string]$SpdmImport.inspection.preview[0].selected.sec_code
& $SpdmPython .\query_rules.py $SpdmDb `
  --sec-code $SpdmSecCode `
  --output $SpdmQueryReport

$SpdmQueryExit = $LASTEXITCODE
if ($SpdmQueryExit -eq 2) { throw "조회 오류. DB/SEC/출력 경로를 확인하세요." }
$SpdmQuery = Get-Content -LiteralPath $SpdmQueryReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmQuery | Format-List source_format, sec_code, match_status
@($SpdmQuery.checkpoints).Count
@($SpdmQuery.rules).Count
$SpdmQuery.rules | Select-Object -First 1 | ConvertTo-Json -Depth 30
```

미리보기를 0으로 지정했거나 세부 규칙이 없다면 입력에서 확인한 SEC를 `$SpdmSecCode`에 직접 지정한다.

| 결과 | 의미 |
| --- | --- |
| MATCHED / 종료 0 | 세부 규칙 조회 성공. PASS 판정은 아님 |
| NO_CHECKS / 종료 3 | 체크포인트는 있지만 세부 규칙 없음. checkpoints의 상태·이슈 확인 |
| NOT_FOUND / 종료 3 | 현재 DB에 해당 SEC 없음 |
| 종료 2 | DB·코드 형식·출력 등의 오류 |

조회에는 다음 필드를 제공한다.

- `requirement_id`, `checkpoint_id`, `row_uid`: 소스 식별자.
- `target_kind`, `target_description`, `applicability`, `level`: 검사 대상과 범위.
- `specification`/`requirement`, `parameters`, `required_design_facts`, `evidence`: 검증기로 넘길 규칙.
- `summary`, `original_checkpoint`, `checkpoint_issues`, `has_preprocessing_issues`: 보완 내용·원문 부재·이슈 구분.
- `source_json_pointer`: 원본 위치. `/0/analysis/checks/0`은 첫 체크포인트의 첫 세부 규칙이다.
- `display_fields`: 표시용 checkPoint/specification/설계치. `설계치_kind=required_design_facts`로 관측값과 구분.

JSON의 `source_row`는 펼친 세부 규칙의 1부터 시작하는 순번이다. 원본 참조는 row_uid/checkpoint_id/JSON 위치로 확인한다.

## 8. 최신 데이터 전용 DB 구조

```text
checkpoints: 현재 JSON의 최상위 객체·summary·status·issues
    └── rules: 현재 checks 각 항목·parameters·required_design_facts·evidence
             checkpoint_db_id → checkpoints.id
```

업무 테이블은 두 개이며 가져오기 이력 테이블과 batch_id는 없다. AUTOINCREMENT를 사용해 SQLite 내부 관리 테이블 sqlite_sequence가 추가로 보일 수 있다. 이는 두 테이블의 번호를 관리하며 과거 규칙을 저장하지 않는다. `rules(sec_code)` 인덱스로 조회하고 `(checkpoint_db_id, source_check_index)`로 항목 위치를 구분한다. target_description은 유일 키가 아니다. 두 테이블의 id는 INTEGER PRIMARY KEY AUTOINCREMENT다. 같은 DB에서 커밋된 ID를 최신 데이터 교체 후 재사용하지 않는다. 동일 규칙의 ID가 갱신 후 유지되는 기능은 아니므로 소스 추적에는 원본 식별자를 함께 사용한다. 새 DB 파일을 만들면 그 파일의 ID 이력이 새로 시작한다. 원본의 checkpoint_id/row_uid/requirement_id와 현재 JSON 위치를 사용한다.

스키마는 ID 재사용 방지를 추가한 v7이다. 이전 v1/v2/v3/v4/v5/v6 DB를 자동 변환하지 않으며 그대로 보존한다. 새 `rules-v7.sqlite` 경로에 원본 JSON을 적재한다. 이후에는 같은 v7 DB를 계속 갱신한다. 다른 용도의 DB나 지원하지 않는 버전은 읽기/적재 모두 거부한다.

새 전체 JSON을 받으면 5장부터 실행한다. 기존 규칙 추가·수정·삭제가 최신 파일대로 반영되며 이전 판본은 보관하지 않는다. 동일 파일을 여러 번 넣어도 현재 행 수만 유지한다. SQLite는 빈 페이지를 다음 저장에 재사용하므로 파일 크기가 삭제 즉시 줄어들지는 않을 수 있지만 과거 규칙 행을 계속 보관하지 않는다.

QCV/BOM 담당자는 `lookup_rules(database, sec_code)` 또는 조회 JSON을 사용할 수 있다. 실제 회로 사실 수집·Gemini 호출·판정은 별도 단계이며 원본의 모순·모호함을 해결됐다고 간주하지 않는다.

## 9. 문제 해결과 보관

| 증상 | 확인 |
| --- | --- |
| schema 파일 없음 | ZIP을 모두 함께 풀었는지 확인 |
| 고정 필드 오류 | 단수 requirement와 필드 대소문자 확인. 입력 컬럼을 임의 변경하지 않음 |
| SEC 오류/부모-하위 불일치 | 문자열·빈값·부모/하위 원문 일치 확인. 하이픈 제거·대소문자 변환·앞뒤 공백 제거는 하지 않음 |
| rejected | 보고서 inspection.issues의 path/reason 확인 |
| 경고 11개 | 이번 파일의 원본 분석 이슈인지 확인. 구조 오류와 구분 |
| NO_CHECKS | 상태·분석 없음·빈 checks 확인. PASS로 처리하지 않음 |
| DB locked | 같은 DB를 쓰는 프로세스를 정리하고 재실행 |
| 이전 DB 버전 오류 | 새 DB 경로에 원본 JSON을 적재. 이전 DB를 삭제/변환하지 않음 |
| 접근/DRM 오류 | 승인된 Python과 사내 접근 조건 확인. 프로그램이 보호를 해제하지 않음 |

PowerShell을 닫으면 변수가 사라진다. 재시작할 때 3장의 경로 변수와 5장의 출력 변수를 복원하고 이미 완료한 압축 해제는 생략한다. 현재 규칙만 조회할 때는 DB 경로와 SEC를 직접 지정한다.

실제 analysis.json, 생성한 DB·점검/조회 보고서는 로컬 산출물이며 실행 ZIP에 포함하지 않는다. 외부 저장소에 게시하지 않는다.

## 10. 검증 범위

v7은 Linux/Python 3.12에서 테스트 25개를 통과했다. 양쪽 테이블의 이전 최대 ID보다 큰 번호가 재적재 후 생성되는지, 원본 규칙 조회와 새 부모/자식 연결·외래키가 유지되는지, 최신 행만 남는지 확인한다. 내부 sqlite_sequence를 업무 테이블 수에서 제외하며 기존 v6 DB는 변형 없이 거부한다. null/error 보존, 실패 진단, SEC 형식, 롤백·비누적 검증도 유지한다.

구현 3b27940은 [v7 Windows CI](https://github.com/doukdoll/circuit-agent/actions/runs/38857144781)에서도 PowerShell 5.1.26100.33438과 7.6.6 각각 테스트 25개 및 JSON CLI 환경 검증 전체를 통과했다. Windows Server 2025/Python 3.12.10/SQLite 3.49.1에서 가상 11체크포인트/35규칙/3SEC JSON을 사용했다. 이는 사내 Windows 11/Python 3.15에서 v7을 적용한 결과와 구분한다.

이전 v6는 [Windows CI](https://github.com/doukdoll/circuit-agent/actions/runs/38844322522)에서 PowerShell 5.1/7 각각 테스트 24개를 통과했다. 사용자는 사내 현재 파일의 구조 검사, 1,000체크포인트/2,572규칙/143SEC 적재, 선택 SEC의 2체크포인트/4규칙 조회와 v6 DDL을 확인했다. 이 결과는 v7을 회사 PC에서 실행한 결과가 아니다.

회사 PC에서는 4장의 명령으로 현재 JSON을 다시 확인한다. 실제 회사 데이터는 외부 CI에 전송하지 않는다. QCV/BOM 사실 추출·Gemini 판정 및 회사 PC 접근/DRM은 별도 범위다.

## 11. 과거 기록: 사내 v5→v6 수동 수정

이 절은 이전 문제의 수정 이력을 보존한다. 현재 v7을 새로 사용할 때는 위 실행 절차를 따르고, 사내 v6 코드에서 ID 정책만 바꿀 때는 다음 12장을 따른다.


이번 오류의 확인 근거·미확인 사항·재현 결과는 [TS-007/TS-008](DEVELOPMENT_HISTORY.md#spdm-트러블슈팅-기록)에 기록했다. 다음은 사용자에게 안내한 **입력 거부와 SQL 저장 제약을 해결하는 최소 변경**이다. 원본 JSON의 null이나 error를 삭제하는 방법이 아니다.

`analysis.schema.json`의 check.properties.applicability:

기존:

```json
"applicability": {"type": "string"},
```

수정:

```json
"applicability": {"type": ["string", "null"]},
```

같은 파일의 checkpoint.properties 마지막 부분:

기존:

```json
"sec_code": {"$ref": "#/$defs/sec"},
"status": {"type": "string", "minLength": 1}
```

수정:

```json
"sec_code": {"$ref": "#/$defs/sec"},
"error": {},
"status": {"type": "string", "minLength": 1}
```

error는 선택 필드이므로 required에는 추가하지 않는다. 필드가 없거나 null이어도 허용하고 존재하면 원문을 보존한다.

`sqlite_store.py`의 스키마 버전:

기존:

```python
SCHEMA_VERSION = 5
```

수정:

```python
SCHEMA_VERSION = 6
```

같은 파일의 rules 테이블:

기존:

```sql
applicability TEXT NOT NULL,
```

수정:

```sql
applicability TEXT,
```

수정 후 먼저 실제 입력 구조를 재검사한다. 오류가 남으면 전체 path/reason을 확인하고 다른 타입/필드의 허용 조건을 추측해서 바꾸지 않는다.

```powershell
$SpdmCheck = Join-Path $SpdmOutput ("input-check_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
& $SpdmPython -S .\inspect_json_rules.py $SpdmInput --report $SpdmCheck --preview 0
if (Test-Path $SpdmCheck) {
    $r = Get-Content -LiteralPath $SpdmCheck -Raw -Encoding UTF8 | ConvertFrom-Json
    $r.issues | Where-Object { $_.severity -eq "error" } | Format-List path, reason
}
```

기존 DB는 변경하지 않는다. 실제 저장 단계에서 다음 새 DB 경로를 사용한다.

```powershell
$SpdmDb = Join-Path $SpdmOutput "rules-v6.sqlite"
```

이 최소 수정으로는 기존 테스트 파일과 환경 점검기의 출력 방식까지 바뀌지 않는다. 당시 v6 전체 배포에는 상세 진단 failed_step, source_error 조회 표시와 null/error 회귀 테스트도 포함한다. 실제 적용한 코드 범위와 실행한 테스트 개수를 함께 기록해야 한다.


## 12. 사내 v6→v7 AUTOINCREMENT 수동 수정

sqlite_store.py 상단:

기존:

```python
SCHEMA_VERSION = 6
```

수정:

```python
SCHEMA_VERSION = 7
```

checkpoints와 rules의 CREATE TABLE 안에 있는 다음 줄을 **두 곳 모두** 바꾼다.

기존:

```sql
id INTEGER PRIMARY KEY,
```

수정:

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
```

외래키 checkpoint_db_id와 소스 식별자들은 수정하지 않는다. 기존 DB 테이블은 코드 수정만으로 바뀌지 않으므로 아래 새 DB에 같은 최신 전체 JSON을 적재한다. 기존 rules-v6.sqlite는 보존한다.

```powershell
$SpdmDb = Join-Path $SpdmOutput "rules-v7.sqlite"
$SpdmImportReport = Join-Path $SpdmOutput ("import_v7_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
& $SpdmPython .\import_rules.py $SpdmInput --db $SpdmDb --report $SpdmImportReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "적재 실패. 콘솔과 보고서를 확인하세요." }
$SpdmImport = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImport | Format-List status, stored_checkpoints, stored_rows
```

이후 query_rules.py도 같은 $SpdmDb를 사용한다. 새 DB의 첫 ID는 처음부터 시작하며 그 파일에 다시 적재할 때부터 기존 번호를 재사용하지 않는다. 새 JSON에서 빠진 규칙 제거와 최신 데이터만 유지하는 정책은 같다.

test_json_rules.py에서 테이블 목록을 읽는 SQL 문자열도 바꾼다. 내부 sqlite_sequence를 업무 테이블로 세지 않기 위한 변경이다.

기존:

```python
"SELECT name FROM sqlite_master WHERE type='table'"
```

수정:

```python
"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
```

실제 DB 확인에서 rules AUTOINCREMENT가 False라면 두 ID 선언의 수정·파일 저장과 $SpdmDb가 가리키는 경로를 먼저 확인한다. 수정 전에 생성한 DB는 재적재만으로 DDL이 바뀌지 않으므로 기존 파일을 보존하고 아직 없는 새 파일명으로 생성한다. 버전 숫자가 7이라는 사실만으로 AUTOINCREMENT가 적용된 것은 아니다.

위 최소 수동 수정만 하면 기존 테스트 개수는 자동으로 늘지 않는다. 배포 코드의 25개 테스트에는 ID 비재사용·부모 재연결 회귀 테스트와 v6 DB 보호 검사까지 포함되어 있다.


## 13. 수동 수정 대신 v7 파일 교체 후 재적재

사내 코드가 일부 수동 수정된 경우 ID 변경 파일만 교체하면 새 테스트가 기대하는 파서/진단 개선과 버전이 섞일 수 있다. spdm-v7-code-replacement.zip에는 다음 8개 코드/계약/테스트 파일만 있으며 실제 입력·DB·보고서는 없다.

```text
sqlite_store.py
json_rules.py
analysis.schema.json
inspect_json_rules.py
import_rules.py
query_rules.py
test_json_rules.py
verify_environment.py
```

탐색기에서 ZIP을 풀고 8개 파일을 현재 SpdmJson/app/spdm_json 폴더에 같은 이름으로 덮어쓴다. 파일 목록은 PowerShell 실행 명령이 아니다. 기존 data/analysis.json과 local-output의 DB·보고서는 그대로 보존한다. 교체 후 해당 코드 폴더의 PowerShell에서 기존 경로 변수를 사용해 다음을 실행한다.

```powershell
$SpdmStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$SpdmDb = Join-Path $SpdmOutput "rules-v7_$SpdmStamp.sqlite"
$SpdmImportReport = Join-Path $SpdmOutput "import_v7_$SpdmStamp.json"
& $SpdmPython -S .\import_rules.py $SpdmInput --db $SpdmDb --report $SpdmImportReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "적재 실패. 콘솔과 보고서를 확인하세요." }
$SpdmImport = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImport | Format-List status, stored_checkpoints, stored_rows
```

새 DB를 만드는 이유는 기존 파일의 테이블 정의가 코드 교체/재적재만으로 바뀌지 않기 때문이다. 이후 조회도 새 $SpdmDb를 사용한다. 동일 입력이라면 앞서 확인한 1,000체크포인트/2,572규칙이 예상되며 실제 파일 변경 시 수치는 달라진다. 적용 확인은 실제 DB의 user_version=7 및 checkpoints/rules 양쪽 CREATE TABLE에 AUTOINCREMENT가 있는지 읽기 전용으로 검사한다. rules False 문제의 사내 수정 후 성공은 아직 확인 대기다.
