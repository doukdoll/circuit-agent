# Circuit Review: SQLite 스키마와 실제 데이터 최초 적재

현재 버전은 사용자가 제공한 14개 테이블·2개 트리거 SQL을 기준으로 합니다. Python 3.10 이상, SQLite 3.31 이상과 JSON1을 사용하며 추가 패키지·외부 API·서버가 필요 없습니다. **가상/모의 데이터 생성이나 자동 샘플 적재 기능은 없습니다.**

## 파일

| 파일 | 역할 |
| --- | --- |
| schema_sqlite.sql | 원본·정규화 규칙·후속 회로 검증용 14개 테이블, 인덱스, 트리거 |
| init_db.py | 빈 DB 초기화. 업무 데이터는 0행 |
| import_data.py | 실제 원본 23컬럼 CSV와 대응 분석 JSON의 최초 전체 적재 |
| db_common.py | SQLite 연결·FK·DB 식별·스키마 일치 검사 |
| setup_rules.py | Python 파일 선택 창으로 빈 DB 생성 또는 실제 CSV+JSON 최초 적재 |
| queries_sqlite.sql | SEC별 규칙·파라미터·요구 사실·결과를 조회하는 읽기 전용 SQL |
| test_schema.py | 레코드를 만들지 않는 빈 스키마 검사. 배포 ZIP에는 포함하지 않음 |

## 실행

PowerShell 명령을 입력하지 않으려면 setup_rules.py를 Python으로 실행합니다. 첫 창에서 예를 누르면 CSV와 JSON을 골라 최초 적재하고, 아니오를 누르면 빈 DB만 만듭니다. 기존 데이터가 있는 DB를 갱신하거나 덮어쓰지 않습니다.

```powershell
python init_db.py --db circuit_review.db
python import_data.py --db circuit_review.db --csv checkpoints.csv --analysis analysis.json
```

CSV와 JSON은 사내 실제 파일을 별도로 준비합니다. 입력을 생성하는 명령은 없습니다. 자세한 설치·실행·제약은 [현재 실행 안내](../../docs/CIRCUIT_REVIEW_RUN.md)를 따릅니다.

## 입력 및 저장 정책

- CSV는 UTF-8 또는 UTF-8 BOM이며, 반복되는 adminno/seqno 이름을 포함한 23개 헤더와 순서가 같아야 합니다. 원본 식별자와 날짜 문자열을 보존합니다.
- JSON은 checkpoint_id/row_uid/sec_code/status/analysis를 가진 배열입니다. analysis는 summary/checks/issues를 가지거나 null일 수 있습니다.
- 행 번호는 제공된 importer의 enumerate(reader, start=2)와 같은 **CSV 레코드 순서**입니다. 헤더가 1, 첫 데이터가 2이며 셀 내부 줄바꿈은 새 레코드가 아닙니다. 물리적 텍스트 줄 번호와 다를 수 있습니다.
- row:숫자 또는 row_uid의 마지막 :숫자로 매칭합니다. 둘 다 해석 가능하면 같아야 하며 파일명 접두사는 달라도 됩니다. 양쪽 SEC는 원문 그대로 같아야 합니다.
- 모든 CSV 레코드와 JSON 레코드가 완전히 대응해야 합니다. 공유 부품 필드 불일치·근거 인용 불일치·제약 오류 등은 전체 트랜잭션을 롤백합니다. 부분 적재/증분 동기화/최신 교체는 수행하지 않습니다.
- evidence.quote는 해당 원본 셀 안에 존재하는 비어 있지 않은 문자열이어야 합니다. 일치하지 않는 근거를 고쳐 쓰거나 만들어내지 않습니다.
- archetype 미제공은 other이며 자동 분류하지 않습니다. version_no는 최초 적재의 1입니다. 미래 검증 테이블은 비어 있습니다.
- raw_row_json은 원본 CSV 23개 셀 배열, raw_analysis_json은 **최상위 레코드 전체**를 저장합니다. 분석 객체만이 아니라 원본 checkpoint_id/row_uid/status와 선택 error도 보존하기 위한 처리입니다.
- 파라미터 문자열은 공백까지 보존합니다. 숫자/범위는 유한한 값일 때만 별도 REAL 컬럼으로 파싱하며 구조화된 값은 JSON 텍스트로 보존합니다. 전체 JSON 타입은 raw_analysis_json에서도 확인할 수 있습니다.

## 스키마 및 이전 버전

init_db.py는 DB 식별(application_id)과 별도 schema version=1을 SQLite 헤더에 기록합니다. 이는 이전 JSON 전용 v7의 후속 버전 숫자가 아닌 **다른 DB 형식**입니다. 임의의 기존 DB 또는 바뀐 스키마를 자동 수리/변환하지 않습니다. 같은 형식의 빈 DB 재초기화는 그대로 두며 데이터가 있는 DB는 거부합니다.

SQL은 제공된 INTEGER PRIMARY KEY 정의를 따릅니다. SQLite가 번호를 자동 부여하지만 예전 v7의 AUTOINCREMENT 비재사용 정책은 이번 스키마에 추가하지 않았습니다. 모든 애플리케이션 연결에서 PRAGMA foreign_keys=ON을 설정해야 합니다.

과거 JSON 전용·최신 규칙 교체 코드는 [spdm_legacy_v7](../spdm_legacy_v7)에 보존되어 있습니다. 두 DB는 테이블명 일부가 같아도 호환되지 않습니다.

## 확인 범위

빈 DB 초기화·14개 빈 테이블·두 트리거 정의·FK 설정·DDL 실패 롤백·기존/변조 DB 거부·읽기 전용 SQL·GUI 빈 DB 생성의 10개 검사를 Linux에서 통과했습니다. 레코드나 가상 CSV/JSON을 생성하지 않았습니다. 실제 SPDM CSV가 없어 CSV+JSON 전체 적재와 실제 Windows GUI 클릭은 검증하지 않았습니다.

제공된 트리거는 검증 결과의 run/instance 설계와 부품 소유 규칙을 INSERT/해당 FK UPDATE 시 확인합니다. 관측 사실의 required_fact/파일 소유 관계 및 참조 부모 변경까지 모두 보호하는 스키마는 아닙니다. 후속 검증 애플리케이션에서 이를 확인해야 합니다.
