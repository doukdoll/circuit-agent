# 전처리 analysis.json → SQLite 규칙 DB 실행 방법

작성일: 2026-10-15

## 1. 이번 버전의 범위

```text
analysis.json → 고정 구조 검사 → 체크포인트/세부 규칙 저장
                                 ↓
                         batch_id + SEC별 조회
                                 ↓
                     QCV/BOM·Gemini 검증 단계에서 사용
```

입력은 **고정 구조의 JSON만** 받는다. Python 3.12를 권장하며 표준 라이브러리만 사용한다. 추가 패키지·DB 서버·외부 API·Gemini 호출이 필요 없다.

현재 담당 범위는 Rule 파싱·저장·조회다. QCV/BOM에서 실제 회로 사실을 추출하거나 Gemini로 PASS/FAIL을 판정하는 연동은 후속 작업이다.

## 2. 실제 필드와 저장 의미

고정 구조는 코드와 동봉한 `analysis.schema.json`에 정의했다. 해당 파일은 외부에서 다운로드하지 않고 로컬에서 읽는다.

```text
최상위 배열
└── checkpoint_id / row_uid / sec_code / status
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

**첨부 데이터에는 독립된 원문 `checkPoint`가 없다.** `original_checkpoint`/`original_checkPoint`는 null이다. `evidence`의 일부 인용문을 합쳐 원문 전체를 만들지 않는다. 원문이 필요하면 별도 원본과 연결해야 한다.

SEC는 8자리 숫자 문자열과 `4자리-6자리` 문자열을 모두 허용한다. 선행 0과 하이픈을 보존하며 서로 다른 체계를 임의 변환하지 않는다.

## 3. Python과 새 ZIP 준비

반입할 파일은 **`spdm-json-only.zip`**과 이 Markdown이다. 실제 `analysis.json`은 별도로 사내 로컬에 둔다. 코드 ZIP에 실제 입력·DB·보고서는 포함하지 않는다. 이전 배포와 섞지 않고 새 폴더에 푼다.

Python이 없으면 사내 승인 경로 또는 https://www.python.org/downloads/windows/ 의 정식 Windows 설치 프로그램을 사용한다. Python 3.12.x 설치 프로그램이 있는 버전 예시는 https://www.python.org/downloads/release/python-31210/ 이다. 설치 이후 프로그램 실행에 인터넷은 필요 없다.

PowerShell에서 작업 폴더를 만들고 ZIP과 입력을 넣는다.

```powershell
$SpdmRoot = Join-Path $env:USERPROFILE "SpdmJson"
New-Item -ItemType Directory -Path $SpdmRoot -Force | Out-Null
```

```text
C:\Users\<사용자>\SpdmJson\
├── spdm-json-only.zip
└── data\analysis.json
```

입력을 기존 사내 위치에 두어도 된다. 다음 `$SpdmInput`만 실제 경로로 바꾼다.

```powershell
Expand-Archive `
  -LiteralPath (Join-Path $SpdmRoot "spdm-json-only.zip") `
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
schema_v3.sql
```

`schema_v3.sql`은 스키마 참조용이다. 직접 실행하지 않아도 프로그램이 DB를 생성한다.

## 4. 실제 입력 없이 테스트

```powershell
& $SpdmPython -m unittest discover -s $SpdmApp -p "test_json_rules.py" -v
if ($LASTEXITCODE -ne 0) { throw "테스트 실패. 반입 파일과 Python을 확인하세요." }
```

기대 결과는 JSON 전용 테스트 13개 통과다. 가상 JSON과 임시 DB만 사용한다. 한글·공백 경로, 외부 연결 차단, 원문·타입 보존, 재실행, 실패 시 롤백도 포함한다.

### 네 Windows PC에서 실제 실행 환경을 검증하려면

```powershell
& $SpdmPython -S .\verify_environment.py `
  --expect-windows --input $SpdmInput `
  --report (Join-Path $SpdmOutput "environment.json")
if ($LASTEXITCODE -ne 0) { throw "환경 검증 실패. environment.json을 확인하세요." }
```

성공 시 `status=passed`, `system=Windows`, `windows_verified=true`가 나온다. Linux에서는 이 옵션으로 성공하지 않는다. 원본 JSON을 수정하지 않고 임시 한글/공백 경로에서 전체 규칙 저장·모든 SEC 조회·파라미터/근거 보존·내용 변경·잘못된 입력·재실행을 점검한다. 실제 파일이 없으면 `--input`을 생략한다. 보고서에는 실행 OS와 Python/SQLite 버전, 항목별 결과가 남는다.

## 5. JSON 구조 점검

```powershell
$SpdmStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SpdmInspectionReport = Join-Path $SpdmOutput "inspection_$SpdmStamp.json"
$SpdmImportReport = Join-Path $SpdmOutput "import_$SpdmStamp.json"
$SpdmQueryReport = Join-Path $SpdmOutput "query_$SpdmStamp.json"
$SpdmDb = Join-Path $SpdmOutput "rules-json.sqlite"

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

고정 필드 누락·새 필드·타입 오류·중복 JSON 키·비유한 숫자·부모/하위 SEC 불일치는 오류다. 원본 분석 이슈, 빈 설명, normalized 이외 상태, 중복 requirement_id는 보존하며 경고로 표시한다. `analysis`가 null이거나 checks가 비어 있으면 체크포인트 이력만 저장할 수 있다.

UTF-8과 UTF-8 BOM을 지원한다. `--preview`는 보고서 예제 수이며 전체 검사·저장 수에 영향을 주지 않는다. 원본 파일을 수정하거나 경고 항목을 자동 삭제하지 않는다.

## 6. DB 저장

```powershell
& $SpdmPython .\import_rules.py $SpdmInput `
  --db $SpdmDb --report $SpdmImportReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "적재 실패. 콘솔과 이번 보고서를 확인하세요." }

$SpdmImport = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImport | Format-List status, batch_id, stored_rows
$SpdmBatchId = [int]$SpdmImport.batch_id
```

입력을 JSON으로만 해석한다. 입력 형식 선택이나 컬럼 매핑 옵션은 없다. 동봉된 `analysis.schema.json`의 고정 계약을 사용한다.

이번 입력의 첫 적재는 `imported`, `stored_rows=35`가 예상된다. 실제 출력의 batch_id를 기록하며 1이라고 고정하지 않는다. 동일 파일 바이트·계약·파서/적재 버전은 `skipped`와 기존 ID를 반환한다. 내용이 바뀌면 새 ID로 추가하고 과거 규칙은 유지한다.

구조 검사는 DB를 열기 전에 수행한다. SQL 오류가 나면 이번 이력·체크포인트·세부 규칙을 전부 롤백한다. DB 커밋 후 보고서 쓰기만 실패하면 콘솔에 적재 완료 ID를 알려준다. 기존 DB를 삭제하지 말고 출력 경로를 수정해 재실행한다.

## 7. SEC별 규칙 조회

첫 조회는 실제 저장된 미리보기의 SEC를 사용한다.

```powershell
$SpdmSecCode = [string]$SpdmImport.inspection.preview[0].selected.sec_code
& $SpdmPython .\query_rules.py $SpdmDb `
  --batch-id $SpdmBatchId --sec-code $SpdmSecCode `
  --output $SpdmQueryReport

$SpdmQueryExit = $LASTEXITCODE
if ($SpdmQueryExit -eq 2) { throw "조회 오류. DB/ID/SEC/출력 경로를 확인하세요." }
$SpdmQuery = Get-Content -LiteralPath $SpdmQueryReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmQuery | Format-List source_format, batch_id, sec_code, match_status
@($SpdmQuery.checkpoints).Count
@($SpdmQuery.rules).Count
$SpdmQuery.rules | Select-Object -First 1 | ConvertTo-Json -Depth 30
```

미리보기를 0으로 지정했거나 세부 규칙이 없다면 입력에서 확인한 SEC를 `$SpdmSecCode`에 직접 지정한다.

| 결과 | 의미 |
| --- | --- |
| MATCHED / 종료 0 | 세부 규칙 조회 성공. PASS 판정은 아님 |
| NO_CHECKS / 종료 3 | 체크포인트는 있지만 세부 규칙 없음. checkpoints의 상태·이슈 확인 |
| NOT_FOUND / 종료 3 | 해당 가져오기에 해당 SEC 없음 |
| 종료 2 | DB·ID·코드 형식·출력 등의 오류 |

조회에는 다음 필드를 제공한다.

- `requirement_id`, `checkpoint_id`, `row_uid`: 소스 식별자.
- `target_kind`, `target_description`, `applicability`, `level`: 검사 대상과 범위.
- `specification`/`requirement`, `parameters`, `required_design_facts`, `evidence`: 검증기로 넘길 규칙.
- `summary`, `original_checkpoint`, `checkpoint_issues`, `has_preprocessing_issues`: 보완 내용·원문 부재·이슈 구분.
- `source_json_pointer`: 원본 위치. `/0/analysis/checks/0`은 첫 체크포인트의 첫 세부 규칙이다.
- `display_fields`: 표시용 checkPoint/specification/설계치. `설계치_kind=required_design_facts`로 관측값과 구분.

JSON의 `source_row`는 펼친 세부 규칙의 1부터 시작하는 순번이다. 원본 참조는 row_uid/checkpoint_id/JSON 위치로 확인한다.

## 8. DB 구조·기존 DB·데이터 갱신

```text
import_batches: 입력 파일·계약·파서 버전과 가져오기 이력
    ├── checkpoints: 체크포인트 원본 객체·summary·status·issues
    └── rules: checks 각 항목·parameters·required_design_facts·evidence
             └── checkpoint_db_id → checkpoints.id
```

`rules(batch_id, sec_code)` 인덱스로 조회하고 `(checkpoint_db_id, source_check_index)`로 항목 위치를 구분한다. target_description은 유일 키가 아니다.

스키마는 JSON 전용 v3이다. 이전 v1/v2 DB를 자동 변환하지 않으며 그대로 보존한다. 이번 코드로 새 `rules-json.sqlite` 경로에 원본 JSON을 적재한다. 다른 용도의 DB나 지원하지 않는 버전은 읽기/적재 모두 거부한다.

`import_batches`에는 파일·계약 해시와 체크포인트/규칙 건수를 저장한다. 규칙 테이블에는 JSON에 있는 대상·규격·파라미터·근거만 저장한다. 부모 체크포인트와 다른 가져오기의 규칙을 잘못 연결할 수 없도록 복합 외래키로 제한한다.

값만 바뀐 동일 구조 JSON을 받으면 입력 경로를 지정해 5장부터 실행한다. 파서나 매핑을 바꾸지 않는다. 부분 샘플의 규칙을 다른 버전에서 자동 보충하지 않으며 사용할 batch_id를 명시한다. 중복 후보와 원본 이슈도 보존한다.

QCV/BOM 담당자는 `lookup_rules(database, sec_code, batch_id)` 또는 조회 JSON을 사용할 수 있다. 실제 회로 사실 수집·Gemini 호출·판정은 별도 단계이며 원본의 모순·모호함을 해결됐다고 간주하지 않는다.

## 9. 문제 해결과 보관

| 증상 | 확인 |
| --- | --- |
| schema 파일 없음 | ZIP을 모두 함께 풀었는지 확인 |
| 고정 필드 오류 | 단수 requirement와 필드 대소문자 확인. 입력 컬럼을 임의 변경하지 않음 |
| SEC 형식/부모-하위 불일치 | 입력 담당자와 해당 위치 확인. 코드 변환/선행0 복구를 추측하지 않음 |
| rejected | 보고서 inspection.issues의 path/reason 확인 |
| 경고 11개 | 이번 파일의 원본 분석 이슈인지 확인. 구조 오류와 구분 |
| NO_CHECKS | 상태·분석 없음·빈 checks 확인. PASS로 처리하지 않음 |
| DB locked | 같은 DB를 쓰는 프로세스를 정리하고 재실행 |
| 이전 DB 버전 오류 | 새 DB 경로에 원본 JSON을 적재. 이전 DB를 삭제/변환하지 않음 |
| 접근/DRM 오류 | 승인된 Python과 사내 접근 조건 확인. 프로그램이 보호를 해제하지 않음 |

PowerShell을 닫으면 변수가 사라진다. 재시작할 때 3장의 경로 변수와 5장의 출력 변수를 복원하고 이미 완료한 압축 해제는 생략한다. 과거 데이터만 조회할 때는 실제 batch_id와 SEC를 직접 지정한다.

실제 analysis.json, 생성한 DB·점검/조회 보고서는 로컬 산출물이며 실행 ZIP에 포함하지 않는다. 외부 저장소에 게시하지 않는다.

## 10. 검증 범위

JSON 전용 가상 테스트 13개와 첨부 JSON의 전체 저장·조회·원문/타입 보존·재실행을 검증한다. 첨부본은 10체크포인트/35규칙/3SEC이며 분석 이슈 11개를 보존한다. Python `-S`와 패키지 없는 별도 환경에서 확인한다.

환경 검증 보고서의 실제 OS를 기준으로 Windows 검증과 Linux 검증을 구분한다. Windows CI 구성은 가상 데이터만 사용하며 실제 회사 PC의 파일 접근·DRM 조건은 해당 PC에서 `verify_environment.py --expect-windows --input ...`으로 별도 확인한다. QCV/BOM·Gemini 판정은 이 도구의 검증 범위에 포함하지 않는다.
