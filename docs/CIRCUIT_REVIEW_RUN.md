# Circuit Review — 14테이블 SQLite 생성·실제 데이터 적재

작성일: 2026-10-19

갱신: 2026-10-20 — LDRC 정보의 체크포인트별 저장, DB 형식 버전 2.

현재 코드는 `tools/spdm_import`입니다. 입력은 **실제 원본 23컬럼 CSV와 그 CSV 전체에 대응하는 분석 JSON**입니다. 빈 DB를 생성할 수 있으며, 실제 파일이 없을 때 데이터는 만들거나 채우지 않습니다. 기존 JSON 전용 v7 방식은 [보존 기록](SPDM_LEGACY_V7.md)에 남겼습니다.

## 1. 준비와 압축 해제

1. Python 3.10 이상이 설치된 Windows PC를 준비합니다. GUI를 쓰려면 Python의 Tcl/Tk 및 IDLE 옵션이 필요합니다.
2. circuit-review-sqlite.zip을 새 폴더에 모두 압축 풀기 합니다.
3. 같은 폴더의 setup_rules.py, init_db.py, import_data.py, db_common.py, schema_sqlite.sql을 함께 둡니다.

실행에 필요한 Python 파일은 네 개입니다. 개발 테스트는 저장소의 tests 폴더에 있고 예전 v7 실행 파일은 Git 이력으로만 보존합니다.

SQLite는 Python에 포함되어 별도 설치하지 않습니다. SQLite 3.31 이상 및 JSON1 지원이 필요하며 프로그램에서 확인합니다. Python 설치 프로그램·실제 CSV/JSON·DB·보고서는 ZIP에 포함하지 않습니다. 설치 후 실행에는 인터넷·추가 패키지·DB 서버·Gemini·외부 API가 필요 없습니다.

## 2. PowerShell 명령 없이 실행

setup_rules.py를 Python으로 실행합니다. 더블클릭이 편집기로 연결되어 있다면 IDLE에서 파일을 열고 F5를 누르거나 VS Code에서 설치된 Python을 선택해 실행합니다.

첫 창에서 목적을 선택합니다.

- **아니오**: 저장 위치를 선택하면 14개 테이블만 있는 빈 DB를 만듭니다. 업무 데이터는 총 0행입니다.
- **예**: 실제 CSV → 대응 JSON → DB 저장 위치 순서로 선택합니다. 빈 스키마를 준비하고 검사·최초 적재를 한 번에 수행합니다.
- **취소**: 종료합니다.

기본 파일명은 circuit_review_v2.db입니다. 기존 데이터가 있는 DB를 선택하면 거부하며 삭제/전체 교체를 하지 않습니다. 같은 형식 버전 2의 빈 DB만 재사용할 수 있습니다. 이전 버전 1 DB는 비어 있어도 새 파일명으로 다시 만듭니다. 완료 창에는 저장 경로와 실제 건수가 표시됩니다. 오류 시 이번 입력 데이터는 전부 롤백되며 새로 만든 DB에는 빈 테이블만 남을 수 있습니다.

## 3. 명령으로 실행하는 경우

압축 해제한 폴더에서 실행합니다. Python 경로는 각 PC의 실제 설치 경로를 사용합니다.

```powershell
python init_db.py --db circuit_review_v2.db
python import_data.py --db circuit_review_v2.db --csv checkpoints.csv --analysis analysis.json
```

첫 명령만 실행하면 빈 DB가 준비됩니다. 두 번째 명령은 실제 CSV와 JSON을 모두 받은 뒤 실행합니다. 성공 종료 코드는 0, 오류는 2입니다. import_data.py는 없는 DB를 자동 생성하지 않으며 init_db.py 실행이 선행되어야 합니다.

이미 적재한 DB를 다시 사용하면 오류로 종료합니다. 수정한 CSV/JSON을 적재하려면 새 DB 파일명으로 초기화한 뒤 해당 파일명을 두 번째 명령에도 지정합니다. 새 DB는 기존 검증 결과를 자동으로 가져오지 않습니다.

## 4. 입력 계약

CSV 헤더는 아래 순서와 철자가 같아야 합니다. 중복 이름이 있으므로 이름만으로 열을 합치지 않습니다.

```text
adminno,seqno,sec_code,writer,comp_date,maker,maker_pn,adminno,seqno,Checkpoint,Specification,설계치,참조문서,input_5,savefolder,ref_date,category,pin_info,ldrc_check_tp,ldrc_regist_tp,ldrc_check_date,ldrc_checker,ldrc_id
```

- CSV 인코딩은 UTF-8 또는 UTF-8 BOM입니다. Excel 파일은 입력이 아닙니다.
- adminno 두 열, 부품 그룹별 공유 값, savefolder와 규칙 seqno의 관계를 검사합니다. SQL의 사번·관리번호 길이 및 허용 값 제한도 적용됩니다.
- 부품 공통 값은 C~G열(SEC/작성자/작성일/제조사/부품번호)입니다. 제조사/부품번호의 공백 빈값은 미제공으로, 수치가 같은 작성일 문자열은 반올림 없는 Decimal로 같은 날짜인지 비교합니다. 비어 있지 않은 SEC·사번·제조사 등의 값은 그대로 비교합니다.
- S~W열 LDRC 정보 5개는 checkpoints에 각 레코드별로 저장합니다. 같은 부품의 규칙마다 달라도 허용하며 부품 공통 값으로 비교하지 않습니다. 선택 항목의 빈 문자열/공백만 있는 값은 SQL NULL로 저장하고, 나머지 문자열은 날짜를 포함해 그대로 보존합니다. 원본 CSV와 raw_row_json도 보존합니다.
- JSON은 최상위 배열이며 checkpoint_id, row_uid, sec_code, status, analysis를 가집니다. analysis가 객체이면 summary/checks/issues를 가져야 합니다.
- analysis:null과 선택 error도 원본 레코드 전체에 보존합니다. 세부 규칙이 없는 분석도 CSV 레코드와 대응해야 합니다.
- CSV **레코드 순서**로 헤더는 1, 데이터는 2부터 셉니다. 셀 안 줄바꿈을 포함한 물리적 텍스트 줄 번호와 혼동하지 않습니다. 제공된 원래 Python importer와 같은 기준입니다.
- checkpoint_id가 row:숫자이거나 row_uid가 :숫자로 끝나야 합니다. 둘 다 해석 가능하면 같아야 합니다. 접두사 파일명은 달라도 됩니다.
- CSV/최상위 JSON/각 check의 SEC가 정확히 같아야 합니다. 하이픈·선행 0·대소문자·공백을 자동 변환하지 않습니다.
- 모든 CSV 행과 모든 JSON 항목이 일대일로 대응해야 합니다. 전체 CSV와 일부 분석 JSON의 조합은 거부합니다.
- evidence의 field는 checkpoint/specification/design_template/reference_document이며 quote가 실제 해당 셀 안에 정확히 있어야 합니다. 빈 인용문도 거부합니다.
- SQL에 정의된 target_kind/level/role/qualifier/issue code 제약과 같은 분석 내 requirement_id 유일성을 지켜야 합니다. 기존 v7보다 제한이 강합니다.

## 5. DB 확인과 조회

사내 승인된 SQLite GUI에서 완료 창에 표시된 DB를 열어 테이블과 내용을 볼 수 있습니다. .db 파일은 실행 프로그램이 아니므로 PowerShell에 경로만 입력해서 실행하지 않습니다.

queries_sqlite.sql에는 읽기 전용 예시가 있습니다. :sec_code, :design_id, :run_id는 사용하는 클라이언트에서 실제 값으로 바인딩합니다. SEC 조회는 parts → checkpoints → checkpoint_analyses → analysis_checks로 연결됩니다. 같은 SEC에 여러 part_id가 있을 수 있으므로 임의로 하나만 선택하지 않습니다.

파라미터/요구 사실/근거/분석 이슈는 각각 별도 테이블입니다. raw_row_json은 CSV 셀 배열, raw_analysis_json은 error 등 최상위 필드를 포함한 JSON 레코드 전체입니다. 요구 사실은 수집할 항목이며 아직 관측값이 아닙니다. 회로 검증용 여섯 테이블은 후속 파서/판정기가 데이터를 넣기 전까지 비어 있습니다.

## 6. 기존 v7 및 갱신 정책

이 버전은 JSON 전용 v7 DB의 자동 업그레이드가 아닙니다. 기존 rules-v7.sqlite는 그대로 보존하고 새 circuit_review_v2.db를 만듭니다. CREATE TABLE IF NOT EXISTS는 마이그레이션이 아닙니다.

현재 Circuit Review 형식은 버전 2입니다. 이전 Circuit Review 버전 1에서 parts에 있던 LDRC 5개 컬럼을 checkpoints로 옮겼습니다. 기존 버전 1 DB는 빈 DB여도 자동 변환하지 않으며 별도 circuit_review_v2.db에 원본 CSV+JSON을 다시 적재합니다.

이번 스키마는 제공된 INTEGER PRIMARY KEY를 따르며 AUTOINCREMENT를 추가하지 않았습니다. 분석 버전 컬럼은 있지만 현재 importer는 최초 version_no=1만 저장합니다. 자동 최신 교체·증분 동기화·규칙 버전 추가 기능은 없습니다.

init_db.py로 DB 식별과 형식 버전을 기록하고 전체 정의를 검사합니다. 같은 이름의 임의 테이블만 있는 DB는 사용하지 않습니다. 다른 프로그램에서도 FK를 적용하려면 연결마다 PRAGMA foreign_keys=ON을 실행합니다.

## 7. 검증 근거와 제한

가상 데이터 없이 빈 스키마 테스트 10개를 Linux에서 통과했습니다. 14개 테이블과 두 트리거 정의, 0행, DB 식별·기존 DB 보호·DDL 롤백·읽기 전용 조회를 확인했습니다. GUI는 빈 DB 생성 흐름의 선택 응답을 대체해 검사했습니다. 실제 Windows 창 클릭과 실제 SPDM CSV+JSON 전체 적재는 아직 검증하지 않았습니다. 실제 CSV가 제공되지 않은 상태에서 성공했다고 기록하지 않습니다.

게시한 구현 37f7b2a의 [Windows CI](https://github.com/doukdoll/circuit-agent/actions/runs/39188935104)는 Windows Server 2025에서 Python 3.10.11/SQLite 3.40.1 및 Python 3.12.10/SQLite 3.49.1을 각각 PowerShell 5.1.26100.33438/7.6.6으로 실행하여 네 조합 모두 통과했습니다. 각 조합의 빈 스키마 테스트 10개와 CLI 초기화를 확인했습니다. 합성 CSV/JSON이나 업무 레코드를 만들지 않았으며 실제 GUI 클릭이나 실제 CSV+JSON 적재 성공을 의미하지 않습니다.

기존 v7의 테스트 34개 및 과거 Windows CI는 보존된 이전 코드의 결과이며 새 14테이블 버전의 검증 결과가 아닙니다. 후속 회로 검증 애플리케이션은 부품 그룹 선택, 사실/파일 소유 관계 및 검증 당시 규칙 버전 보존 정책을 별도로 구현해야 합니다.

2026-10-20의 공통 필드 비교/상세 오류 수정은 Linux에서 총 15개 검사(기존 10개+스칼라 비교 5개)를 통과했습니다. 합성 CSV/JSON이나 업무 레코드를 만들지 않았습니다. 위 Windows CI는 수정 전 버전의 근거이며 새 비교 코드의 실제 Windows 실행이나 원본 CSV 31번 오류 해소를 확인한 결과가 아닙니다.

이후 LDRC를 체크포인트로 이동한 형식 버전 2는 Linux/Python 3.12에서 총 18개 검사를 통과했습니다. LDRC 컬럼 소유 테이블·형식 버전·이전 버전 DB 보호와 실제 importer의 INSERT/UPDATE SQL 컴파일을 확인했습니다. SQL은 EXPLAIN으로 준비만 하므로 업무 레코드를 넣지 않았습니다. 실제 SPDM 전체 CSV+JSON 적재와 이번 수정의 Windows 실행은 미확인입니다.

## 8. CSV 공통 필드 오류가 날 때

최신 import_data.py로 다시 실행하면 `Inconsistent shared fields for part` 아래에 최초/현재 레코드 번호, 다른 컬럼, 두 값이 표시됩니다. 부품 그룹은 왼쪽 adminno+seqno이며 오른쪽 규칙 seqno가 달라지는 것은 정상입니다.

형식 버전 2에서는 S~W열 LDRC의 행별 차이를 허용하고 각 체크포인트에 보존합니다. C~G열의 실제 공통 값 차이, SEC 불일치, 원문 인용 불일치, SQL의 허용 값 제약 등은 계속 전체 적재를 취소합니다. LDRC 컬럼의 Y/N/B 등 기존 허용 값 제약도 유지합니다.

이전 설명의 “실패 후 빈 DB 재사용”은 같은 형식 안에서만 적용됩니다. 이번 버전 1→2 변경은 테이블 구조가 다르므로 버전 1의 빈 DB도 재사용하지 않습니다. 기존 DB나 원본 CSV를 삭제하거나 수정할 필요는 없습니다.

## 9. 이번 수정본으로 교체하고 다시 적재하기

1. 최신 circuit-review-sqlite.zip을 새 폴더에 모두 압축 풉니다. import_data.py 하나만 교체하면 SQL/버전이 맞지 않습니다.
2. 새 폴더의 setup_rules.py를 Python으로 실행하고 첫 창에서 **예**를 선택합니다.
3. 기존과 같은 실제 원본 23컬럼 CSV와 그 전체에 대응하는 분석 JSON을 선택합니다.
4. DB 저장 위치에서 아직 존재하지 않는 **circuit_review_v2.db**를 지정합니다. 같은 이름이 이미 있으면 새 이름을 사용합니다.
5. 완료 창의 실제 건수를 확인하고, SQLite GUI에서 새 DB의 checkpoints 테이블을 엽니다. LDRC 5개 컬럼은 parts가 아닌 이 테이블에 있습니다.

SQLite GUI의 SQL 실행 창에서 버전과 오류 지점의 저장값을 확인할 수 있습니다. 아래는 조회문이며 데이터를 생성하지 않습니다.

```sql
PRAGMA user_version; -- 2
SELECT source_row_no, ldrc_check_tp, ldrc_regist_tp,
       ldrc_check_date_serial, ldrc_checker_emp_no, ldrc_id
FROM checkpoints
WHERE source_row_no IN (30, 31)
ORDER BY source_row_no;
```
