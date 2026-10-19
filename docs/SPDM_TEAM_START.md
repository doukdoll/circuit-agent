# SPDM JSON 규칙 DB — 팀원 설치·실행 안내

> 이전 JSON 전용 v7의 보존 문서입니다. 현재 배포는 [CSV+JSON/14테이블 안내](CIRCUIT_REVIEW_RUN.md)를 따릅니다.

작성일: 2026-10-16 / 배포: spdm-team-v7.zip / DB 스키마: 7

갱신: 2026-10-19 — Python 파일 선택 실행기 setup_rules.py 추가. 최신 ZIP에는 SPDM_PYTHON_START.md도 포함됩니다.

이 도구는 전처리된 JSON을 검사하고 로컬 SQLite DB에 저장한 뒤 SEC 코드로 조회합니다. 회로 검증 담당자는 조회 결과를 QCV/BOM 검증 단계의 규칙 입력으로 사용할 수 있습니다. 회로 사실 추출과 Gemini PASS/FAIL 판정은 이 배포에 포함되지 않습니다.

## 1. 전달할 파일과 준비물

- **spdm-team-v7.zip**: 코드·계약·테스트·스키마·이 설명서가 들어 있습니다.
- **원본 규칙 JSON**: 담당자가 사내에서 별도로 전달합니다. ZIP에는 실제 JSON·DB·보고서가 없습니다.
- **Windows와 Python 3**: Python 3.12를 권장합니다. 이미 Python이 있으면 우선 아래 명령으로 실행 환경을 점검합니다.

Python이 없다면 사내 승인 경로에서 준비하거나 [Python 공식 Windows 다운로드](https://www.python.org/downloads/windows/)에서 설치합니다. 테스트한 3.12 계열 설치 프로그램의 예시는 [Python 3.12.10](https://www.python.org/downloads/release/python-31210/)입니다. PC에 맞는 설치 프로그램을 사용합니다.

**ZIP은 압축 해제해서 쓰는 Python 소스 배포본이며 Python 설치 프로그램은 포함하지 않습니다.** SQLite는 Python의 sqlite3 모듈에 포함되어 별도 설치가 필요 없습니다. pip·openpyxl·DB 서버·Git·Gemini·외부 API가 필요하지 않으며 설치 후 실행에는 인터넷이 필요 없습니다. PowerShell 실행 정책 변경과 가상환경 활성화도 필요 없습니다.

### 명령 입력 없이 실행하기

탐색기에서 ZIP을 모두 압축 풀기 한 뒤 app → spdm_json → setup_rules.py를 Python으로 실행합니다. JSON 선택 → DB 저장 위치 선택 → 검사·적재 → 완료 창 순서입니다. 기존 DB를 선택하면 전체 교체 여부를 확인합니다. 자세한 방법은 ZIP의 SPDM_PYTHON_START.md 또는 저장소의 [Python 실행 안내](SPDM_PYTHON_START.md)를 따릅니다. 이 방식은 아래 PowerShell 경로 변수 설정을 생략할 수 있습니다. 더블클릭이 편집기로 연결되면 IDLE에서 열고 F5로 실행할 수도 있습니다.

## 2. 새 폴더에 압축 해제

Windows PowerShell 5.1 또는 PowerShell 7에서 실행합니다. ZIP의 전체 경로를 입력할 때 파일을 PowerShell로 끌어다 놓거나 탐색기의 '경로로 복사'를 이용할 수 있습니다.

```powershell
$SpdmZip = (Read-Host "spdm-team-v7.zip 전체 경로 입력").Trim('"')
$SpdmRoot = Join-Path $env:USERPROFILE "SpdmJson-Team-v7"

if (-not (Test-Path -LiteralPath $SpdmZip -PathType Leaf)) {
    throw "ZIP 경로를 확인하세요."
}
if (Test-Path -LiteralPath $SpdmRoot) {
    throw "대상 폴더가 이미 있습니다. 기존 설치는 보존하고 SpdmRoot를 새 폴더명으로 바꾸세요."
}

Expand-Archive -LiteralPath $SpdmZip -DestinationPath $SpdmRoot -ErrorAction Stop

$SpdmApp = Join-Path $SpdmRoot "app\spdm_json"
$SpdmOutput = Join-Path $SpdmRoot "local-output"
New-Item -ItemType Directory -Path $SpdmOutput -Force | Out-Null
Set-Location -LiteralPath $SpdmApp
Get-ChildItem
```

압축 해제는 한 번만 합니다. 이미 설치한 폴더에는 위 블록을 반복하지 않습니다.

### 탐색기로 이미 압축을 풀었거나 경로를 찾을 수 없는 경우

탐색기에서 압축 해제한 실제 폴더를 열고 app → spdm_json으로 들어갑니다. import_rules.py가 보이는 폴더에서 주소창을 클릭하거나 Ctrl+L을 누르고 전체 경로를 복사합니다. ZIP 안을 탐색하는 화면이 아닌 압축 해제한 디스크 폴더여야 합니다. 폴더 이름이 spdm-team-v7 등으로 다르면 위 기본 경로와 일치하지 않을 수 있습니다. Join-Path는 경로 문자열만 만들며 압축을 풀거나 코드 파일을 설치하지 않습니다.

다음 명령 자체는 바꾸지 말고, 안내문이 뜬 다음 복사한 폴더 경로를 붙여넣고 Enter를 누릅니다.

```powershell
$SpdmApp = (Read-Host "import_rules.py가 보이는 실제 폴더 전체 경로 입력").Trim('"')
if (-not [string]::IsNullOrWhiteSpace($SpdmApp) -and
    (Test-Path -LiteralPath (Join-Path $SpdmApp "import_rules.py") -PathType Leaf)) {
    $SpdmApp = (Resolve-Path -LiteralPath $SpdmApp).Path
    $SpdmRoot = Split-Path -Parent (Split-Path -Parent $SpdmApp)
    $SpdmOutput = Join-Path $SpdmRoot "local-output"
    New-Item -ItemType Directory -Path $SpdmOutput -Force | Out-Null
    Set-Location -LiteralPath $SpdmApp
    Get-ChildItem
} else {
    throw "압축 해제한 실제 코드 폴더를 입력하세요."
}
```

이 방법으로 이동했다면 아래 3장부터 진행합니다. 이후 9장의 창 재시작에서도 SpdmRoot는 본인이 실제로 압축 해제한 위치로 지정하거나 위 방법으로 복원합니다.

```text
SpdmJson-Team-v7\
├── 설치_실행_안내.md
├── SPDM_PYTHON_START.md
├── VERSION.txt
├── SHA256SUMS.txt
├── app\spdm_json\
│   ├── sqlite_store.py
│   ├── setup_rules.py
│   ├── json_rules.py
│   ├── analysis.schema.json
│   ├── inspect_json_rules.py
│   ├── import_rules.py
│   ├── query_rules.py
│   ├── test_json_rules.py
│   ├── verify_environment.py
│   └── schema_v7.sql
└── local-output\                 ← 실행하면서 생성
```

schema_v7.sql은 참고용이며 직접 실행할 필요가 없습니다. import_rules.py가 테이블을 만듭니다. SHA256SUMS.txt는 전달된 파일들의 무결성 확인용이며 실행에 사용되는 입력 파일은 아닙니다.

## 3. 내 PC의 Python과 원본 JSON 지정

**다른 사람의 Python 경로를 그대로 쓰지 않습니다.** 설치된 Python 경로를 모르면 다음 명령을 먼저 참고합니다. py 명령이 없으면 탐색기나 Python 설치 위치에서 python.exe를 찾습니다.

```powershell
py -0p
```

목록에 나온 실제 python.exe 전체 경로와 사내 원본 JSON 전체 경로를 각각 입력합니다. 원본 JSON은 다른 폴더에 두어도 되며 이름을 바꿀 필요가 없습니다.

**Read-Host 뒤의 따옴표 안 문구는 경로가 아니라 안내문입니다. 아래 명령을 그대로 실행한 뒤 안내문과 콜론(:)이 나오면 그때 실제 경로를 붙여넣고 Enter를 누릅니다. 안내문 자리에 경로를 적고 Enter만 누르면 변수는 빈 값이 됩니다.** 경로를 명령에 직접 적으려면 Read-Host 없이 `$SpdmPython = "실제 python.exe 전체 경로"`, `$SpdmInput = "실제 JSON 전체 경로"`처럼 대입합니다. 이 예시의 설명 문구를 실제 경로로 바꿉니다.

```powershell
$SpdmPython = (Read-Host "사용할 python.exe 전체 경로 입력").Trim('"')
$SpdmInput = (Read-Host "원본 규칙 JSON 전체 경로 입력").Trim('"')

if ([string]::IsNullOrWhiteSpace($SpdmPython) -or
    -not (Test-Path -LiteralPath $SpdmPython -PathType Leaf)) {
    throw "Python 실행 파일 경로를 확인하세요."
}
if ([string]::IsNullOrWhiteSpace($SpdmInput) -or
    -not (Test-Path -LiteralPath $SpdmInput -PathType Leaf)) {
    throw "원본 JSON 경로를 확인하세요."
}

& $SpdmPython -S -c "import sys, sqlite3; print('Python:', sys.version); print('SQLite:', sqlite3.sqlite_version)"
if ($LASTEXITCODE -ne 0) { throw "Python 또는 sqlite3 실행을 확인하세요." }
```

이후 명령의 $SpdmPython과 $SpdmInput은 방금 입력한 값을 사용합니다. -S는 외부 설치 패키지를 로드하지 않는 실행 옵션입니다.

## 4. 실제 Windows 환경과 JSON 전체 흐름 점검

```powershell
& $SpdmPython -S .\verify_environment.py `
    --expect-windows --input $SpdmInput `
    --report (Join-Path $SpdmOutput "environment.json")

if ($LASTEXITCODE -ne 0) {
    throw "점검 실패. local-output\environment.json의 error와 failed_step을 확인하세요."
}

$SpdmEnvironment = Get-Content -LiteralPath (Join-Path $SpdmOutput "environment.json") -Raw -Encoding UTF8 |
    ConvertFrom-Json
$SpdmEnvironment | Format-List status, system, python, sqlite, windows_verified
```

기대 결과는 status=passed, system=Windows, windows_verified=true입니다. 최신 배포본의 가상 테스트 34개(이전 배포본 25개)와 원본 JSON 검사·임시 DB 저장·모든 SEC 조회·원문/타입 보존·반복/교체·실패 시 보호를 확인합니다. 원본을 수정하지 않으며 이 단계의 DB는 임시 파일입니다. 사용할 DB는 다음 단계에서 생성합니다.

사내 JSON이 아직 없으면 3장에서 SpdmInput 지정/존재 확인을 생략하고 위 명령의 --input $SpdmInput을 빼면 됩니다. 가상 데이터만 점검되며, 실제 파일을 받은 뒤 3장의 입력 경로 설정부터 진행합니다. 실제 규칙 DB의 적재에는 원본 JSON이 필요합니다.

## 5. JSON 점검 후 사용할 DB에 적재

새 설치는 아직 존재하지 않는 DB 파일을 만듭니다. 아래 블록은 새 파일 생성 전용입니다. 이미 만들어진 DB는 보존하고 8장의 갱신 방법을 사용합니다.

```powershell
$SpdmDb = Join-Path $SpdmOutput "rules-v7.sqlite"
$SpdmStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$SpdmInspectionReport = Join-Path $SpdmOutput "inspection_$SpdmStamp.json"
$SpdmImportReport = Join-Path $SpdmOutput "import_$SpdmStamp.json"

if (Test-Path -LiteralPath $SpdmDb) {
    throw "DB가 이미 있습니다. 갱신은 8장을 따르거나 새 파일명을 지정하세요."
}

& $SpdmPython -S .\inspect_json_rules.py $SpdmInput `
    --report $SpdmInspectionReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "JSON 구조 오류. inspection 보고서의 issues를 확인하세요." }

& $SpdmPython -S .\import_rules.py $SpdmInput `
    --db $SpdmDb --report $SpdmImportReport --preview 3
if ($LASTEXITCODE -ne 0) { throw "적재 실패. 콘솔과 import 보고서를 확인하세요." }

$SpdmImport = Get-Content -LiteralPath $SpdmImportReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmImport | Format-List status, stored_checkpoints, stored_rows
```

첫 적재의 status는 imported입니다. 건수는 전달받은 JSON에 따라 달라집니다. 이전에 확인한 입력과 동일한 경우 stored_checkpoints=1000, stored_rows=2572이며 두 업무 테이블의 합계는 3572행입니다. 이 건수를 프로그램의 고정 조건으로 사용하지 않습니다.

오류 0이면 적재할 수 있습니다. 경고는 전처리 이슈·미제공 적용 범위 등 검토할 정보를 뜻하며 회로 FAIL 수가 아닙니다. summary는 보완된 체크포인트, specification은 검사 기준, required_design_facts는 추후 수집할 설계 사실 항목이며 실제 측정값이 아닙니다.

## 6. 저장된 스키마와 행 수 확인

```powershell
@'
import sqlite3
import sys
from pathlib import Path

uri = Path(sys.argv[1]).resolve().as_uri() + "?mode=ro"
with sqlite3.connect(uri, uri=True) as con:
    version = con.execute("PRAGMA user_version").fetchone()[0]
    print("schema_version:", version)
    assert version == 7
    for table in ("checkpoints", "rules"):
        ddl = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        automatic = "AUTOINCREMENT" in ddl.upper()
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(table, "AUTOINCREMENT:", automatic, "rows:", count)
        assert automatic
    assert not con.execute("PRAGMA foreign_key_check").fetchall()
'@ | & $SpdmPython -S - $SpdmDb

if ($LASTEXITCODE -ne 0) { throw "DB 스키마 또는 연결 확인 실패." }
```

schema_version:7, checkpoints/rules의 AUTOINCREMENT:True가 정상입니다. SQLite 내부 sqlite_sequence는 번호 관리용이며 규칙 이력을 저장하지 않습니다. GUI가 필요하면 사내 승인된 DB Browser for SQLite 등으로 $SpdmDb 파일을 열 수 있습니다. GUI는 선택 사항입니다.

## 7. SEC 코드로 규칙 조회

실제로 저장된 SEC를 import 보고서에서 하나 골라 조회합니다. SEC 형식은 자동 변환하지 않으므로 BOM 코드와 원문의 선행 0·하이픈·대소문자·공백까지 일치해야 합니다.

```powershell
$SpdmSecCode = [string]$SpdmImport.inspection.preview[0].selected.sec_code
$SpdmQueryReport = Join-Path $SpdmOutput ("query_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff") + ".json")

& $SpdmPython -S .\query_rules.py $SpdmDb `
    --sec-code $SpdmSecCode --output $SpdmQueryReport

$SpdmQueryExit = $LASTEXITCODE
if ($SpdmQueryExit -eq 2) { throw "조회 오류. DB·SEC·출력 경로를 확인하세요." }

$SpdmQuery = Get-Content -LiteralPath $SpdmQueryReport -Raw -Encoding UTF8 | ConvertFrom-Json
$SpdmQuery | Format-List sec_code, match_status
"체크포인트 수: $(@($SpdmQuery.checkpoints).Count)"
"세부 규칙 수: $(@($SpdmQuery.rules).Count)"
```

MATCHED는 규칙을 찾았다는 의미이며 회로 PASS를 뜻하지 않습니다. NO_CHECKS는 부모 체크포인트만 있고 세부 규칙이 없는 경우, NOT_FOUND는 SEC가 없는 경우입니다. 두 경우 종료 코드는 3이며 조회 오류 2와 구분합니다. 임의 SEC를 확인하려면 SpdmSecCode에 실제 코드를 문자열로 지정합니다.

## 8. 새 JSON을 받았을 때

SpdmInput을 새 원본 경로로 지정하고 5장의 inspect 명령을 먼저 실행합니다. 보고서 경로는 새 SpdmStamp로 갱신합니다. 검사 성공 후 **같은 v7 DB**에 import_rules.py를 실행하면 status=replaced가 나옵니다. 최신 입력 전체로 교체하므로 기존 DB에만 있던 규칙/SEC는 제거됩니다. 변경분만 담긴 일부 JSON을 넣으면 기존의 나머지 규칙을 유지하는 방식이 아닙니다.

업무 테이블에는 최신 데이터만 남으며 가져오기 이력을 누적하지 않습니다. 같은 DB의 AUTOINCREMENT ID는 커밋된 이전 번호를 재사용하지 않지만 동일 규칙의 ID를 고정하지는 않습니다. 외부 시스템의 영구 식별자로 DB id만 저장하지 않습니다. 새 DB 파일에서는 번호가 처음부터 시작합니다.

이전 v6 등 지원하지 않는 DB는 자동 변환하지 않습니다. 기존 파일을 보존하고 아직 없는 새 v7 DB 경로에 원본 JSON을 적재합니다. 파일 교체만으로 이미 만들어진 테이블 정의가 바뀌지 않습니다.

## 9. PowerShell을 닫았다가 다시 사용할 때

압축을 다시 풀지 않고 아래처럼 변수를 복원합니다. Python·JSON 경로는 본인의 실제 경로를 지정합니다. 조회만 한다면 SpdmInput은 필요 없습니다.

```powershell
$SpdmRoot = Join-Path $env:USERPROFILE "SpdmJson-Team-v7"
$SpdmApp = Join-Path $SpdmRoot "app\spdm_json"
$SpdmOutput = Join-Path $SpdmRoot "local-output"
$SpdmDb = Join-Path $SpdmOutput "rules-v7.sqlite"
$SpdmPython = (Read-Host "사용할 python.exe 전체 경로 입력").Trim('"')
Set-Location -LiteralPath $SpdmApp
```

7장의 첫 줄 대신 다음처럼 실제 SEC를 입력한 뒤 조회 명령부터 실행합니다. SpdmImport는 새 PowerShell 창에 자동 복원되지 않습니다.

```powershell
$SpdmSecCode = Read-Host "조회할 SEC 코드 입력"
```

## 10. 오류가 났을 때 확인할 것

| 증상 | 확인·조치 |
| --- | --- |
| Python 경로를 찾을 수 없음 | 다른 사용자의 경로를 복사하지 말고 3장에서 실제 python.exe 지정 |
| LiteralPath가 빈 문자열 / & 뒤 식이 잘못된 개체 | Read-Host 안내문에 경로를 적은 뒤 빈 응답을 제출했는지 확인. 3장의 입력 방식 또는 직접 변수 대입으로 복원 |
| 폴더 또는 변수가 없음 | 2장 설치 위치 확인, 창을 다시 열었다면 9장 변수 복원 |
| inspect 종료 2 / errors가 0보다 큼 | inspection 보고서 issues의 path/reason 확인. JSON 원문을 임의로 삭제하지 않음 |
| 경고가 많지만 오류는 0 | 전처리 검토 정보인지 확인. 경고를 회로 불합격으로 해석하지 않음 |
| 지원하지 않는 DB 버전 | 새 파일명의 v7 DB에 재적재 |
| 버전은 7인데 한쪽 AUTOINCREMENT False | 코드 8개를 같은 배포본으로 맞추고 아직 없는 새 DB 생성. 실제 DB 경로 확인 |
| database is locked | DB를 열어 둔 GUI/다른 작업을 닫고 재시도 |
| SEC 조회 NOT_FOUND | 정확한 SEC·올바른 DB 경로 확인. 하이픈 삭제 등 자동 정규화 없음 |
| 파일 내용을 확인하려고 DB 경로를 입력했더니 PowerShell 명령 오류 | .sqlite는 실행파일이 아님. GUI에서 열거나 query_rules.py 사용 |

팀에 오류를 공유할 때는 환경 버전·실행 단계·종료 코드·해당 path/reason부터 확인합니다. 실제 JSON/DB/원문이 포함된 보고서는 사내에서 관리합니다.

## 11. 검증 근거와 범위

핵심 저장 코드 기준은 구현 3b27940입니다. 기존 [v7 Windows CI](https://github.com/doukdoll/circuit-agent/actions/runs/38857144781)에서 Windows Server 2025/Python 3.12.10/SQLite 3.49.1, Windows PowerShell 5.1.26100.33438과 PowerShell 7.6.6 각각 가상 테스트 25개 및 JSON CLI 환경 검증이 통과했습니다. 2026-10-19에 추가한 Python 실행기와 34개 테스트의 실제 Windows 재실행은 아직 수행하지 않았습니다. 핵심 저장 코드와 스키마는 그대로이며 과거 CI를 새 실행기의 Windows 검증으로 표현하지 않습니다.

이번 ZIP은 별도로 Linux/Python 3.12.14의 외부 패키지 없는 환경에 압축 해제하여 가상 테스트 25개 및 UTF-8 BOM JSON 적재·SEC 조회·이 설명서의 DB 확인 코드를 통과했습니다. 스키마 7, 양쪽 AUTOINCREMENT=True, 외래키를 확인했으며 파일별 해시와 검증한 런타임 코드의 일치도 확인했습니다. 새 Windows 실행 결과는 아니며 각 팀원의 Windows/Python/실제 JSON 조합은 4장의 환경 점검기로 직접 확인합니다. 사내 사용자에게서 v7 재적재 완료 보고를 받았지만 이 보고만으로 모든 팀원의 환경이나 실제 양쪽 DDL을 검증한 것으로 간주하지 않습니다.
