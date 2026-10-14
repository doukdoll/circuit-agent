# SPDM 규칙 DB — 빈 Windows 환경에서 처음 실행하기

작성일: 2026-10-14 / 예정 실행일: 2026-10-15

## 0. 오늘 준비할 것과 내일의 목표

내일의 목표는 **병합/정제된 규칙 Excel 점검 → SQLite 저장 → SEC 코드별 규칙 조회**다.

조건은 다음과 같다.

- Windows PC에 Python·Git·개발 도구가 없다고 가정한다.
- 인터넷은 사용 가능하다. Python과 패키지는 설치 단계에서 다운로드할 수 있다.
- 프로그램은 외부 API·Gemini·클라우드·서버 없이 로컬에서 실행한다.
- 실제 회사 파일과 DB·보고서는 사내에 유지한다.

**설치용 다운로드와 실행 중 외부 API 호출은 별개다.** 패키지 저장소 접근까지 제한된 환경이면 마지막의 오프라인 설치 대안을 사용한다.

### 오늘 가져갈 파일

1. **`spdm-import-sqlite.zip`**: SQLite 저장이 포함된 최신 ZIP. 이전 `spdm-import-starter.zip`은 점검 전용이다.
2. **이 Markdown 파일**: 코드 ZIP과 별도로 함께 가져간다. 메모장으로도 읽을 수 있다.

코드 ZIP에는 Python이나 패키지 설치 파일이 없다. 반입 절차에 따라 두 파일을 준비한다. 실제 사내 xlsx를 밖으로 가져올 필요는 없다.

### 현재 구현 범위

규칙 파싱·점검·DB 저장·조회까지 구현되어 있다. **QCV/BOM 자동 파싱·규칙 연결·회로 PASS/FAIL 판정은 아직 연동하지 않았다.** 이번 실행은 그 검증 도구에서 사용할 규칙 DB를 준비하는 단계다.

SQLite는 Python 표준 라이브러리에 포함되어 있어 DB 서버를 설치하지 않는다. Git, JDK, Maven, Docker, Gemini CLI, API 키, DB 관리 GUI, VS Code도 필요하지 않다. 일반 xlsx 읽기에는 Microsoft Excel도 필수가 아니지만 사내 DRM 파일을 읽을 수 있는 실행 환경은 별도로 필요하다.

## 1. Python을 설치한다

사내에서 지정한 Python 배포 경로가 있으면 먼저 사용한다. 직접 다운로드할 수 있다면 공식 Windows 설치 프로그램을 사용한다.

- 공식 안내: https://www.python.org/downloads/windows/
- 이 문서의 설치 예시: **Python 3.12.x, Windows 64-bit 정식 설치 프로그램**.
- Windows 설치 프로그램이 제공되는 버전 예시: https://www.python.org/downloads/release/python-31210/

설치 순서:

1. 대상 PC가 일반적인 64비트 Windows라면 `Windows installer (64-bit)`를 받는다. ARM64/32비트 PC라면 해당 아키텍처와 승인된 설치 방법을 확인한다.
2. `pip`가 포함된 일반 설치를 사용한다. embeddable ZIP이나 소스 압축 파일을 받지 않는다.
3. 사용자별 설치가 가능하다면 해당 방식으로 설치한다. 설치 권한이 제한되면 사내 배포 담당자를 통해 설치한다.
4. 실제 설치 위치를 확인한다. 아래 명령은 `%LOCALAPPDATA%\Programs\Python\Python312`에 설치했다고 가정한다.

PowerShell을 열고 확인한다.

```powershell
$SpdmBasePython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"

if (-not (Test-Path $SpdmBasePython)) {
    throw "SpdmBasePython을 실제 설치한 python.exe 경로로 바꾸세요."
}

& $SpdmBasePython --version
& $SpdmBasePython -c "import sys, sqlite3, venv; print(sys.executable); print('SQLite:', sqlite3.sqlite_version)"
```

기대 결과: Python 버전·실행 파일 경로·SQLite 버전 표시. 이후 실행 파일의 전체 경로를 사용하므로 PATH 설정에 의존하지 않는다. Store 설치 안내가 뜨면 실제 설치된 실행 파일을 지정한 것이 맞는지 확인한다.

## 2. 로컬 작업 폴더를 만들고 ZIP을 둔다

```powershell
$SpdmRoot = Join-Path $env:USERPROFILE "SPDMOffline"
New-Item -ItemType Directory -Path $SpdmRoot -Force | Out-Null
Set-Location $SpdmRoot
```

허용된 반입 경로로 가져온 `spdm-import-sqlite.zip`과 이 문서를 `$SpdmRoot`에 둔다. `SPDMOffline`은 로컬 작업 폴더 이름이며 설치 단계에서 인터넷을 사용하는 데는 문제가 없다.

```text
C:\Users\<사번>\SPDMOffline\
├── SPDM_WINDOWS_FIRST_RUN.md
└── spdm-import-sqlite.zip
```

실제 규칙 Excel은 사내의 기존 위치에 두고 그 경로를 사용할 수 있다.

## 3. ZIP을 풀고 9개 파일을 확인한다

```powershell
Expand-Archive `
  -LiteralPath (Join-Path $SpdmRoot "spdm-import-sqlite.zip") `
  -DestinationPath (Join-Path $SpdmRoot "app")

$SpdmApp = Join-Path $SpdmRoot "app\spdm_import"
$SpdmOutput = Join-Path $SpdmRoot "local-output"
New-Item -ItemType Directory -Path $SpdmOutput -Force | Out-Null
Set-Location $SpdmApp
Get-ChildItem
```

ZIP 내부에 `spdm_import` 폴더가 있으므로 실제 코드 위치는 `app\spdm_import`다. 다음 9개 파일이 있어야 한다.

```text
inspect_rules.py
sqlite_store.py
import_rules.py
query_rules.py
mapping.json
requirements.txt
test_inspect_rules.py
test_sqlite_store.py
README.md
```

이미 압축을 풀었다면 `Expand-Archive`를 반복하지 않고 해당 폴더를 사용한다. PowerShell의 줄 끝 백틱(`) 뒤에는 공백을 넣지 않는다. 줄바꿈 복사가 어렵다면 해당 명령을 한 줄로 이어서 실행해도 된다.

## 4. 전용 Python 환경을 만든다

```powershell
& $SpdmBasePython -m venv (Join-Path $SpdmRoot "venv")
if ($LASTEXITCODE -ne 0) {
    throw "가상 환경 생성 실패. Python 설치 구성과 사내 실행 권한을 확인하세요."
}

$SpdmPython = Join-Path $SpdmRoot "venv\Scripts\python.exe"
& $SpdmPython --version
& $SpdmPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) {
    throw "pip 준비 실패. pip/venv가 포함된 정식 Python 설치를 확인하세요."
}
```

`ensurepip`는 Python에 포함된 설치 자료를 사용한다. `Activate.ps1`을 실행하지 않고 가상 환경의 실행 파일을 직접 호출하므로 PowerShell 실행 정책을 바꾸지 않는다.

## 5. 필요한 패키지 두 개를 설치한다

인터넷 또는 사내 패키지 저장소를 통해 설치할 수 있는 경우:

```powershell
& $SpdmPython -m pip --disable-pip-version-check install `
  "openpyxl==3.1.5" "et-xmlfile==2.0.0"

if ($LASTEXITCODE -ne 0) {
    throw "패키지 설치 실패. 사내 패키지 저장소 설정 또는 오프라인 설치 대안을 확인하세요."
}

& $SpdmPython -c "import openpyxl, et_xmlfile, sqlite3; print('openpyxl:', openpyxl.__version__); print('et-xmlfile: OK'); print('SQLite:', sqlite3.sqlite_version)"
```

기대 결과: `openpyxl: 3.1.5`, `et-xmlfile: OK`, SQLite 버전 표시.

이 두 패키지는 설치 시 다운로드하는 라이브러리다. 이후 Excel 파싱·DB 저장·조회가 외부 API를 호출하지는 않는다. 위 버전은 현재 검증에 사용한 버전이다. 인터넷이 있어도 PyPI가 차단될 수 있으므로, 실패 시 사내 저장소/배포 경로 또는 17장의 오프라인 설치를 사용한다. 인증서 검증을 끄거나 방화벽을 우회하지 않는다.

## 6. 회사 파일 없이 먼저 테스트한다

```powershell
& $SpdmPython -m unittest discover -s $SpdmApp -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) {
    throw "가상 데이터 테스트 실패. 실제 적재 전에 설치 환경과 반입 파일을 확인하세요."
}
```

기대 결과:

```text
Ran 25 tests ...
OK
```

테스트는 임시 폴더에 가상 Excel·DB를 만들고 삭제한다. 사내 파일과 외부 API가 필요 없다. 현재 Linux 환경에서 통과했으며 Windows에서는 이 단계로 확인한다. 테스트 통과가 DRM 파일 접근까지 보장하지는 않는다.

## 7. 실제 파일 경로와 사용할 매핑을 정한다

기본 입력 경로는 전달받은 파일명을 사용한 예시다. 병합/정제 완료 파일의 위치가 다르면 `$SpdmInput`을 실제 경로로 바꾼다.

```powershell
$SpdmInput = Join-Path $env:USERPROFILE "Downloads\Data\spdm_checkpoint_merged_20261012_160751.xlsx"
if (-not (Test-Path $SpdmInput)) {
    throw "SpdmInput을 실제 병합/정제 완료 xlsx 경로로 바꾸세요."
}

$SpdmMapping = Join-Path $SpdmRoot "mapping.local.json"
Copy-Item -LiteralPath (Join-Path $SpdmApp "mapping.json") -Destination $SpdmMapping

$SpdmDb = Join-Path $SpdmOutput "rules.sqlite"
$SpdmRunStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SpdmInspectionReport = Join-Path $SpdmOutput "inspection_$SpdmRunStamp.json"
$SpdmImportReport = Join-Path $SpdmOutput "import_$SpdmRunStamp.json"
$SpdmQueryReport = Join-Path $SpdmOutput "query_$SpdmRunStamp.json"
```

매핑 복사는 처음 한 번만 한다. 이미 편집한 `mapping.local.json`이 있다면 복사를 다시 하지 않는다. 실행마다 보고서 이름을 구분하여 이전 보고서를 이번 실행 결과로 오인하지 않도록 한다.

### 기본 설정 확인

- 시트명: `병합결과`와 정확하게 일치.
- 선택 열: A/B/C/F/G/H/I/J/K/L/M/Q/R의 13개.
- A/B와 H/I의 `adminno`·`seqno`는 서로 구분.
- SEC: 대시 없는 ASCII 숫자 8자리 문자열. 선행 0 보존.
- 문장: 앞뒤 공백과 줄바꿈 형식만 정리하고 숫자·단위·조건·핀 표현·`|`는 유지.
- 중복 후보·빈 Checkpoint·분류 경고는 자동 삭제하지 않음.

정제 담당자가 추가한 결과 컬럼을 사용한다면 해당 헤더를 확인하고 매핑을 편집한다.

```powershell
notepad $SpdmMapping
```

예를 들어 실제 고유 헤더가 `Checkpoint_cleaned`인 경우, 기존 `checkpoint` 필드 객체만 다음처럼 바꿀 수 있다. 나머지 설정은 유지한다. 이 컬럼명은 예시다.

```json
{"name": "checkpoint", "header": "Checkpoint_cleaned", "type": "text"}
```

`column`을 제거하면 고유 헤더로 찾고, 중복 헤더라면 실제 열도 지정한다. JSON은 UTF-8 또는 UTF-8 BOM으로 저장한다. 빈 정제값을 원문으로 자동 대체하지 않는다. DB 적재용 `sec_code` 이름과 `sec_code` 타입 매핑은 유지한다.

## 8. 실제 Excel을 먼저 점검한다

```powershell
& $SpdmPython (Join-Path $SpdmApp "inspect_rules.py") $SpdmInput `
  --mapping $SpdmMapping `
  --report $SpdmInspectionReport `
  --preview 20

$SpdmInspectExit = $LASTEXITCODE

if (Test-Path $SpdmInspectionReport) {
    $SpdmInspection = Get-Content -LiteralPath $SpdmInspectionReport -Raw -Encoding UTF8 | ConvertFrom-Json
    $SpdmInspection | Format-List data_rows, empty_rows, valid_unique_sec_codes, errors, warnings
    $SpdmInspection.issues | Format-Table row, field, severity, reason -AutoSize
}

if ($SpdmInspectExit -ne 0) {
    throw "점검 실패. 15장의 문제 해결 순서로 확인한 뒤 이 단계부터 다시 실행하세요."
}
```

확인할 내용:

1. 선택열과 실제 헤더가 맞는지.
2. `errors`가 0인지. 경고·중복 후보는 별도 검토한다.
3. 행 수와 고유 SEC 수가 실제 파일 규모에 맞는지. 전달받은 파일의 7,252행/901개는 참고값이며 버전이 다르면 달라도 된다.
4. 원문과 정제값에서 조건·단위·핀 표현이 보존되는지.

```powershell
$SpdmInspection.preview | Select-Object -First 3 | ConvertTo-Json -Depth 10
```

보고서와 원문 출력은 사내에서 확인한다. `--preview 0`은 미리보기만 끄고 전체 검사는 유지한다. 파일명·헤더·문제 위치는 남으므로 외부 공유용 익명화 옵션은 아니다.

`File is not a zip file`이나 접근 거부가 발생하면 DB 단계로 넘어가기 전에 15장의 DRM 항목을 확인한다.

## 9. 전체 규칙을 SQLite에 저장한다

```powershell
& $SpdmPython (Join-Path $SpdmApp "import_rules.py") $SpdmInput `
  --mapping $SpdmMapping `
  --db $SpdmDb `
  --report $SpdmImportReport `
  --preview 20

$SpdmImportExit = $LASTEXITCODE
if ($SpdmImportExit -ne 0) {
    throw "적재 명령 실패. 콘솔과 이번 실행 보고서를 확인하세요. 기존 DB는 삭제하지 마세요."
}

$SpdmImportResult = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImportResult | Format-List status, batch_id, stored_rows
$SpdmBatchId = [int]$SpdmImportResult.batch_id
```

기대 결과:

```text
상태=imported, batch_id=<가져오기 ID>, 저장행=<실제 행 수>, 오류=0, ...
```

이미 같은 입력을 저장했다면 `skipped`도 정상이다. `batch_id`는 실제 결과에서 받으며 무조건 1이라고 가정하지 않는다.

미리보기 수와 무관하게 모든 데이터 행을 저장한다. 완전히 빈 행만 제외한다. 선택된 원문/정제값·원본 행 번호·추가 선택 필드·경고·중복 후보와 가져오기별 파일/설정 해시 등을 보관한다. 입력 Excel은 수정하지 않는다. 변환·SQL 오류가 생기면 이번 적재 전체를 취소하고 기존 데이터는 유지한다. 처음 실패하면 내용 없는 DB 파일이 남을 수 있다.

## 10. 실제 저장된 행 수를 확인한다

DB 관리 프로그램을 설치하지 않고 Python 표준 라이브러리로 확인한다.

```powershell
$SpdmCountScript = @'
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

uri = Path(sys.argv[1]).resolve().as_uri() + '?mode=ro'
batch_id = int(sys.argv[2])
with closing(sqlite3.connect(uri, uri=True)) as connection:
    batch = connection.execute('SELECT row_count FROM import_batches WHERE id=?', (batch_id,)).fetchone()
    if batch is None:
        raise SystemExit('지정한 가져오기가 없음')
    actual = connection.execute('SELECT COUNT(*) FROM rules WHERE batch_id=?', (batch_id,)).fetchone()[0]
    print('batch_id:', batch_id)
    print('기록된 행 수:', batch[0])
    print('실제 저장 행 수:', actual)
    if batch[0] != actual:
        raise SystemExit('행 수 불일치')
'@

& $SpdmPython -c $SpdmCountScript $SpdmDb $SpdmBatchId
if ($LASTEXITCODE -ne 0) {
    throw "DB 행 수 확인 실패. DB 경로와 batch_id를 확인하세요."
}
```

기대 결과: 두 행 수가 같고 9장의 `stored_rows`와 일치한다. 해당 가져오기만 확인하며 다른 버전까지 합산하지 않는다.

## 11. SEC별 규칙을 조회한다

첫 조회는 실제 저장한 미리보기의 SEC를 사용한다. 임의의 예시코드를 조회해서 미매칭을 설치 실패로 착각하지 않도록 한다.

```powershell
$SpdmSecCode = [string]$SpdmImportResult.inspection.preview[0].selected.sec_code

& $SpdmPython (Join-Path $SpdmApp "query_rules.py") $SpdmDb `
  --batch-id $SpdmBatchId `
  --sec-code $SpdmSecCode `
  --output $SpdmQueryReport

$SpdmQueryExit = $LASTEXITCODE
if ($SpdmQueryExit -eq 2) {
    throw "조회 오류. DB/가져오기 ID/SEC 형식을 확인하세요."
}

$SpdmMatched = Get-Content -LiteralPath $SpdmQueryReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmMatched | Format-List batch_id, sec_code, match_status
@($SpdmMatched.rules).Count
```

기대 결과: `MATCHED`, 규칙 1개 이상. 여러 체크포인트가 조회될 수 있다. `--preview 0`으로 적재했다면 위 자동 코드 선택 대신 실제 입력에서 확인한 8자리 SEC를 `$SpdmSecCode`에 직접 넣는다.

| 결과 | 의미 |
| --- | --- |
| `MATCHED` / 종료 0 | 규칙을 찾음. 회로 PASS는 아님. |
| `NOT_FOUND` / 종료 3 | 해당 가져오기에 해당 SEC의 규칙 없음. 코드·설정·버전을 확인. |
| 종료 2 | DB·가져오기 ID·코드 형식·출력 경로 등의 오류. |

## 12. QCV·BOM과 연결할 준비 상태를 확인한다

현재 준비된 연결 지점은 다음과 같다.

```text
QCV에서 부품 참조번호·핀/넷 확인
              ↓
BOM에서 해당 참조번호의 SEC 확인
              ↓
이 DB에서 batch_id + SEC로 규칙 전체 조회
              ↓
실제 회로 사실 + 규칙을 검증기에 전달 (후속 구현)
```

BOM에서 코드를 확인할 수 있다면 `$SpdmSecCode`를 그 값으로 바꾸고 11장의 조회를 실행할 수 있다. 현재 도구가 QCV/BOM을 직접 읽지는 않는다.

원본 규칙의 숫자 8자리 코드와 BOM의 다른 코드 체계 사이 관계가 확인되지 않았다면 변환 기준을 정해야 한다. 하이픈을 제거하거나 0을 붙여 임의 매칭하지 않는다. 규칙의 `design_value`는 규칙에 기록된 값이며 실제 회로 관측값이 아니다.

## 13. 같은 입력을 다시 저장해 본다

입력과 매핑을 바꾸지 않고 재실행한다.

```powershell
$SpdmRepeatReport = Join-Path $SpdmOutput "import_repeat_$SpdmRunStamp.json"

& $SpdmPython (Join-Path $SpdmApp "import_rules.py") $SpdmInput `
  --mapping $SpdmMapping `
  --db $SpdmDb `
  --report $SpdmRepeatReport `
  --preview 20

if ($LASTEXITCODE -ne 0) {
    throw "재실행 실패. 이번 오류를 확인하세요."
}

$SpdmRepeat = Get-Content -LiteralPath $SpdmRepeatReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmRepeat | Format-List status, batch_id, stored_rows
```

동일 파일 바이트·설정·파서/적재 버전이면 `skipped`와 같은 ID가 나와야 한다. 입력/설정이 바뀌면 새 ID를 만들고 과거 규칙은 유지한다. 예상과 다르면 파일 바이트나 설정이 바뀌었는지 확인한다.

규칙 내용의 중복 후보는 보존하며, 동일 입력을 반복 저장하는 중복만 방지한다. 조회할 때 사용할 ID를 명시하여 여러 버전을 섞지 않는다.

## 14. 결과를 사내에 보관한다

보관할 항목:

- `mapping.local.json`: 실제 선택한 컬럼/타입 설정.
- `local-output\rules.sqlite`: 규칙 DB.
- 이번 점검·적재·조회 보고서와 사용한 `batch_id`.
- 원본 xlsx의 사내 위치와 확인한 문제.

DB 복사/백업은 적재 프로세스 종료 후 수행한다. 실제 회사 DB·보고서·원문 로그를 외부 개발 저장소나 대화에 올리지 않는다.

## 15. 막히면 확인할 순서

| 증상 | 확인/조치 |
| --- | --- |
| Python 없음/Store 설치 안내 | `$SpdmBasePython`에 실제 실행 파일 전체 경로 지정. |
| venv/ensurepip 실패 | 표준 라이브러리·pip·venv를 포함한 정식 설치 확인. |
| pip 접속/인증서 오류 | 사내 패키지 저장소·프록시·인증서 설정 또는 17장 오프라인 경로 확인. 검증을 끄거나 우회하지 않음. |
| `No module named openpyxl` | 설치와 실행을 같은 `$SpdmPython`으로 했는지 확인. |
| 스크립트/테스트 없음 | SQLite ZIP인지, 9개 파일이 함께 있는지 확인. |
| 시트/헤더 불일치 | 실제 시트명·열 위치·헤더와 `mapping.local.json` 대조. |
| SEC 숫자/길이 오류 | 코드 체계·문자열 제공 기준 확인. 선행 0이나 변환 규칙을 추측하지 않음. |
| 수식/Excel 오류 셀 | 선택 열에 확정된 값이 필요한지 입력 담당자와 확인. 프로그램은 Excel 계산을 하지 않음. |
| `database is locked` | 같은 DB에 쓰는 프로그램을 종료하고 재실행. DB는 삭제하지 않음. |
| 타 용도 DB/미지원 버전 | 별도 새 SPDM DB 경로 사용. |
| `rejected` | 이번 보고서 `inspection.issues` 확인·수정·재실행. 일부 정상 행만 저장된 상태가 아님. |
| “DB 적재는 완료됨…보고서 기록 실패” | DB는 이미 저장됐을 수 있음. 콘솔 ID와 출력 폴더 권한 확인 후 재실행. |
| 조회 `NOT_FOUND` | 코드 체계·매핑·batch_id 확인. PASS로 처리하지 않음. |

### DRM 파일 읽기 실패

이 도구는 NASCA 보호 해제/우회를 구현하지 않았다. Python이 설치됐다고 보호 xlsx가 자동으로 읽히는 것은 아니다.

1. 가상 데이터 테스트부터 통과했는지 확인한다.
2. 실제 파일 경로·사용자 권한·DRM 에이전트 상태를 확인한다.
3. 기존 사내 Python 프로그램이 읽을 수 있다면 승인된 실행 파일과 프로세스 접근 조건을 확인한다. 새 가상 환경의 실행 파일도 허용되는지는 별도 확인이 필요하다.
4. 승인된 Python을 사용해야 한다면 `$SpdmPython`을 해당 실행 파일로 바꾸고 그 환경의 openpyxl/SQLite 사용 가능 여부를 확인한다. 패키지 설치도 같은 실행 파일 기준으로 해야 한다.
5. 계속 실패하면 사내 DRM 담당자/입력 생성 담당자에게 허용된 Python 접근 또는 사내 전처리 결과 전달 방식을 확인한다. 데이터를 외부로 옮겨 해결하지 않는다.

## 16. 창을 닫았다가 다시 실행할 때

설치·패키지 설치를 반복하지 않고 변수를 복원한다. 실제 경로를 다르게 사용했다면 수정한다.

```powershell
$SpdmRoot = Join-Path $env:USERPROFILE "SPDMOffline"
$SpdmPython = Join-Path $SpdmRoot "venv\Scripts\python.exe"
$SpdmApp = Join-Path $SpdmRoot "app\spdm_import"
$SpdmOutput = Join-Path $SpdmRoot "local-output"
$SpdmInput = Join-Path $env:USERPROFILE "Downloads\Data\spdm_checkpoint_merged_20261012_160751.xlsx"
$SpdmMapping = Join-Path $SpdmRoot "mapping.local.json"
$SpdmDb = Join-Path $SpdmOutput "rules.sqlite"
$SpdmRunStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SpdmInspectionReport = Join-Path $SpdmOutput "inspection_$SpdmRunStamp.json"
$SpdmImportReport = Join-Path $SpdmOutput "import_$SpdmRunStamp.json"
$SpdmQueryReport = Join-Path $SpdmOutput "query_$SpdmRunStamp.json"
Set-Location $SpdmApp
```

8장부터 재실행하면 된다. 과거 가져오기만 조회하려면 실제 ID/SEC를 지정하고 11장의 조회 명령을 실행한다. 그 경우 11장의 미리보기 기반 `$SpdmSecCode` 대입은 실행하지 않는다.

```powershell
$SpdmBatchId = 1                 # 실제 저장한 ID로 변경
$SpdmSecCode = "03438806"        # 실제 확인한 코드로 변경
```

## 17. 패키지 저장소가 막혔을 때의 오프라인 설치 대안

인터넷이 있어도 PyPI 접속이나 패키지 다운로드가 금지될 수 있다. 그때는 사내 배포/반입 경로에서 실제 wheel 두 개를 준비한다.

```text
SPDMOffline\wheels\
├── openpyxl-3.1.5-py2.py3-none-any.whl
└── et_xmlfile-2.0.0-py3-none-any.whl
```

5장의 온라인 설치 대신 다음 명령을 사용한다.

```powershell
& $SpdmPython -m pip --isolated --disable-pip-version-check install `
  --no-index `
  --find-links (Join-Path $SpdmRoot "wheels") `
  --only-binary=:all: `
  "openpyxl==3.1.5" "et-xmlfile==2.0.0"

if ($LASTEXITCODE -ne 0) {
    throw "wheel 파일과 버전을 확인하세요. requirements.txt만으로 오프라인 설치할 수는 없습니다."
}
```

`--no-index`로 외부 패키지 인덱스를 사용하지 않고 로컬 wheel에서만 설치한다. Python 다운로드도 막혔다면 승인된 정식 오프라인 설치 프로그램을 먼저 확보한다. 코드 ZIP에는 설치 프로그램과 wheel이 없다.

## 18. 내일 완료 기준과 검증 한계

1. Python·패키지 설치와 가상 테스트 25개 통과.
2. 실제 사내 규칙 파일 점검 성공과 컬럼 선택 확인.
3. SQLite 적재 성공 및 가져오기별 기록/실제 행 수 일치.
4. 저장된 SEC의 규칙 조회 성공과 동일 입력 재실행 스킵 확인.

DRM 접근이 막히면 1번까지의 결과와 사내에서 확인한 원인을 남기고 접근 확인 후 2번부터 진행한다.

현재 코드는 Linux/Python 3.12.14/openpyxl 3.1.5에서 가상 데이터 25개 테스트와 반입 ZIP의 저장·조회 CLI가 통과했다. 이 문서는 현재 구현·CLI와 대조한 실행 안내이며, Windows 설치·사내 DRM·실제 파일 실행을 직접 검증한 문서는 아니다.
