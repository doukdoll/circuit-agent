# 개발 이력 및 포트폴리오 기록

기준일: 2026-10-10, Asia/Seoul. 기능 추가와 트러블슈팅을 이어서 기록하는 문서입니다. 실행 방법은 [개발 가이드](DEVELOPMENT_GUIDE.md), 이후 기록 방식은 [작업 및 기록 규칙](WORKFLOW.md)을 참고합니다.

## 프로젝트 배경과 현재 결과

회로 넷리스트를 읽고 Rule별 근거를 찾아 검사한 뒤, 사람이 검토할 항목까지 시각적 보고서로 제공하는 프로젝트입니다. 회사 자료를 보안 사유로 사용할 수 없어 공개 자료로 개발 가능한 범위를 먼저 정했습니다. 현재 구현은 Java CLI 데모이며 [최신 MVP 요구사항](MVP_REQUIREMENTS.md)의 일부를 검증하는 출발점입니다.

확인된 흐름은 다음과 같습니다.

```text
공개 QCV / 작성한 테스트 회로 + 개발용 Rule JSON
→ 전체 파일 파싱과 연결 참조 해결
→ 명시한 DNI 제외 및 부품·핀·넷 조회
→ 해당 Rule의 모든 적용 인스턴스 열거
→ 관련 회로 조회와 코드 기반 계산
→ PASS / FAIL / NEEDS_REVIEW
→ JSON 결과 + HTML 보고서
```

Java 21, Maven, Jackson, JUnit 5를 사용했습니다. QCV·BOM·Rule의 의미와 애플리케이션 패키지 경계를 논의한 뒤, 먼저 실행 가능한 파서·기본 검사·보고서 흐름을 만들었습니다. 구현과 테스트 작성에는 Codex 개발 지원을 사용했고, 사용자는 범위·아키텍처 방향·협업 절차를 정하고 Windows에서 빌드와 보고서를 확인했습니다. 세부 개인 기여는 이 작업 내역과 실제 작성·검토한 코드를 기준으로 설명합니다.

## 구현한 기능과 설계 근거

| 기능 | 구현 내용 | 선택한 이유 / 한계 |
| --- | --- | --- |
| 입력 파서 | NET, COMP, Property, Explicit Pin 문법 지원 | 확인한 공개 QCV 문법부터 지원하고, 미지원 줄은 오류로 기록 |
| 연결 참조 해결 | 파일 전체를 읽은 뒤 부품·핀·넷 참조 대조 | NET이 COMP보다 먼저 나오는 파일에서도 누락 없이 참조 해결 |
| 근거 보존 | 원문 파일·줄·부품 블록·속성 위치 기록 | 결과에서 입력 근거를 다시 확인할 수 있도록 추적 정보 보존 |
| DNI 처리 | 실행 시 지정한 속성·값만 제외 | 회사의 표시 관례를 임의로 정하지 않고 원본과 제외 기록 보존 |
| 구조적 조회 | 같은 넷의 연결 부품, 두 넷 사이 부품 조회 | 회로 연결은 부품·핀·넷 구조로 확인; 현재 벡터 검색은 미구현 |
| 대상 열거 | 모델이 일치하는 모든 인스턴스를 검사 전에 수집 | 일부 검색 결과를 전체 검사로 오해하는 것을 방지 |
| 기본 Rule | TPS56C230 명목 FB 분압식 계산 | BigDecimal 계산을 사용하여 수치 결과를 재현 |
| 보류 판정 | 값 누락·단위 오류·추가 분기·미지원 Rule 등을 NEEDS_REVIEW로 처리 | 정보가 부족한 상태를 자동 PASS로 처리하지 않음 |
| 결과 출력 | audit.json 및 독립 report.html 생성 | CLI 결과를 코드와 사람이 각각 확인할 수 있도록 제공 |
| 실행 식별 | 입력 SHA-256, Rule 버전, 실행 시각 기록 | 어떤 입력과 기준으로 계산했는지 구분 |

전체 입력 바이트를 한 번 읽어 파싱과 SHA-256 계산에 함께 사용합니다. 입력 식별용 해시는 결과 추적을 위한 메타데이터이며, 아래 공개 원본 무결성 테스트와 역할이 다릅니다.

패키지는 `file.netlist`, `circuit`, `rule`, `audit`, `result`로 나눴습니다. 입력 형식 처리, 공통 회로 모델, 판정 로직, 실행 집계, 보고서 책임을 분리하여 후속 API에서 `AuditExecutor`를 호출할 수 있도록 구성했습니다. 상세 구조는 [개발 가이드](DEVELOPMENT_GUIDE.md#패키지와-호출-흐름)에 있습니다.

## 샘플과 정답 근거

| 자료 | 사용 방식 | 근거 |
| --- | --- | --- |
| Ansys PyAEDT Schematic1.qcv | 원본 그대로 보존하여 파싱 기대 결과와 비교 | [고정 커밋·원본 해시·MIT 라이선스](../samples/qcv/ansys-pyaedt/provenance.json) |
| TI TPS56C230EVM 사용자 가이드 | FB 분압 부분만 직접 작성한 테스트 회로로 표현 | [참고 페이지·사실·개발 선택](../samples/ti/tps56c230/provenance.json) |
| expected.json | 코드 실행과 별도로 기록한 기대 결과 | [파서 기대 결과](../samples/qcv/ansys-pyaedt/expected.json), [검사 사례](../samples/ti/tps56c230/expected.json) |

공개 QCV는 부품 11개·넷 6개·핀 연결 16개를 제공합니다. 연결 정보가 없는 V1007·V1008·V2005는 경고로 남깁니다. TI 참고 회로는 U1의 FB·AGND와 R4·R6만 표현한 축약 모델이며 공식 EDA 내보내기 파일이 아닙니다.

R4와 R6이 각각 10kΩ, 기준 전압이 0.6V이면 `V_OUT = 0.6 × (1 + R4/R6) = 1.2V`입니다. 판정에 사용한 ±3%는 개발용 허용 기준입니다. 부품 목록에 있는 저항 공차 1%와 다른 개념이며 TI 규격이나 회사의 승인 기준으로 주장하지 않습니다.

## 검증 결과

### 자동 검증

초기 구현은 테스트 33개가 통과했고, LF·CRLF 회귀 사례를 추가한 뒤 38개가 통과했습니다.

| 테스트 클래스 | 최신 개수 | 검증 범위 |
| --- | ---: | --- |
| AuditDemoTest | 8 | CLI 결과·종료 코드·파일 출력·HTML 이스케이프·입력 오류 |
| PublicQcvTest | 3 | 원본·라이선스 해시, LF·CRLF의 전체 파싱 기대 결과 |
| QcvValidationTest | 9 | 연결 충돌·참조 누락·지원하지 않는 입력·명시적 DNI |
| RuleEvaluationTest | 18 | 여섯 시나리오·값 오류·허용 오차 경계·전체 대상 열거 |
| 합계 | 38 | 모두 통과한 개발 환경 결과 |

관리 환경은 Linux의 Java 21·Maven 3.9.9를 사용했습니다. 해당 런타임에 `ct.sym`이 없어 환경 한정 컴파일 옵션을 사용한 사실은 [개발 가이드](DEVELOPMENT_GUIDE.md#검증과-후속-작업)에 남겼습니다. `core.autocrlf=true` 체크아웃과 작성한 QCV의 CRLF 변환을 별도 작업 사본에서 확인한 뒤 테스트·패키징이 통과했습니다. 이 회귀 검증을 Windows 운영체제에서 실행한 것으로 표현하지 않습니다.

실행 JAR에서도 다음 여섯 사례와 공개 원본 파싱을 확인했습니다.

| 사례 | 결과 | 수치 / 처리 |
| --- | --- | --- |
| 정상 | PASS | 1.2V, 명목 오차 0% |
| 상단 저항 12kΩ | FAIL | 1.32V, 오차 10% |
| 저항값 누락 | NEEDS_REVIEW | 필요한 값 확인 요청 |
| 추가 병렬 저항 | NEEDS_REVIEW | 기본 모델에서 연결 모호성 처리 |
| DNI 필드·값 명시 | PASS | R99 제외 1개, 1.2V |
| DNI 미지정 | NEEDS_REVIEW | R99 유지, 제외 0개 |

### 사용자 Windows 환경 확인

사용자가 제공한 Windows PowerShell 로그에서 초기 테스트 실패 5개, 코드 수정 후 실패 1개를 확인했습니다. 공개 원본 두 파일을 LF·UTF-8 BOM 없이 저장한 뒤 사용자는 빌드가 정상 동작한다고 확인했습니다. 이어 정상·위반·값 누락 검사와 HTML 보고서를 실행하고 모두 정상 동작한다고 확인했습니다. 최종 성공의 근거는 사용자 확인이며, 성공 시의 전체 테스트 요약 로그와 보고서 화면은 별도로 수집하지 않았습니다.

## 트러블슈팅 기록

### TS-001: Java·Maven 명령을 찾을 수 없음

- **환경·증상:** Windows PowerShell에서 `java`, `mvn`이 명령으로 인식되지 않음.
- **진단:** 설치 여부 또는 PATH 등록 상태를 확인해야 하는 실행 환경 문제. 최초 로그만으로 둘 중 하나를 확정하지 않음.
- **대응:** JDK 21과 Maven 3.9.9 설치 안내, 새 터미널에서 버전 확인. 이후 Maven 빌드 로그가 출력되어 명령 실행이 가능해진 것을 확인.
- **배운 점:** 실행 안내에는 요구 버전과 설치·PATH 확인을 먼저 포함해야 함.

### TS-002: Maven 실행 디렉토리에 POM이 없음

- **환경·증상:** `C:\circuit-agent`에서 `mvn clean package` 실행 시 `MissingProjectException`, 이어 JAR·보고서 파일도 없음.
- **진단:** 해당 경로에 `pom.xml`이 없어 Maven 프로젝트를 찾지 못함. 폴더 위치·현재 브랜치·최신 코드 수신 여부를 확인하도록 안내했으며, 실제 어떤 조건이 원인이었는지는 로그로 확정하지 않음.
- **대응:** `git status`, main 브랜치·최신 코드 확인, `Test-Path .\pom.xml` 안내. 다음 로그에서 `pom.xml`을 읽고 Java 컴파일·테스트가 시작됨.
- **배운 점:** 빌드 실패가 선행하면 JAR·보고서 생성도 진행되지 않으므로 `BUILD SUCCESS` 확인 후 실행해야 함.

### TS-003: Windows 줄바꿈으로 테스트 실패

**증상과 재현**

처음에는 `PublicQcvTest.originalAndLicenseMatchPinnedSourceHashes` 1개와 `RuleEvaluationTest.unsafeLowerValueRequiresReview` 4개가 실패했습니다. 실패한 실제 원본 해시는 다음과 같았습니다.

```text
LF 원본 SHA-256:
4a2bd1ce78828fbc97fea82f79bacd5301a72d102425d5c2eb043ba0fd7e3ca7

CRLF 사본 SHA-256:
2aa5b607e442c588fa23e5a5c06f79cab948534e6a168f85fbbc518b2c15ef43
```

공개 원본의 LF를 CRLF로 바꿔 계산한 해시가 사용자 로그와 정확히 일치했습니다. 또한 하단 저항값을 바꾸는 테스트가 `\n`으로 이어진 문자열을 찾고 있어 CRLF 사본에서는 치환되지 않았습니다. 파서의 LF·CRLF 해석과 별개로 원본 바이트 검사·테스트 준비 코드에서 문제가 발생한 것입니다.

**해시 검사의 목적과 위치**

[PublicQcvTest.java](../src/test/java/com/ssafy/circuitaudit/PublicQcvTest.java)의 `originalAndLicenseMatchPinnedSourceHashes()`는 공개 QCV와 라이선스의 SHA-256을 [provenance.json](../samples/qcv/ansys-pyaedt/provenance.json)의 고정값과 비교합니다. 파일이 내려받은 원본 그대로 보존됐는지 확인하려고 추가한 개발용 JUnit 검사입니다. `mvn clean package`의 테스트 단계에서 실행되며, 고정 해시 비교는 앱의 회로 판정 조건이 아닙니다.

**수정 및 실제 해결 순서**

1. [.gitattributes](../.gitattributes)에 일반 텍스트 LF 유지와 공개 원본·라이선스의 `-text` 설정을 추가했습니다. 공개 원본은 Git의 줄바꿈 변환 대상에서 제외했습니다.
2. 테스트 준비 코드가 선택한 줄바꿈을 사용하도록 바꾸고, LF·CRLF 모두의 파싱·잘못된 저항값 사례를 추가했습니다. 테스트 수가 33개에서 38개로 증가했습니다.
3. 사용자 Windows 로그에서는 문자열 치환 관련 실패가 사라지고 공개 원본 해시 검사 1개만 남았습니다. 기존 CRLF 작업 사본은 설정 추가만으로 바뀌지 않았습니다.
4. `git -c core.autocrlf=false restore ...`를 안내했으나 사용자 로그에서는 실행 후에도 같은 CRLF 해시가 남았습니다. 복원이 반영되지 않은 세부 원인은 해당 로그만으로 확정하지 않았습니다.
5. 공개 QCV와 라이선스의 CRLF를 LF로 직접 바꾸고, UTF-8 BOM 없이 저장하도록 안내했습니다. LF 변환 후 원본 해시와 일치하는 것을 개발 환경에서 확인했고, 사용자는 해당 PowerShell 명령 이후 빌드가 정상 동작한다고 확인했습니다.
6. 사용자가 정상·위반·값 누락 사례와 HTML 보고서까지 확인했습니다. 최종 실행 명령은 [개발 가이드의 Windows 해결 절차](DEVELOPMENT_GUIDE.md#windows에서-줄바꿈-때문에-테스트가-실패할-때)에 있습니다.

**재발 방지와 배운 점**

원본 바이트 보존과 파서의 줄바꿈 지원은 각각 검증해야 합니다. `.gitattributes`는 이후 체크아웃 정책을 정하지만 기존 파일을 자동으로 다시 저장하지 않습니다. 해시 검사의 기대값을 CRLF 값으로 바꾸거나 테스트를 건너뛰는 방식 대신, 원본 바이트를 복구하고 플랫폼 차이를 회귀 테스트에 포함했습니다. 이후 안내는 사용자에게 실제로 성공한 직접 LF 저장 절차를 기준으로 갱신했습니다.

## 작업 이력과 협업 절차

| 날짜 | 변경 | 추적 근거 |
| --- | --- | --- |
| 2026-10-07 | 문서 정리·최초 기획 자료 보존 | [6c89baf](https://github.com/doukdoll/circuit-agent/commit/6c89baf), [ec89593](https://github.com/doukdoll/circuit-agent/commit/ec89593) |
| 2026-10-09 | 최신 MVP 범위·미확정 사항 기록 | [e768416](https://github.com/doukdoll/circuit-agent/commit/e768416) |
| 2026-10-10 | 공개 샘플·Java CLI·기본 검사·보고서 구현 | [cb01cf5](https://github.com/doukdoll/circuit-agent/commit/cb01cf5) |
| 2026-10-10 | Git 줄바꿈 정책·LF/CRLF 회귀 테스트 추가 | [a56c465](https://github.com/doukdoll/circuit-agent/commit/a56c465) |
| 2026-10-10 | 사용자 Windows 환경에서 공개 원본 LF 복구, 빌드·세 보고서 정상 동작 확인 | 이 개발 대화의 사용자 확인 |
| 2026-10-10 | 개발 기록·포트폴리오 활용 근거·향후 문서 규칙 정리 | 이 문서를 포함하는 작업 브랜치 및 PR |

초기 코드와 줄바꿈 수정은 main에 직접 반영됐습니다. 사용자가 작업 브랜치와 PR 절차를 요청했으며, 이 문서 작업부터 **작업 브랜치 → 검증 → 승인된 커밋·푸시 → PR → 별도 승인 후 병합**을 적용합니다. 기존 이력을 PR로 진행했던 것처럼 소급하여 표현하지 않습니다.

## 포트폴리오에 활용할 핵심 내용

현재 결과를 설명하는 예시 문장은 다음과 같습니다. 개인 역할은 위 기여 내역에 맞춰 함께 설명합니다.

> 회사 원본 자료를 사용할 수 없는 조건에서 공개 QCV와 평가보드 자료를 활용한 Java 회로 검사 데모를 구성했다. 전체 파일의 부품·핀·넷 참조를 해결하고, 명목 분압 Rule을 코드로 계산하여 정상·위반·검토 필요 판정과 원문 근거를 HTML·JSON으로 제공했다. Windows 줄바꿈이 원본 해시와 테스트 준비 코드에 미치는 영향을 추적하여 Git 정책·회귀 테스트·기존 작업 사본 복구 절차를 정리했다.

활용할 근거는 공개 샘플의 출처와 기대 결과, 38개 테스트의 범위, 정상 1.2V/위반 1.32V/값 누락 보류 사례, 실제 Windows 로그와 해결 과정입니다. 시간·정확도·검사 완료율 수치는 아직 측정하지 않았습니다.

다음 항목은 현재 성과와 구분합니다.

- 삼성전자 내부 QCV 호환성 및 실제 회사 Rule의 정답 검증
- 대용량 QCV 처리 성능·회로 전체 적합성·부품 공차·동적 응답 평가
- BOM 입력 파서와 제공 generate 모듈 연결
- Gemini/RAG 제품 연동, DB, 웹 서버, 사람 답변·재검증 이력 저장
- Spring Boot API: 다음 구현 방향으로 제안됐으나 아직 구현하지 않음

후속 기능과 해결한 문제는 [작업 및 기록 규칙](WORKFLOW.md)의 양식으로 이 문서에 추가합니다. 새 결과를 추가할 때 기존 검증 환경·근거·한계를 함께 보존합니다.

## 후속 설계 결정

### 2026-10-10 — 웹 프로젝트의 DB로 MySQL 선택

- **상태:** DB 종류는 사용자 선택으로 확정; 웹 구조와 실행 환경은 구현 제안.
- **목표:** 현재 CLI 검사 흐름을 웹의 업로드·결과 조회·이력·사람 검토로 연결.
- **선택:** 초기 PostgreSQL 제안 이후 사용자가 MySQL을 선택. 현재 데이터 저장 요구는 MySQL의 관계형 테이블·JSON 컬럼으로 충족 가능한 범위이므로 MySQL을 기준으로 후속 설계.
- **변경:** [웹 구조 및 MySQL 설계 방향](WEB_ARCHITECTURE.md)을 작성하고 문서 목차에 연결.
- **검증 범위:** 문서의 경로·링크·diff 확인. 이 작업에서 Java 테스트나 DB 연결 검증을 수행한 것으로 기록하지 않음.
- **미구현:** 디렉토리 실제 이동, Spring Boot·FE·MySQL 연결, Docker Compose 설정. 상세 버전·API·스키마는 구현 단계에서 확인.

### 2026-10-14 — SPDM 컬럼 선택·최소 정제 점검 도구

- **상태:** 첫 점검 단계 구현 및 가상 입력 검증 완료. 저장 후보·중복 키는 제안이며 실제 정제 결과 컬럼은 미확정.
- **문제와 목표:** 새 담당 영역은 이미 병합/정제된 SPDM xlsx에서 사용할 컬럼·값을 선택하고 로컬 SQLite에 저장하는 작업. 기존 Java QCV 검사 모델은 목적과 필드가 달라 별도 Python 모듈로 시작.
- **구현 범위:** `tools/spdm_import/inspect_rules.py`, `mapping.json`, `requirements.txt`, `test_inspect_rules.py`; 전체 컬럼 통계·설정 기반 선택·최소 정제·변환 오류·중복 후보·원문/정제값 미리보기. 입력 수정·재병합·문장 의미 정제·행 자동 삭제·서버·외부 API 호출은 없음.
- **설계 선택:** 중복 헤더는 열/헤더 동시 확인, 정제 결과 고유 헤더 선택도 지원. 숫자 SEC의 앞자리 0을 추측하지 않음. `|`, 핀 표현, 단위와 조건은 유지. 선택한 정제값이 비어 있으면 원문으로 자동 대체하지 않음. 날짜는 통합문서 epoch를 사용. 수식과 오류 셀은 변환 오류로 표시.
- **변경 문서:** [SPDM 시작 가이드](SPDM_IMPORT.md), 개발 가이드·문서 목차. Python 생성 캐시를 `.gitignore`에 추가.
- **검증:** 관리 Linux, Python 3.12.14 / openpyxl 3.1.5. `python -m unittest discover -s tools/spdm_import -p 'test_*.py' -v`로 가상 xlsx 11개 테스트 통과. 원본 바이트 보존·중복 헤더·코드·단위·빈값·중복 행·정제 컬럼 선택·1900/1904 날짜·오류 셀·CLI 출력/종료 코드·입력 덮어쓰기 방지를 확인. 기존 Java 테스트는 이번 작업에서 재실행하지 않음.
- **사용자 환경 확인:** 사용자가 사내 자료/프로그램 반출 불가·외부 코드 반입 가능을 확인. 실제 입력·보고서를 외부로 가져오지 않는 개발/로컬 검증 절차와 `tools/spdm_import/README.md`를 추가. 실제 회사 입력과 Windows/DRM 접근은 검증하지 않음.
- **다음 작업과 한계:** 실제 파일 점검으로 컬럼 선택·빈값 처리·행 제외·중복 관계 확정 후 SQLite 저장·재실행 정책 구현. 현재 SQLite 저장·DRM 해제·Gemini·Java 엔진 연동은 미구현. 기존 웹/MySQL 설계와 이번 로컬 SQLite 요구는 별도 범위.
- **Git 승인:** 사용자가 이번 작업의 커밋·푸시 진행을 승인. 작업 브랜치 게시 및 PR로 검토하며 main 병합은 이번 승인 범위에 포함하지 않음. 실제 커밋·브랜치·PR 결과는 완료 보고에서 확인.
- **반입 준비 검증:** 코드·매핑·의존성 명세·가상 테스트·독립 안내 5개 파일만 담은 ZIP을 로컬 `output/spdm/`에 생성. 별도 임시 폴더로 풀어 `python -m unittest discover -s . -p 'test_*.py' -v`를 실행했고 11개가 통과. 사내 입력이나 보고서, Python/패키지 바이너리는 포함하지 않음.

### 2026-10-14 — SPDM SQLite 적재·SEC별 규칙 조회

- **상태:** 로컬 구현 및 가상 입력 검증 완료. 실제 입력/정제 컬럼 계약·BOM 코드 변환은 미확정.
- **문제와 목표:** 사용자가 QCV·BOM에서 찾은 부품으로 검증할 수 있도록 규칙 DB를 고려한 뒤 SQLite 저장 구현을 요청. 점검 미리보기 일부가 아닌 전체 선택 행을 저장하고, SEC별 규칙 목록을 버전별로 조회할 수 있게 함.
- **구현:** `sqlite_store.py`, `import_rules.py`, `query_rules.py`, `test_sqlite_store.py`. `inspect_rules.py`에 전체 행 전달 콜백과 입력 바이트 지정 지원을 추가하여 점검/적재가 같은 파싱·정제 기준을 사용. 매핑의 13개 기본 컬럼과 선택된 원문/정제값·추가 컬럼 JSON·행 번호·경고·중복 위치를 저장.
- **설계:** `import_batches`의 입력/매핑 해시·파서/적재 버전으로 동일 실행 스킵. 변경된 입력/설정은 새로운 가져오기로 보관. 조회에는 명시적 가져오기 ID를 요구해 규칙 버전 혼합 방지. `(batch_id, sec_code)` 인덱스와 `(batch_id, source_row)` 유일성 제약을 사용하며 업무 중복 후보는 보존. 보드별 참조번호·관측 회로값·판정은 규칙 테이블과 분리.
- **오류 처리:** 입력/설정/DB/보고서 경로 충돌 방지. 트랜잭션 안에서 스키마 생성과 행/이력 삽입을 수행하고 변환/SQL 오류 시 전부 롤백. 기존 데이터 유지, 타 용도 DB·미지원 버전 거부. 입력의 동일 바이트를 해시/파싱. 조회는 읽기 전용, 미매칭은 NOT_FOUND/종료 코드 3이며 PASS로 간주하지 않음. 보고서 쓰기가 커밋 후 실패하면 DB 완료 여부를 별도 안내.
- **검증:** 관리 Linux, Python 3.12.14 / openpyxl 3.1.5. `python -m unittest discover -s tools/spdm_import -p 'test_*.py' -v`로 기존 11개 포함 전체 25개 테스트 통과. 25행 입력·미리보기 1행에서도 전체 적재, 코드 선행 0/타입/문장/원문·빈 규칙·중복/경고 보존, 파일/설정 변경별 조회 분리, 파일명 변경/preview=0 재실행, 변환 오류 및 실제 SQLite 트리거 실패의 전체 롤백, 읽기 전용 조회/미매칭·경로 충돌·타 DB/버전 거부를 확인. Java 테스트는 이번 작업에서 재실행하지 않음.
- **문서:** [SPDM 가이드](SPDM_IMPORT.md), [독립 반입 안내](../tools/spdm_import/README.md), 개발 가이드와 목차 갱신.
- **사용자 환경·한계:** 실제 사내 파일 없이 구현. Windows/DRM 검증 미수행. 현재 명세의 8자리 원본 SEC를 조회하며 다른 형식과의 임의 변환은 하지 않음. QCV/BOM 파싱 연동·검증기 호출·업무 유일 키·사내 컬럼 선별은 후속 작업.
- **Git 승인·게시 대상:** 사용자가 이번 SQLite 변경의 커밋·푸시와 [PR #2](https://github.com/doukdoll/circuit-agent/pull/2) 반영을 승인. 기존 `feat/spdm-inspection` 브랜치에서 이번 변경만 추가 커밋하여 일반 푸시하고 PR 제목·설명을 최종 구현 범위로 갱신. main 병합은 이번 승인 범위에 포함하지 않음. 실제 추가 커밋과 게시 결과는 완료 보고에서 확인.
- **게시 전 확인:** 직전 구현 작업의 25개 테스트 및 분리 ZIP/CLI 검증 결과를 재사용하며 이번 게시 작업에서 테스트를 새로 실행했다고 표현하지 않음. ZIP과 현재 실행 파일의 바이트 일치, 문서 링크, diff 공백, 게시 파일 목록을 확인.
- **반입 검증:** `output/spdm/spdm-import-sqlite.zip`에 실행 코드·설정·의존성 명세·테스트·독립 안내 9개 파일만 포함. 압축 무결성 및 로컬 소스와 바이트 일치를 확인하고 별도 임시 폴더에서 25개 테스트 통과. 추출 폴더에서 가상 xlsx 생성 → 실제 `import_rules.py` 프로세스로 1행 적재 → `query_rules.py`로 MATCHED/1규칙 조회까지 성공. 실제 회사 입력·DB·보고서·패키지 바이너리는 ZIP에 포함하지 않음.

### 2026-10-14 — 빈 Windows PC의 SPDM 첫 실행 안내

- **상태:** 문서 작성 및 예제 대조 완료. 예정 실행일은 사용자 기준 다음 날인 2026-10-15.
- **목표:** Python 등 개발 환경이 없는 사내 Windows PC에서 반입한 코드를 설치·점검·적재·조회할 수 있게 단계별 명령을 제공.
- **사용자 확인:** 인터넷은 사용 가능하나 프로그램의 외부 API 호출은 사용하지 않는 조건. 설치 다운로드와 로컬 실행을 구분하고, 패키지 저장소 접근이 제한될 때만 오프라인 wheel 설치를 대안으로 안내.
- **변경:** [처음 실행하기](SPDM_WINDOWS_FIRST_RUN.md) 추가, 문서 목차 및 개발 가이드 연결. Python 정식 설치·venv·패키지 버전·25개 가상 테스트·매핑 변경·점검·적재·실제 행 수·SEC 조회·재실행·DRM 문제 해결·창 재시작 절차 포함. 코드나 기존 반입 ZIP은 변경하지 않음.
- **검증:** 문서의 CLI 인수를 현재 구현과 대조, 장 순서·코드 블록·공백·문서 링크 확인. 행 수 확인용 Python 예제를 가상 SQLite에 실행해 정상 일치와 불일치 종료를 확인. 기존 앱의 25개 테스트 및 ZIP/CLI 결과는 직전 구현 결과를 재사용하고 새로 실행했다고 표현하지 않음.
- **한계:** Windows/PowerShell 명령·설치 프로그램·사내 DRM·실제 입력 접근은 이 작업에서 실행하지 않음. Python 공식 다운로드 주소는 안내용이며 이 작업에서 외부 다운로드를 수행하지 않음.
- **Git 승인·게시 대상:** 사용자가 이번 문서의 커밋·푸시를 승인. 기존 `feat/spdm-inspection`에 문서 변경만 추가 커밋하여 일반 푸시하고 [PR #2](https://github.com/doukdoll/circuit-agent/pull/2)의 안내를 갱신. main 병합은 별도 승인 범위이며 실제 추가 커밋·게시 결과는 완료 보고에서 확인.
- **게시 전 확인:** 직전 문서 작업의 예제 검증 결과를 재사용. 이번 게시에서는 문서 링크·장 순서·코드 블록·공백·파일 목록을 확인하며 앱 테스트나 Windows 실행을 새로 수행했다고 표현하지 않음.

### 2026-10-15 — 고정 analysis JSON 입력·구조화 규칙 저장

- **상태:** 구현·가상 테스트·사용자 제공 부분 입력의 로컬 적재/조회 검증 완료. 실제 입력은 저장소 및 배포 ZIP에 포함하지 않음.
- **요구:** 사용자가 고정 필드의 전처리 JSON 일부를 제공하고 Rule 파싱·DB 저장·조회와 실행 Markdown 작성을 요청. 데이터 내용은 변경될 수 있지만 컬럼/키 구조는 고정.
- **실제 구조 확인:** 최상위 체크포인트 배열 안의 `analysis.checks`가 세부 규칙 단위. 실제 키는 단수 `requirement`, 원문 checkPoint는 별도 필드로 존재하지 않음. SEC는 8자리와 4자리-6자리 두 형식. target_kind는 검사 대상 유형으로 원형 유지.
- **구현:** `analysis.schema.json`, `json_rules.py`, `inspect_json_rules.py`, `test_json_rules.py` 추가. import CLI는 JSON/Excel 자동 감지 및 `--format` 지원, JSON은 고정 계약을 사용. JSON 경로의 외부 패키지 의존성을 제거하고 표준 라이브러리만 사용.
- **저장 구조:** 스키마 v2의 `import_batches → checkpoints → rules`. 부모 원본 객체·상태·summary·issues와 각 check의 target·requirement·parameters·required_design_facts·evidence·소스 ID/JSON 위치를 보존. summary는 표시용 checkpoint, requirement는 specification으로 연결. 필요한 설계치 항목은 배열로 표시하고 실제 관측값으로 채우지 않음; original_checkpoint와 JSON design_value는 null.
- **무결성·호환:** 구조/타입·중복 JSON 키·비유한 숫자·상하위 SEC 불일치 검사. 원본 이슈·중복 규칙·수식 문자열·파라미터 타입 보존. 동일 입력/계약/버전은 스킵, 내용 변경은 새 가져오기. v1 읽기 전용 조회와 트랜잭션 v2 이관, ID 보존 및 중간 SQL 실패 시 원상복구 지원. 별도 객체가 있는 v1은 자동 이관 거부. 빈/미완료 분석도 체크포인트 이력으로 보관하고 NO_CHECKS로 조회.
- **가상 검증:** 관리 Linux/Python 3.12.14/openpyxl 3.1.5에서 전체 `python -m unittest discover -s tools/spdm_import -p 'test_*.py' -v` 37개 통과. JSON 전용 12개는 표준 라이브러리만 사용. 필드/타입·혼합 SEC·파라미터/원문 보존·빈 분석·중복·SQL 롤백·v1 이관/조회·이관 중 SQL 실패 복구·CLI 확인. Java 테스트는 재실행하지 않음.
- **실제 입력 검증:** 첨부 JSON을 `python -S`로 점검/적재/조회. 10체크포인트/35규칙/3SEC, 구조 오류 0개, 분석 이슈 11개 보존. 각 SEC의 전체 규칙 및 파라미터·근거·요구 설계 정보의 원본 일치, 부모/자식 원문 객체 일치, FK 무결성, 입력 해시 불변, 재실행 skipped 확인. 소스의 실제 규칙 내용·부품 코드는 문서/테스트에 복사하지 않음.
- **문서·배포:** [JSON 실행 가이드](SPDM_JSON_RUN.md), 목차·개발 가이드·기존 Excel 안내 갱신. JSON 전용 ZIP에는 코드·고정 계약·가상 테스트·MD·스키마 SQL만 포함. 실제 입력/DB/보고서는 로컬 output 또는 첨부 경로에 유지. `.gitignore`에 실제 입력 기본 파일명 `analysis.json` 추가.
- **한계:** Windows·DRM·QCV/BOM 사실 추출·Gemini 판정은 미검증/미연동. 원문 checkPoint의 완전한 복원이나 분석 이슈의 해결을 수행하지 않음. 이번 파일은 일부 데이터이며 다른 버전의 규칙을 자동 병합하지 않음.
- **Git:** 기존 `feat/spdm-inspection` 작업 트리에서 수정. 이번 변경의 커밋·푸시·PR 업데이트는 아직 수행하지 않음. 이전 작업의 게시 승인과 구분.
- **배포 최종 확인:** `output/spdm/spdm-analysis-json.zip`의 허용 목록 9개 파일을 로컬 코드/문서와 바이트 비교. 별도 임시 폴더에 풀어 `python -S`로 JSON 전용 12개 테스트 및 가상 입력의 점검→저장→SEC 조회 CLI 성공. 초기화용 스키마 SQL도 가상 DB에서 실행 확인. 실제 첨부/DB/보고서는 ZIP에 포함하지 않음.

### 2026-10-15 — JSON 전용 입력 확정·이전 입력 코드 제거·환경 검증

- **상태:** JSON 전용 구현과 로컬 배포 검증 완료. 실제 Windows CI의 PowerShell 5.1/7 검증 완료. 회사 PC 자체의 파일 접근 조건은 미검증이며 Linux 실제 입력 결과와 구분.
- **문제와 목표:** 사용자가 앞으로 입력은 JSON으로 고정된다고 확정하고 이전 Excel 부분 제거와 실제 입력·Windows/PowerShell 환경 검증을 요청.
- **변경:** 기존 입력 파서·매핑 설정·패키지 요구 파일·해당 테스트를 삭제. import CLI의 형식 감지/선택·컬럼 매핑 옵션, sqlite_store의 기존 입력 저장/조회·이관 분기를 제거. JSON 전용 고정 계약과 표준 라이브러리만 사용.
- **저장:** 스키마 v3의 import_batches/checkpoints/rules만 유지. 기존 입력 전용 컬럼 제거, 계약 해시 명칭 통일, 다른 가져오기의 체크포인트 연결을 복합 외래키로 차단. v1/v2 및 다른 용도의 DB는 변형 없이 거부하고 새 JSON DB에 적재하도록 안내.
- **검증 도구:** verify_environment.py 추가. Python -S 하위 CLI로 점검→전체 적재→모든 SEC 조회→원문/구조화 타입·FK 비교→재실행→값 변경→잘못된 입력 거부를 임시 한글/공백/# 경로에서 실행. 실제 OS·Python·SQLite·항목별 결과 기록, --expect-windows는 Linux에서 종료 2로 실패하며 windows_verified=false 유지. 실제 입력은 읽기만 수행.
- **가상 검증:** 관리 Linux/Python 3.12.14에서 JSON 테스트 13개 통과. 한글/공백 경로·BOM·원문·타입·미완료 분석·중복 보존·읽기 전용 조회·지원하지 않는 DB 불변·부분 SQL 실패 롤백·외부 연결 차단·CLI 검증 포함. 이전 단계의 37개는 기존 입력 호환을 포함했던 과거 결과이며 이번 테스트 수와 구분.
- **실제 입력:** 첨부본 전체 10체크포인트/35규칙/3SEC, 구조 오류 0개, 분석 이슈 11개 보존. 로컬 v3 DB 저장·전체 SEC 원문 조회 일치·동일 입력 skipped·원본 해시 불변 확인. 환경 점검에서도 내용 변경 시 새 이력과 잘못된 입력 시 기존 이력 보존 확인.
- **독립 배포 검증:** spdm-json-only.zip의 허용 목록 10개 파일만 추출하고 pip/openpyxl이 없는 새 venv에서 Python -S로 13개 테스트와 실제 첨부본 환경 검증 통과. 스키마 SQL 실행 및 버전 3 확인. ZIP은 코드·고정 계약·가상 테스트·실행 MD·SQL만 포함하며 실제 첨부/DB/보고서는 포함하지 않음.
- **Windows 구성:** GitHub Actions windows-latest에서 PowerShell 7(pwsh)와 Windows PowerShell 5.1(powershell)을 각각 사용해 가상 데이터로 실행하는 workflow 준비. 이후 실제 실행/성공 결과는 아래 후속 근거에 기록. 회사 PC의 접근 권한·DRM 조건은 그 PC에서 제공된 환경 검증 명령으로 별도 확인 필요.
- **문서:** JSON 실행 가이드·기존 진입 문서·목차·개발 가이드 갱신. 추가 설치 패키지·가상환경 활성화·외부 API 없이 실행하며 새 DB 경로 사용.
- **범위/게시:** QCV/BOM 파싱·Gemini 판정은 변경/검증하지 않음. 기존 작업 브랜치 feat/spdm-inspection 사용. 사용자가 이번 코드·문서·가상 Windows workflow의 커밋·푸시·PR 갱신 및 Windows 테스트 실행을 승인. 실제 데이터 산출물은 로컬에 유지.

- **Windows CI 초기 오류:** 첫 workflow는 shell 속성의 matrix 표현식이 GitHub 문맥 검사에서 거부되어 작업 시작 전 실패(run 38720451877). YAML 파싱 성공만으로 GitHub 표현식 유효성을 입증할 수 없었음. 각 step의 shell을 pwsh/powershell 상수로 지정하고 if 조건으로 선택하도록 수정해 재실행. Python 기능 오류나 Windows 런타임 테스트 실패와 구분.

- **Windows 최종 근거:** [run 38720635486](https://github.com/doukdoll/circuit-agent/actions/runs/38720635486), 구현 ff08c37 및 workflow 수정 5fbcf34 기준 PR 병합 미리보기(e2c7765)에서 성공. Windows Server 2025 / Python 3.12.10 / SQLite 3.49.1, Windows PowerShell 5.1.26100.33438(job 116374033312) 및 PowerShell 7.6.6(job 116374033610) 각각 가상 테스트 13개와 환경 검증 전체 통과. 한글·공백·# 경로, Python -S 실행, system=Windows/windows_verified=true 확인. 가상 2체크포인트/4규칙/2SEC의 전체 적재·조회·타입 보존·새 이력·오류 거부·반복 스킵 검증. 회사 첨부본을 Windows CI에 전송하지 않음. 이후 문서만 갱신하며 이 실행 결과를 재사용, 추가 런타임 실행으로 표현하지 않음.

### 2026-10-15 — 가져오기 이력 제거·최신 규칙만 유지

- **상태:** 로컬 구현·테스트·실제 부분 JSON 적재/조회·독립 ZIP 검증 완료. 이번 변경의 커밋·푸시 및 Windows CI 재실행은 수행하지 않음.
- **요구와 결정:** 사용자가 최신 규칙만 관리한다고 확정. 내용 변경 시 전체 규칙을 새 batch로 중복 저장하던 구조를 제거. 최신 전체 JSON을 하나의 현재 데이터 집합으로 취급하고 이전 판본을 보관하지 않음.
- **구조/API:** 스키마 v4는 checkpoints/rules 두 테이블만 사용. import_batches와 batch_id, 가져오기 메타데이터·동일 파일 스킵 분기를 삭제. rules(sec_code) 인덱스로 조회, lookup_rules(database, sec_code)와 CLI의 --sec-code만 사용. 부모/자식 원문·상태·이슈·파라미터·근거 및 소스 식별자는 그대로 보존.
- **교체 동작:** 구조 검증 후 BEGIN IMMEDIATE에서 자식/부모 삭제와 새 데이터 삽입을 한 번에 커밋. 첫 적재 imported, 기존 데이터가 있으면 동일 파일도 replaced. SQL 오류는 삭제 및 부분 삽입을 롤백하여 기존 데이터 복구. 신규 JSON에서 빠진 SEC·체크포인트·규칙은 남기지 않으며 부분 입력 누적은 지원하지 않음. 내부 정수 ID는 재사용될 수 있어 외부 영속 식별자로 사용하지 않음.
- **기존 DB:** v1/v2/v3는 자동 변환·덮어쓰기하지 않고 새 rules-latest.sqlite 경로에 입력을 적재하도록 안내. 기존 파일을 변경하지 않음. 이후 동일 v4 DB를 최신 JSON으로 갱신.
- **가상 검증:** 관리 Linux/Python 3.12.14에서 Python -S 테스트 15개 통과. 35→36개 추가 후 전체 36행, 규격 변경, 이전 SEC 삭제, 25회 반복 저장 후 행·SQLite 페이지 수 비누적, 삭제 후 부분 삽입 실패 시 기존 조회 결과 복구 확인. 구조/타입·원문·빈 분석·중복·FK·읽기 전용 조회·기존 버전 거부·네트워크 차단·CLI 검증 포함.
- **실제 입력/배포:** 첨부본 10체크포인트/35규칙/3SEC, 구조 오류 0개·분석 이슈 11개 보존. 새 v4 DB 저장과 전체 SEC 원문 조회, 5회 추가 적재 후 10/35행 및 페이지 수 불변, 원본 바이트 불변 확인. spdm-json-latest.zip의 허용 목록 10개 파일을 한글·공백·# 임시 경로에 추출하고 pip/외부 패키지 없는 새 venv에서 Python -S 환경 검증(테스트 15개 및 실제 JSON CLI 전 과정) 통과. schema_v4.sql 초기화도 실행 확인.
- **Windows 범위:** 이전 v3의 Windows PowerShell 5.1/7 성공은 과거 근거이며 이번 v4 검증으로 표현하지 않음. 현재 PC의 실제 OS를 기록하는 환경 검증기는 v4 교체 동작을 확인하도록 갱신했으며 Windows 재실행은 아직 없음. 회사 PC의 실제 입력·DRM·QCV/BOM·Gemini 판정도 별도 범위.
- **문서/산출물:** JSON 실행 가이드·모듈 README·개발 가이드·목차를 최신 교체/SEC 조회 명령으로 갱신. 새 ZIP과 SQL은 기존 배포와 구분. 실제 입력·DB·보고서는 output/첨부 경로에만 두며 ZIP/저장소에 포함하지 않음. SQLite 파일의 빈 페이지는 재사용되므로 규칙 삭제 시 물리 파일이 즉시 축소된다고 보장하지 않음.
- **Git:** feat/spdm-inspection 작업 트리에서 수정. 현재 작업에 대한 새 게시 승인이 없으므로 로컬 반영만 완료했으며 main 또는 PR을 갱신하지 않음.

### 2026-10-15 — 최신 규칙 v4의 실제 Windows JSON 테스트

- **상태:** 실제 Windows CI에서 PowerShell 5.1/7 모두 성공. 사용자가 v4를 Windows에서 JSON으로 테스트하도록 요청했으며 기존에 승인한 코드 게시·Windows 테스트 목적과 경로로 진행.
- **변경:** PowerShell 5.1/7 각각 UTF-8 BOM의 가상 JSON 파일(10체크포인트/35규칙/3SEC/분석 이슈 11개)을 명시적으로 생성하고 --input으로 전달하도록 workflow 보강. 부품 코드·규칙 문구·이슈는 직접 만든 가상 값이며 실제 회사 입력을 사용하지 않음.
- **검증 범위:** 스키마 v4의 15개 테스트와 저장→모든 SEC 조회→원문/타입 보존→동일 입력 비누적→최신 교체→잘못된 입력 거부를 실제 Windows에서 실행 예정. 초기 JSON 파일을 수정하지 않았는지도 검증. 실행 결과는 완료 후 추가.
- **게시:** feat/spdm-inspection에 최신 규칙 전용 코드·문서·가상 테스트·workflow만 게시. 실제 첨부 JSON·DB·보고서 및 배포 ZIP은 제외. main 병합은 수행하지 않음.

- **첫 실행:** run 38721867130에서 PowerShell 7의 v4 테스트 15개·명시적 JSON 파일 환경 검증 성공. PowerShell 5.1은 Python 시작 전 ps1 문자열 종료 파싱 오류로 실패. UTF-8 BOM 없는 실행 스크립트의 한글 파일명 해석 문제를 피하도록 workflow 본문을 ASCII로 바꾸고 한글 작업 경로는 Unicode 코드 포인트로 생성. 입력 JSON은 UTF-8 BOM과 한글 내용을 그대로 유지하며 Python 내부 한글/공백/# 경로 검증도 유지. 수정 후 재실행 결과를 별도 기록.

- **v4 최종 Windows 근거:** [run 38722021083](https://github.com/doukdoll/circuit-agent/actions/runs/38722021083), 구현 02833ab 및 CI 인코딩 수정 74296ab 기준. Windows Server 2025 / Python 3.12.10 / SQLite 3.49.1. Windows PowerShell 5.1.26100.33438(job 116378634794)과 PowerShell 7.6.6(job 116378635177) 각각 테스트 15개 및 명시적 UTF-8 BOM JSON 파일 검증 전체 성공. 10체크포인트/35규칙/3SEC/분석 이슈 11개 보존, 원문·구조화 타입·모든 SEC 조회·외래키·반복 비누적·최신 교체·잘못된 입력 시 기존 DB 보존·원본 불변 확인. 35→36개 추가·규격 변경·SEC 삭제·25회 페이지 비누적·SQL 롤백은 함께 실행된 15개 테스트에 포함.
- **완료/배포:** 실행 결과는 output/spdm/latest-validation/windows-powershell51.json 및 windows-pwsh7.json으로 로컬 보관. JSON 실행 가이드와 ZIP의 MD를 최신 v4 Windows 성공 근거로 갱신. 테스트한 런타임 코드는 그대로이며 문서 갱신 후 테스트를 새로 수행한 것으로 기록하지 않음. feat/spdm-inspection에 일반 푸시하고 PR #2 설명 갱신. 실제 회사 파일은 게시하지 않음.

### 2026-10-16 — SEC 코드 형식 제한 완화(v5)

- **요구:** 사용자가 안내한 세 부분을 직접 수정했으며 저장소에도 같은 변경과 커밋·푸시를 요청. 8자리/10자리/하이픈 유무를 허용하고 하이픈 제거 등 자동 변환은 하지 않음.
- **구현:** JSON 계약의 SEC pattern을 string/minLength 조건으로 교체, validate_sec_code는 문자열·공백뿐인 값만 검사하고 원문 반환, SQL SEC_CHECK는 length(trim(sec_code)) > 0. 스키마 버전 5, 기존 v4 이하 DB는 변형 없이 거부하고 새 rules-flex.sqlite 사용. 최신 규칙 교체 및 두 테이블 구조는 유지.
- **검증:** Linux/Python 3.12.14에서 가상 테스트 18개 통과. 8/10자리·하이픈·영문·대소문자·앞뒤 공백의 원문 및 개별 조회 보존, 빈값/null/숫자 거부 후 기존 DB 불변, 양쪽 테이블 SQL 빈값 제한, v4 버전 거부 확인. 기존 규칙 교체/비누적/롤백 등 포함. Windows CI의 명시적 JSON fixture에도 10자리 SEC를 추가했으며 실행 결과는 후속 기록.
- **문서/게시:** 실행 가이드·개발 가이드·모듈 README를 새 DB/스키마/SEC 정책으로 갱신. feat/spdm-inspection에 소스·문서·가상 테스트만 커밋·일반 푸시하고 PR #2 갱신. 실제 회사 입력·DB·보고서는 게시하지 않음.

- **v5 Windows/배포 결과:** [run 38841920516](https://github.com/doukdoll/circuit-agent/actions/runs/38841920516), 구현 15478f3 기준. Windows Server 2025/Python 3.12.10, PowerShell 5.1.26100.33438(job 116783734525)과 7.6.6(job 116783734256) 각각 테스트 18개 및 명시적 JSON 파일 환경 검증 전체 통과. 8자리·10자리·하이픈 포함 SEC의 가상 JSON 사용, 한글/공백/# 경로·최신 교체·원문/타입 보존·오류 거부 확인. 새 spdm-json-flex.zip(10개 파일)을 pip/외부 패키지 없는 별도 환경에 추출하여 Python -S로 18개 테스트와 혼합 SEC 가상 JSON CLI 검증 통과. schema_v5.sql 초기화 확인. 이후 문서만 갱신하며 런타임 테스트를 다시 실행한 결과로 표현하지 않음. 실제 입력/DB/보고서는 ZIP과 게시 대상에서 제외.

### 2026-10-16 — 환경 검증의 실제 JSON 검사 오류 사유 누락 수정

- **사용자 확인:** 사내 Windows 11/Python 3.15.0/SQLite 3.53.4에서 기존 가상 테스트 18개 통과 후 실제 입력 inspect 단계가 종료 2로 실패. stderr가 비어 environment.json의 error에 실제 원인이 표시되지 않음. 사용자 제공 보고서에 근거하며 해당 PC나 입력을 직접 재현한 결과가 아님.
- **확인된 코드 문제:** inspect CLI는 구조/값 오류를 JSON 보고서와 stdout에 쓰지만 환경 점검기가 stderr만 포함하고 임시 보고서는 종료 시 삭제. 실제 입력 오류 항목은 현재 보고서에서 알 수 없음. Python 버전·SEC 형식·보안 환경을 원인으로 단정하지 않음.
- **수정:** 하위 명령 실패 시 command/종료 코드/stdout/stderr 보존, 검사 보고서의 오류 path/reason(최대 50개)을 failed_step.inspection에 복사. 원문 미리보기는 제외. stdout과 검사 오류를 사용해 빈 사유 방지. 구조 검사 전 원본 JSON의 키를 직접 탐색하던 부분을 검사 성공 후로 이동하여 잘못된 JSON/필드 누락도 같은 진단 경로로 보고. DB 스키마와 규칙 허용 조건은 변경하지 않음.
- **검증:** Linux/Python 3.12에서 테스트 21개 통과. stderr가 빈 SEC 부모/하위 불일치, 잘못된 JSON/필드 누락/중복 키, 검사 보고서 없는 stderr 오류에 대한 회귀 테스트 포함. 실제 사내 오류의 원인은 사용자에게 path/reason 확인을 요청한 상태. Windows/Python 3.15 재실행은 아직 수행하지 않음.
- **문서:** JSON 실행 가이드·개발 가이드에 원문 미리보기 없는 별도 검사 명령과 새 진단 필드 설명 추가. 이번 수정은 로컬 반영이며 아직 커밋·푸시하지 않음.

### 2026-10-16 — 실제 입력의 적용 범위 null·선택 error 지원(v6)

- **근거:** 사용자 검사 결과 28개 중 처음 10개를 확인. applicability:null의 string 타입 오류와 최상위 error 필드 거부를 확인. 전체 오류 목록과 error 자료형을 추가 요청했으며 실제 값/원문 자료를 요구하지 않음.
- **변경:** applicability는 string/null을 허용하고 SQL TEXT NULL로 원형 보존. 최상위 error는 선택 JSON 메타데이터로 받아 부모 raw_json에 저장하고 조회 source_error/has_source_error_field에 표시. null 적용 범위는 경고, 비어 있지 않은 error/미완료 상태는 검토 필요로 표시. 원본 분석 오류가 있는 데이터가 자동 PASS가 되지 않으며 알 수 없는 다른 필드는 계속 거부.
- **DB:** SQL 제약 변경으로 버전 6, 기존 v5 이하 DB는 보존하고 새 rules-v6.sqlite에 적재. 이력/테이블 추가 없이 최신 두 테이블 구조 유지.
- **검증:** Linux/Python 3.12에서 24개 테스트 통과. null의 SQL/JSON 왕복, error null/문자열/객체 보존, checks 없는 실패 객체의 NO_CHECKS, checks와 error 병존 시 검토 표시, 임의 신규 키 거부, v5 보호 포함. 검사 진단 보존 수정도 같은 작업 트리에 유지. 실제 사내 전체 입력과 Windows/Python 3.15의 수정 후 성공은 아직 확인하지 않음.
- **문서:** v6 실행 가이드/README/개발 가이드에 필드 의미와 새 DB 경로를 갱신. 현재 로컬 수정이며 커밋·푸시는 아직 수행하지 않음.


## SPDM 트러블슈팅 기록

이 절은 SPDM 개발 중 발생한 문제를 증상·원인·대응·검증 상태별로 찾기 위한 기록이다. 위 날짜별 이력과 함께 유지한다. 아래 테스트 결과는 각 작업에서 이미 실행한 결과를 재사용했으며 이번 문서 정리에서 새로 실행한 것으로 표현하지 않는다. 실제 회사 JSON·규칙 문구·개인 파일 경로는 기록하지 않는다.

| 기록 | 문제 | 현재 확인 상태 |
| --- | --- | --- |
| TS-004 | Windows CI의 matrix 셸 표현식 거부 | 수정 후 실제 Windows CI 성공 |
| TS-005 | PowerShell 5.1 실행 스크립트 문자열 파싱 오류 | 수정 후 실제 Windows CI 성공 |
| TS-006 | SEC 길이·하이픈 제한으로 다른 형식 수용 불가 | v5 구현 및 Linux/Windows 테스트 성공 |
| TS-007 | environment.json에 실제 입력 검사 실패 사유 누락 | 로컬·Windows CI 회귀 검증 완료, 사용자 PC 재검증 대기 |
| TS-008 | 실제 JSON의 null·선택 error와 부분 샘플 기반 계약 불일치 | 사내 현재 파일 구조 검사·1,000체크포인트/2,572규칙 적재·선택 SEC 조회 성공 확인 |
| TS-010 | 탐색기 압축 해제 위치와 명령의 기본 경로 불일치 | 실제 코드 폴더 지정 안내, 후속 프롬프트에서 이동 확인 |
| TS-011 | Read-Host 안내문을 경로 대입으로 오해해 빈 변수 생성 | 원인 확인·직접 대입 안내, 후속 Python 실행 확인 대기 |

### TS-004 — Windows CI 셸 표현식이 실행 전 거부됨

- **발생 환경/증상:** GitHub Actions에 추가한 Windows workflow가 작업 생성 전 실패. `Unrecognized named-value: 'matrix' ... matrix.shell`이 표시됐고 jobs가 없었다. Python 테스트는 아직 실행되지 않은 상태였다.
- **확인 방법:** PR 이벤트만 조회하는 실행 목록에는 초기 실패가 보이지 않아 전체 workflow run 목록과 실행 페이지 annotation을 확인했다. YAML 파싱만 통과한 사실을 GitHub의 표현식 검사 통과로 간주할 수 없었다.
- **원인:** 해당 shell 속성에서 사용한 matrix 표현식이 GitHub workflow 검증에서 거부됐다.
- **대응/최종 수정:** pwsh/powershell step을 각각 두고 shell을 상수로 지정했다. matrix 값에 따른 선택은 각 step의 if 조건에서 수행했다.
- **재검증:** 초기 실패 run 38720451877 이후 [run 38720635486](https://github.com/doukdoll/circuit-agent/actions/runs/38720635486)에서 실제 Windows 양쪽 셸 성공. 수정 커밋 5fbcf34. 당시 테스트는 13개였으며 최신 버전의 테스트 수와 구분한다.
- **재발 방지:** CI 설정은 YAML 구문 확인과 실제 workflow 실행을 모두 확인한다. 실행 전 설정 오류를 Python/Windows 기능 실패로 기록하지 않는다.
- **관련 파일:** `.github/workflows/spdm-json-windows.yml`.

### TS-005 — PowerShell 5.1에서 CI 스크립트 문자열 파싱 실패

- **발생 환경/증상:** 명시적 JSON fixture 생성 단계를 추가한 run 38721867130에서 pwsh는 성공했지만 powershell은 Python 실행 전에 `TerminatorExpectedAtEndOfString`으로 실패했다.
- **가설/확인:** 한글 파일명 리터럴을 추가한 ps1의 인코딩 처리를 조사했다. BOM 없는 UTF-8을 사용하는 Windows PowerShell 5.1의 해석 차이를 피하는 방식으로 수정했다. 사내 PC의 Python 데이터 파싱 실패와는 다른 단계의 증상이다.
- **대응/최종 수정:** workflow 실행문을 ASCII로 작성하고 한글 작업 경로는 Unicode 코드 포인트로 생성했다. fixture 생성 코드는 Python 파일로 저장해서 실행하고 JSON은 UTF-8 BOM으로 썼다. Python 내부의 한글·공백·# 경로 검증은 유지했다.
- **재검증:** 수정 74296ab 이후 [run 38722021083](https://github.com/doukdoll/circuit-agent/actions/runs/38722021083)에서 Windows PowerShell 5.1.26100.33438과 PowerShell 7.6.6 모두 v4 테스트 15개 및 명시적 JSON 파일 검증 성공.
- **재발 방지:** PowerShell 5.1용 파일에 한글을 직접 넣어 저장할 때 UTF-8 BOM을 명시한다. CI 스크립트 파싱과 Python 프로그램의 UTF-8 JSON 지원을 구분한다.
- **관련 파일:** Windows workflow 및 JSON 실행 가이드의 PowerShell 안내.

### TS-006 — SEC 코드 자리수·하이픈 제한

- **발생 조건/증상:** 사용자가 실제 SEC에 8자리·10자리·하이픈 유무가 섞여 있다고 확인. 기존 계약은 8자리 숫자 또는 4자리-6자리 형식만 허용했다.
- **원인:** 형식 제한이 JSON 계약, 조회용 Python 정규식, 양쪽 SQLite 테이블 CHECK에 각각 존재했다. 한 곳만 바꾸면 다른 단계에서 다시 거부될 수 있었다.
- **최종 수정:** `$defs.sec`를 string/minLength 조건으로 교체하고 validate_sec_code는 비어 있지 않은 문자열을 검사한 뒤 원문을 반환한다. SQL SEC_CHECK는 `length(trim(sec_code)) > 0`으로 변경. 하이픈 제거·대소문자/선행 0/앞뒤 공백 변환은 하지 않는다. 빈 문자열·공백뿐인 값·null·숫자 타입 거부와 부모/하위 SEC 원문 일치 검사는 유지한다.
- **DB 대응:** 버전을 4에서 5로 올리고 새 rules-flex.sqlite에 적재하도록 안내했다. 버전 숫자를 바꾸는 것만으로 기존 테이블의 CHECK가 변경되지는 않는다. 기존 DB는 자동 수정하지 않는다.
- **검증:** Linux 테스트 18개와 [Windows run 38841920516](https://github.com/doukdoll/circuit-agent/actions/runs/38841920516)의 PowerShell 5.1/7 테스트 18개 및 혼합 형식 JSON 파일 검증 성공. 서로 다른 표기를 자동으로 같은 코드에 합치지 않음을 확인. 구현 15478f3, 결과 기록 5c80aa0.
- **재발 방지:** 식별자의 형식 허용과 식별자 정규화를 별도 정책으로 관리한다. 원본→수정본을 보여주고 JSON 검사·Python 조회·SQL 제약·기존 DB 처리까지 함께 안내한다.
- **관련 파일:** `analysis.schema.json`, `sqlite_store.py`, `test_json_rules.py`.

### TS-007 — 실제 JSON 검사 오류가 environment.json에서 빈 사유로 표시됨

- **사용자 환경/증상:** Windows 11 / Python 3.15.0 / SQLite 3.53.4. 사용자 보고서에서 기존 가상 테스트 18개는 통과했지만 `inspect_json_rules.py: 종료 2, 예상 0:`으로 실패했으며 뒤의 사유가 비었다. 이는 사용자 제공 결과이며 해당 PC를 직접 실행한 결과가 아니다.
- **확인된 원인:** inspect CLI는 입력 오류 항목을 검사 JSON에 기록하고 요약을 stdout으로 출력한다. 기존 환경 점검기는 stderr만 오류 메시지에 넣었다. 검사 보고서가 있던 임시 폴더도 종료 시 삭제되어 원인이 남지 않았다.
- **진단 절차:** inspect CLI를 별도로 `--preview 0`으로 실행하고 issues에서 severity=error인 항목의 path/reason만 확인하도록 안내했다. 이 단계에서 실제 입력의 null/선택 필드 문제(TS-008)가 드러났다. Python 재설치·버전 변경으로 해결을 시도한 사실은 없다.
- **최종 코드 수정:** 하위 명령의 stdout/stderr/종료 코드를 failed_step에 보존하고 검사 JSON의 오류 path/reason을 최대 50개 복사한다. 원문 미리보기는 포함하지 않는다. 실제 JSON의 키를 직접 탐색하기 전에 구조 검사부터 완료하도록 순서를 수정했다.
- **로컬 재검증:** 진단 수정 시 테스트 21개 통과. stderr는 비었지만 검사 JSON에 SEC 불일치 사유가 있는 가상 사례에서 기존의 빈 오류를 재현하고 수정 후 경로/사유가 남는지 확인했다. 잘못된 JSON·누락 필드·중복 키·보고서가 없는 stderr 오류도 검증했다. 이후 v6의 24개 테스트에 포함된다.
- **상태/한계:** 로컬 수정·회귀 검증 완료. 사내 Windows/Python 3.15에서 수정한 점검기의 재실행 성공은 아직 확인하지 않았다. 이 로그만으로 Python 3.15 호환성 전체를 보장하거나 설치 문제가 원인이라고 결론 내리지 않는다.
- **관련 파일:** `verify_environment.py`, 환경 진단 회귀 테스트, 실행 가이드의 별도 검사 명령.

### TS-008 — 실제 데이터의 applicability:null과 선택 error를 계약이 거부함

- **발생 환경/증상:** 사내 실제 JSON을 별도 검사한 결과 오류 28개·경고 0개. 사용자가 제공한 처음 10개에는 `/0/analysis/checks/0/applicability` 같은 위치의 `string 필요, null 입력`과 최상위 `/0/error` 같은 위치의 `고정 계약에 없는 필드`가 포함됐다. 위 경로는 익명화 예시다.
- **확인된 원인:** 처음 받은 부분 샘플을 기준으로 applicability를 필수 문자열로만 정의했고 최상위 속성을 닫힌 목록으로 제한하면서 선택 error를 정의하지 않았다. 실제 입력에서 확인된 미제공 값과 분석 실패 메타데이터를 지원하지 못한 것이다. JSON 키 이름이 동일하다는 것과 값이 null일 수 있는지, 선택 메타데이터가 있는지는 별도로 확인해야 했다.
- **집계 해석:** 검사 출력의 체크포인트/규칙/SEC 0은 실제 데이터가 비었다는 뜻이 아니다. 초기 구조 검사에서 오류가 발생하면 이후 행 펼치기와 통계를 수행하지 않는 기존 동작 때문이다.
- **잠재 후속 제약:** SQL의 applicability TEXT NOT NULL도 null 저장을 차단한다. 이번 사용자 로그는 SQL 단계 이전 검사 실패이므로, SQL 오류가 실제 발생했다고 기록하지 않는다. 코드 확인에 따라 입력 계약과 함께 수정한 제약이다.
- **최종 수정:** JSON의 applicability를 string/null로 허용하고 SQL 컬럼을 nullable TEXT로 바꾼다. 최상위 error를 선택 JSON 메타데이터로 허용하며 required에는 넣지 않는다. null을 빈 문자열로 바꾸지 않고 SQL NULL로 저장한다. error는 부모 raw_json에 원형 저장하고 source_error/has_source_error_field로 조회한다. 미제공 적용 범위·분석 실패는 검토 표시를 남기며 PASS를 생성하지 않는다. 다른 알 수 없는 필드와 잘못된 SEC 타입은 계속 거부한다.
- **수동 수정 안내:** 사내 v5 코드 기준으로 analysis.schema.json의 applicability 및 checkpoint.properties.error, sqlite_store.py의 SCHEMA_VERSION 5→6 및 rules.applicability NOT NULL 제거를 원본→수정본으로 안내했다. 이는 입력 거부·SQL 저장 문제의 필수 변경이다. 상세 진단·조회 표시·추가 테스트는 v6 전체 코드에 포함돼 수동 최소 수정과 전체 배포의 범위를 구분한다.
- **DB 대응:** 기존 v5 이하 DB는 보존하고 새 rules-v6.sqlite를 사용한다. CREATE TABLE 정의 변경과 버전 숫자 변경만으로 기존 DB의 NOT NULL이 사라지지 않는다. 환경 점검기의 임시 DB와 실제 운영 DB 생성은 별개 단계다.
- **로컬 재검증:** Linux/Python 3.12에서 v6 테스트 24개 통과. null의 SQL/JSON 왕복, error의 null/문자열/객체 보존, checks 없는 분석 실패의 NO_CHECKS, checks와 error 병존 시 검토 표시, 예상하지 않은 필드 거부, 기존 v5 보호를 확인했다. 별도 패키지 없는 venv에 v6 ZIP 10개 파일을 추출해 가상 혼합 데이터의 점검·저장·SEC 조회·최신 교체 전 과정도 통과했다. 실제 사내 파일을 가져와 실행한 결과가 아니다.
- **상태/다음 확인:** 이후 사용자 사내 실행 로그에서 현재 입력의 구조 검사 성공을 확인했다: 1,000체크포인트/2,572규칙/143SEC, 오류 0·경고 950·원본 분석 이슈 923. 사용자 보고서에 근거하며 해당 파일을 외부에서 직접 실행한 결과가 아니다. 이전 오류 28개의 전체 목록·error의 실제 자료형·입력 파일 동일 해시는 확인하지 않았으므로 각각의 이전 오류가 어떻게 해소됐는지 추정하지 않는다. 이후 사용자 로그로 rules-v6.sqlite에 imported/1,000체크포인트/2,572규칙 저장과 선택한 SEC의 MATCHED/2체크포인트/4규칙 조회 성공도 확인했다. 환경 점검기 전체 재실행·143개 SEC 전수 조회·실제 회로 판정은 아직 확인하지 않았다.
- **재발 방지:** 정제 담당자와 필수/선택 키 및 필드별 null 허용 여부를 명시한다. 부분 샘플에서 보이지 않은 값 상태를 전체 계약으로 단정하지 않는다. 분석 성공·실패·미완료 입력을 가상 테스트에 포함한다. 오류가 난다고 모든 additionalProperties/타입 검사를 한꺼번에 해제하지 않는다. 사용자 PC에서 수정이 필요하면 정확한 원본→수정본과 새 DB 필요 여부를 먼저 안내한다.
- **관련 파일:** JSON 계약·파서·SQLite 저장/조회·환경 점검기·가상 테스트·[실행 가이드](SPDM_JSON_RUN.md). 이번 v6 및 진단 수정은 72a84c7로 feat/spdm-inspection에 커밋·푸시했다. Windows CI 결과는 아래 게시 기록에 추가했고 사내 현재 파일의 구조 검사 성공은 후속 기록에 남겼다. DB 적재·선택 SEC 조회 성공은 후속 사용자 로그로 확인했으며 환경 점검기 전체 재실행은 대기 중이다.

### v6 수정 및 트러블슈팅 기록 게시

- 사용자가 v6 수정·진단 개선·트러블슈팅 기록의 커밋·푸시를 승인. 기존 feat/spdm-inspection 브랜치와 PR #2를 갱신하며 main 병합은 수행하지 않음.
- Windows CI 가상 JSON에 applicability:null, checks와 error가 함께 있는 항목, analysis:null/status:error 항목을 추가. 11체크포인트/35규칙/3SEC 가상 파일로 두 PowerShell 환경에서 확인. 회사 원본은 포함하지 않음. 실행 결과는 완료 후 기록.

- **최종 Windows/게시 근거:** 구현 72a84c7을 feat/spdm-inspection에 일반 푸시. [run 38844322522](https://github.com/doukdoll/circuit-agent/actions/runs/38844322522)에서 Windows Server 2025/Python 3.12.10, PowerShell 5.1.26100.33438(job 116791274539)과 7.6.6(job 116791274357) 각각 테스트 24개 및 JSON CLI 환경 검증 전체 성공. 가상 11체크포인트/35규칙/3SEC 파일에 null 적용 범위와 분석 실패 항목 포함. 검사 진단 보존과 null/error 왕복은 24개 테스트에 포함. 이 결과는 사내 Windows 11/Python 3.15의 실제 전체 입력 성공을 뜻하지 않는다.
- **문서/검증 구분:** 트러블슈팅 TS-004~008, 수동 원본→수정본 및 새 DB 경로를 같은 PR #2에 포함. 위 결과 확인 후 문서만 갱신하며 런타임 테스트를 새로 반복한 결과로 표현하지 않음. 실제 입력·DB·보고서·배포 ZIP은 Git 게시에서 제외.

### 사내 현재 입력 파일의 JSON 구조 검사 성공 확인

- **사용자 확인:** 사내 PowerShell에서 inspect_json_rules.py 실행 결과 1,000체크포인트/2,572규칙/143고유SEC, 오류 0개·경고 950개·원본 분석 이슈 923개. 가상 테스트나 외부 재현이 아니라 사용자가 제공한 실제 실행 출력으로 확인.
- **해석:** 구조/타입·SEC 일치 등의 필수 검사를 통과하여 해당 파일을 적재할 수 있는 상태. 원본 분석 issues 923개가 경고에 포함되고 다른 파서 주의 항목이 27개 추가된다. 경고 수는 부품/규칙별 FAIL 수나 고유 문제 수가 아니다. 원본 모호함/분석 실패/미제공 값을 수정·삭제하거나 회로 PASS로 판단한 결과도 아니다.
- **다음 단계:** 실제 적재·조회는 별도 확인. 기존 rules-latest.sqlite에 이전 버전 제약이 남아 있을 수 있으므로 v6 코드는 새 rules-v6.sqlite 경로 사용 안내. 경고 내용의 분류·개별 규칙 검토도 필요. 사내 전체 Rule 원본이나 추가 보드 검증 완료로 확대 해석하지 않음.
- **기록 범위:** 이번에는 사용자 로그에 따른 문서 상태만 갱신. 프로그램 코드를 변경하거나 런타임 테스트를 다시 수행하지 않았으며 커밋·푸시는 아직 하지 않음.

### 사내 실제 DB 적재·선택 SEC 조회 성공 확인

- **적재 확인:** 사용자 PowerShell 로그의 상태 imported, 오류 0·경고 950·중복후보 0, stored_checkpoints=1,000/stored_rows=2,572. rules-v6.sqlite 파일에 저장 완료로 보고됨. 실제 회사 파일이나 DB를 외부에서 읽은 검증은 아니다.
- **조회 확인:** 같은 DB에서 사용자가 선택한 SEC의 match_status=MATCHED, checkpoints 2개/rules 4개를 반환. 원문·parameters·required_design_facts·evidence·원본 이슈·소스 위치가 출력되는 것 확인. 실제 SEC 값·규격 문구·출처 식별자는 문서와 가상 테스트에 복사하지 않음.
- **의미:** 전체 저장 규칙 수와 단일 SEC 조회 규칙 수는 범위가 다르다. MATCHED는 규칙을 찾았다는 뜻이며 실제 QCV/BOM 준수 여부 판정은 아니다. has_preprocessing_issues=true는 원본 분석 이슈를 보존한 정상 동작. original_checkpoint=null은 독립 원문 필드 부재, design_value=null은 실제 회로 설계값 미수집 상태를 나타낸다.
- **범위/한계:** 현재 사용자 파일의 구조 검사→SQLite 적재→선택 SEC 조회까지 성공 확인으로 상태 갱신. 143개 SEC 전수 비교, 값 변경 후 사내 DB 교체, 환경 점검기 전체 재실행, 원본 이슈 해결·QCV/BOM 연결·Gemini 판정까지 확인된 것으로 기록하지 않음.
- **문서 작업:** 사용자 결과를 반영한 기록과 실행 가이드만 갱신. 이번 턴에 코드나 테스트를 변경/재실행하지 않으며 아직 커밋·푸시하지 않음.

### AUTOINCREMENT ID 정책 추가(v7)

- **요구:** 사용자가 삭제된 ID 재사용 방지의 장점을 검토한 후 두 테이블을 AUTOINCREMENT로 교체하고 사내 코드의 정확한 수정 위치 안내를 요청.
- **구현:** checkpoints.id/rules.id를 INTEGER PRIMARY KEY AUTOINCREMENT로 변경, SCHEMA_VERSION 6→7. 동일 DB 파일에서 이전에 커밋된 번호를 재사용하지 않으며 부모/자식 INSERT와 연결은 새 ID 기준으로 유지. 기존 두 업무 테이블의 최신 전체 교체·롤백·SEC/null/error 정책 유지.
- **구별:** 동일 규칙의 ID 고정, 과거 데이터 이력 저장, ON DELETE CASCADE 추가는 수행하지 않음. 새 DB 파일에 이전 v6의 번호 이력이 자동 이전되는 것도 아님. SQLite 내부 sqlite_sequence는 번호 관리용이고 업무 테이블이 아니다. 코드/버전 수정만으로 기존 DB DDL이 바뀌지 않으므로 v6를 보존하고 새 rules-v7.sqlite에 JSON 재적재 안내.
- **검증:** Linux/Python 3.12에서 25개 테스트 통과. 양쪽 최대 ID가 재적재 후 증가, 현재 행 수만 유지, 새 부모 연결·FK·원문 조회 유지 확인. 업무 테이블 검사에서 sqlite_% 내부 테이블 제외. 기존 버전 거부 대상에 v6 추가. 실패 시 삭제/삽입/번호 변경까지 롤백되는 기존 테스트도 통과.
- **문서:** 실행 가이드 12장에 사내 v6 코드 원본→수정본(버전, ID 두 곳, 테스트 SQL)과 새 DB 적재·조회 경로 안내. 11장의 과거 v5→v6 기록은 보존하고 현재 변경과 구분. 기존 사내 성공 기록은 v6 결과로 유지.
- **범위:** v7 Windows/사내 실제 입력 재실행은 아직 없음. 요청 범위의 로컬 구현이며 커밋·푸시는 수행하지 않음. 이전 문서의 사내 성공 상태 갱신 작업도 보존.

### TS-009 — 사내 DB에서 rules AUTOINCREMENT가 False로 확인됨

- **상태:** 사용자 보고에 따른 조사 중. 처음에는 rules AUTOINCREMENT=False만 보고됐고, 사용자가 이후 버전 7과 다른 항목 True를 확인했다고 추가 보고. rules 정의에 옵션이 없다는 점은 확인했지만 실제 DB 경로·수정한 소스/생성 순서는 제공되지 않아 원인을 단정하지 않음.
- **가능한 원인/확인:** ID 선언 두 곳 중 rules만 누락했는지, 수정 전에 생성한 파일을 계속 사용하는지, $SpdmDb가 다른 파일을 가리키는지 확인 필요. 원인을 단정하지 않음. Select-String으로 SCHEMA_VERSION과 id INTEGER PRIMARY KEY 선언 두 줄 확인 안내.
- **중요 동작:** 스키마 버전 숫자 변경이나 import 재실행은 기존 CREATE TABLE을 다시 만들지 않는다. 기존 파일의 헤더가 7이어도 rules 정의가 예전 상태로 생성됐다면 자동으로 변경되지 않는다.
- **대응 안내:** 수정한 파일을 저장한 뒤 아직 존재하지 않는 새 DB 파일명으로 같은 JSON 적재, 그 파일을 $SpdmDb로 지정해 actual DDL을 읽기 전용 확인. 기존 파일은 보존. 양쪽 AUTOINCREMENT True와 버전 7 확인이 완료 기준. 수정 후 사내 성공 결과는 대기 중.
- **검증 범위:** 문서 기록만 갱신하며 런타임 코드 변경/테스트 재실행이나 커밋·푸시는 수행하지 않음.

- **TS-009 후속 배포 안내:** 사용자가 직접 수정 대신 파일 다운로드 교체와 재적재 방법을 요청. ID 변경 자체는 sqlite_store.py에 있지만 새 테스트가 json_rules/verify_environment 등에 의존하므로 버전 혼합 방지를 위해 8개 파일 묶음을 제공. 교체용 ZIP의 파일 집합·바이트 일치 확인, 실제 입력/DB/보고서 제외. 기존 DB 보존 후 타임스탬프가 붙은 새 v7 DB에 동일 JSON 재적재하는 PowerShell 명령을 실행 가이드 13장에 추가. 사내 적용 성공은 아직 미확인. 런타임 변경이나 테스트 재실행 없이 배포 파일·문서만 갱신.

### v7 AUTOINCREMENT 및 교체 안내 게시

- 사용자가 현재 v7 변경의 커밋·푸시를 승인. feat/spdm-inspection에 두 ID AUTOINCREMENT·버전 7·내부 테이블 검사 수정·ID 비재사용 회귀 테스트와 사내 교체/재적재 안내를 함께 게시. 사내 v6 구조 검사/적재/선택 SEC 조회 성공 기록 및 TS-009의 실제 DB와 소스 DDL 불일치 조사 내용도 포함.
- 이번 게시 전 Linux/Python 3.12에서 테스트 25개를 새로 실행하여 통과. Windows CI 결과는 실행 완료 후 별도 추가. 실제 회사 입력·DB·보고서·ZIP은 Git에 포함하지 않고 가상 테스트만 사용. main 병합은 수행하지 않음.

- **게시/Windows 검증 완료:** 구현 3b2794044efa1a320d94562d42c87e249257c9e5를 feat/spdm-inspection에 일반 푸시. [run 38857144781](https://github.com/doukdoll/circuit-agent/actions/runs/38857144781)에서 Windows Server 2025/Python 3.12.10/SQLite 3.49.1, Windows PowerShell 5.1.26100.33438(job 116831064706)과 PowerShell 7.6.6(job 116831064823) 각각 테스트 25개와 명시적 가상 JSON CLI 환경 검증 전체 성공. 11체크포인트/35규칙/3SEC, null/error와 원문/타입 보존·모든 SEC 조회·최신 교체·외래키·반복 비누적·실패 시 DB 보존 확인. ID 비재사용 및 새 부모 연결 회귀 검증은 25개 테스트에 포함.
- **산출물/한계:** 두 CI 보고서는 output/spdm/v7-validation에 로컬 보관. 실행 가이드와 전체 ZIP의 가이드를 이 결과로 갱신하고 PR #2에 반영. 검증 후 런타임 코드는 변경하지 않았으며 문서만 갱신한 뒤 같은 테스트를 다시 실행한 것으로 기록하지 않음. 실제 회사 자료는 게시하지 않음. TS-009의 사내 v7 양쪽 AUTOINCREMENT 확인과 Windows 11/Python 3.15 환경 점검기 전체 재실행은 여전히 사용자 확인 대기.

### 2026-10-16 — 팀원용 v7 설치·실행 배포본

- **목표/범위:** 사용자가 팀원에게 설치 방법과 설치 파일을 전달하도록 요청. 기존 v7 런타임 8개 파일과 참조 SQL, 독립 실행 안내, 코드 기준 버전, 파일별 SHA-256 목록을 묶은 spdm-team-v7.zip을 로컬 산출물로 준비. 실제 JSON·DB·보고서·인증 정보와 Python 설치 프로그램은 포함하지 않음. 별도 서버/API/패키지 설치 없이 Python 표준 라이브러리로 실행.
- **안내 개선:** 다른 사람의 Python 설치 경로를 고정하지 않고 각 PC에서 실제 경로를 지정. 기존 설치를 덮어쓰지 않는 새 폴더, 환경 점검·JSON 검사·최초 DB 적재·실제 v7/양쪽 AUTOINCREMENT/외래키 확인·SEC 조회·최신 JSON 전체 교체·PowerShell 변수 복원 순서를 정리. 팀원별 실제 JSON은 사내에서 별도 준비.
- **사용자 환경 확인:** 사용자는 v7 교체·재적재 절차를 전체 완료했다고 보고. 구체적인 DDL/행 수 출력이나 환경 점검 보고서는 추가 제공되지 않았으므로 TS-009의 실제 양쪽 True 및 Python 3.15 점검기 전체 성공을 직접 확인한 것으로 처리하지 않음.
- **검증 계획/근거:** 런타임은 3b27940 그대로이며 이전 Windows CI run 38857144781의 양쪽 PowerShell/25개 성공을 재사용한다고 명시. 새 ZIP은 압축 해제 후 별도 표준 라이브러리 환경에서 가상 입력으로 전체 점검하고 결과를 추가 기록. 새 Windows 실행이나 사내 데이터 재실행으로 표현하지 않음. 현재 요청에는 새 문서의 커밋·푸시나 팀원에게 실제 메시지 발송을 포함하지 않음.
- **새 배포본 검증 결과:** 12개 파일의 ZIP을 한글/공백/# 경로에 추출하고 pip 없는 별도 venv의 Python 3.12.14에서 -S로 실행. 환경 점검기의 가상 테스트 25개와 가상 2체크포인트/3규칙/2SEC의 UTF-8 BOM JSON(null/error 포함) 왕복 전체 성공. 별도 최초 적재 imported 및 SEC 조회 MATCHED, 설명서의 Python DB 확인 코드로 버전 7/양쪽 AUTOINCREMENT=True/외래키를 확인. 파일별 SHA-256 및 런타임 8개 파일과 검증 커밋 3b27940의 바이트 일치 확인. environment.json은 output/spdm/team-v7-validation에 로컬 보관. 성공 후 설명서의 검증 결과만 갱신하며 런타임 재실행으로 표현하지 않음. 실제 파일은 사용하지 않음.

### TS-010 — 탐색기 압축 해제 위치와 기본 경로 불일치

- **증상/사용자 근거:** 팀원 PowerShell에서 USERPROFILE 아래 SpdmJson-Team-v7/app/spdm_json으로 이동하려고 했으나 경로 없음 오류. 후속 프롬프트는 실제 spdm-team-v7/app/spdm_json에서 실행 중인 것으로 확인.
- **원인/범위:** 안내가 가정한 폴더명과 실제 압축 해제 위치가 달랐음. Join-Path는 문자열 생성이며 New-Item으로 local-output을 만들어도 코드가 설치되지는 않음. JSON이나 Python 실행 전 경로 설정 단계 문제.
- **대응:** import_rules.py가 보이는 실제 폴더 주소를 탐색기에서 복사해 SpdmApp으로 지정하고 파일 존재 확인 후 Root/Output을 파생하도록 팀 안내 2장·재시작 안내를 보완. 압축을 재해제하거나 기존 DB를 삭제하지 않음.
- **확인/한계:** 후속 사용자 로그로 코드 폴더에 이동한 사실만 확인. 런타임 변경·새 테스트·Windows 직접 실행·커밋/푸시는 수행하지 않음.

### TS-011 — Read-Host의 안내문과 입력값 혼동

- **증상/사용자 근거:** 설치된 Python 3.12 경로를 py 출력으로 확인했지만 Read-Host 안내문 자리에 경로를 넣고 응답을 비운 뒤 Enter. Python/JSON 두 변수 모두 빈 문자열이 되어 Test-Path의 LiteralPath 바인딩 오류와 & 실행 오류 발생.
- **확인된 원인:** Read-Host 인수는 표시할 문구이며 반환값은 이후 입력한 응답. 실제 경로가 없다는 증거가 아니라 변수가 비어 있음이 원인. 사용자의 실제 계정/사내 파일 경로는 기록에서 제외.
- **대응/재발 방지:** 확인된 경로를 Read-Host 없이 문자열로 직접 대입하도록 안내. 이미 이동한 실제 코드 폴더에서 Root/Output도 재설정하여 TS-010에서 남은 잘못된 출력 경로 사용을 방지. 팀 안내에 프롬프트 입력 시점·직접 대입 대안·빈 문자열 사전 검사를 추가.
- **검증/상태:** 제공된 PowerShell 로그로 원인 확인. 명령 안내와 문서만 변경했으며 이 환경에는 PowerShell 실행기가 없어 해당 Windows 명령을 직접 재실행했다고 기록하지 않음. 사용자 PC의 수정 후 버전/SQLite 출력은 확인 대기. Python 런타임 8개 파일은 변경하지 않음.

### 2026-10-19 — Python 파일 선택으로 규칙 DB 생성·적재

- **요청/범위:** 사용자가 가능 여부 질문과 구현 요청을 구분하라고 명시한 뒤, 이번에 직접 구현을 요청. PowerShell 변수/명령 입력 대신 setup_rules.py에서 JSON과 DB 경로를 고르고 검사·적재·결과 확인까지 수행하는 실행기를 추가. 기존 파서/SQLite 스키마 v7/CLI는 변경하지 않음.
- **설계:** tkinter 파일 선택·메시지 창과 기존 import_rules.main을 연결. 신규 DB 생성, 기존 DB 전체 교체의 명시적 확인(기본 아니오), 취소, 오류 경로 표시, DB 옆 시각별 적재 보고서, 보고서 실패 후 이미 반영된 DB 상태 표시를 지원. 다른 버전 DB와 원본 경로 충돌은 기존 적재 코드가 거부. 서버/외부 API/추가 패키지 없음.
- **변경 파일/문서:** setup_rules.py, test_json_rules.py와 Python 실행 안내·기존 실행/팀 안내·목차·개발 가이드. 기존 팀 배포 관련 미커밋 문서 변경은 보존. spdm-python-v7.zip 및 팀 ZIP에 같은 런타임을 포함해 로컬 배포 준비. 실제 회사 JSON/DB/보고서는 포함하지 않음.
- **검증:** Linux/Python 3.12.14에서 `python -S -m unittest discover -s tools/spdm_import -p 'test_*.py' -v` 총 34개 성공. 기존 25개와 신규 9개 포함. 새 DB/UTF-8 BOM/null 보존·교체와 새 ID·양쪽 취소·교체 거부·잘못된 입력 시 기존 DB 불변·v6 보호·원본과 DB 경로 충돌·DB 반영 후 보고서 실패 표시를 확인. GUI 선택 창은 가짜 응답으로 대체하고 JSON/SQLite는 실제 실행.
- **한계/다음 확인:** 실제 Windows에서 새 tkinter 선택 창을 마우스로 조작하는 검증은 수행하지 않음. 과거 v7 Windows CI 25개 성공과 구분하며 새 ZIP 추출 실행 결과는 후속 기록. 현재 작업은 로컬 구현/배포 준비이며 새 커밋·푸시·메시지 발송은 수행하지 않음.
- **배포본 검증 완료:** spdm-python-v7.zip(13개 파일)을 별도 한글/공백/# 경로에 풀고 pip 없는 venv의 Python -S로 환경 점검 실행. 테스트 34개와 UTF-8 BOM/null/error가 포함된 가상 2체크포인트/3규칙/2SEC 저장·조회 전체 성공. 압축 해제 위치와 다른 현재 작업 폴더에서 실행기의 파일 선택 응답을 대체해 실제 새 DB 생성/건수/외래키/완료 메시지를 확인. 팀 ZIP(14개 파일)과 실행기 ZIP의 런타임 바이트 일치, 평평한 배포와 app/spdm_json 구조의 기본 출력 경로, 파일별 SHA-256을 확인. 보고서는 output/spdm/python-launcher-validation/environment.json에 로컬 보관. 핵심 저장 코드 7개 파일은 검증된 3b27940과 바이트 일치하며 setup_rules.py와 테스트만 추가/변경. 실제 회사 데이터와 GUI 클릭 검증은 포함하지 않음.

### 2026-10-19 — 사용자 제공 CSV+JSON / 14테이블 SQLite 방식으로 전환

- **권한/새 기준:** 사용자가 기존 방식을 기억으로 남기고 새 요청사항대로 코드를 바꾸라고 명시. 이전 JSON 전용·최신 교체·AUTOINCREMENT 정책을 새 DB에 암묵적으로 적용하지 않음. 기존 미커밋 코드/문서 변경을 보존한 채 현재 tools/spdm_import를 새 구현으로 전환하고 이전 디렉터리 전체를 tools/spdm_legacy_v7로 이동. 요구와 과거 검증은 SPDM_LEGACY_V7.md에 별도 기록.
- **구현:** 제공된 schema_sqlite.sql의 14개 테이블·인덱스·두 검증 결과 트리거, init_db.py, import_data.py, 읽기 전용 queries_sqlite.sql. setup_rules.py는 빈 DB만 생성하거나 실제 CSV+분석 JSON을 선택해 최초 적재. 연결마다 FK/JSON1/SQLite 최소 버전을 확인하며 새 DB 형식 식별/정의 검사를 추가. 기존 DB 자동 마이그레이션·증분 동기화·최신 교체는 하지 않음.
- **데이터 계약/보호:** UTF-8/BOM 원본 23컬럼 순서와 반복 헤더, 공유 부품 필드/관리번호/savefolder/정확한 SEC/전체 행 대응/원문 인용을 검사하고 BEGIN IMMEDIATE에서 전체 롤백. 제공된 importer와 동일하게 CSV 레코드를 헤더=1부터 세며 셀 내부 줄바꿈을 물리 줄 번호로 혼동하지 않도록 명시. 두 JSON 식별자가 해석 가능하면 같은 행인지 추가 검사.
- **보존 보완:** analysis:null도 CSV 행과 연결하고 최상위 error를 잃지 않도록 raw_analysis_json에는 분석 객체만이 아닌 입력 레코드 전체를 보존. 파라미터 문자열 공백·배열/객체를 보존하고 비유한 숫자 및 중복 JSON 키를 거부. archetype 누락은 other이며 자동 분류하지 않음. SQL의 ENUM 상당 CHECK·requirement_id 유일성·INTEGER PRIMARY KEY는 제공 정의 그대로 적용.
- **가상 데이터 금지:** 새 구현/배포에 가상 CSV·JSON·샘플 레코드 생성기·seed를 포함하지 않음. 새 테스트는 빈 스키마/메타데이터·취소/빈 DB GUI 흐름만 검사. 과거 가상 테스트는 보존 폴더에만 남기고 재실행하지 않음. Windows workflow도 합성 fixture를 제거하고 Python 3.10/3.12 및 두 PowerShell에서 빈 스키마 검사만 하도록 변경했으며 아직 게시/실행하지 않음.
- **새 검증:** Linux/Python 3.12의 `python -S -m unittest discover -s tools/spdm_import -p 'test_*.py' -v` 10개 통과. 14개 테이블/2개 트리거/전체 0행·생성 컬럼·FK·DDL 오류 롤백·기존/변조 DB 보호·읽기 SQL 6개·GUI 빈 DB 생성 확인. 이전 사용자가 제공한 실제 부분 JSON을 읽기 전용으로 파싱하여 10레코드/35규칙/58파라미터의 행 식별·값 파싱 확인. 새 입력을 만들어 성공으로 간주하지 않음.
- **한계/산출물:** 실제 원본 SPDM CSV가 없어 CSV+JSON 전체 적재·원문 인용 매칭/전체 데이터 롤백의 실제 입력 검증은 미수행. 새 실제 Windows GUI 클릭도 미확인. 현재 실행 안내·목차·기록을 갱신하며 새 배포 ZIP은 실제 파일/DB/보고서·과거 테스트를 제외해 준비. 기존 v7 Windows CI를 새 버전 성공으로 재사용하지 않음. 현재 요청 범위에서 커밋·푸시·외부 메시지 발송은 하지 않음.
- **배포본 확인:** circuit-review-sqlite.zip의 10개 허용 파일과 SHA-256을 확인하고 별도 한글/공백/# 경로의 pip 없는 venv에 추출해 Python -S로 검증. 테스트 코드는 검증 중에만 별도로 복사했으며 ZIP에는 포함하지 않음. 빈 스키마 테스트 10개와 패키지 CLI 초기화/재초기화 불변/실제 입력 미지정 시 DB 불변 확인. 14개 테이블 모두 0행, 두 트리거, integrity_check=ok. 기존 v7 핵심 7개 파일이 HEAD의 원본과 바이트 일치하고 미커밋 GUI 테스트도 보존되었음을 확인. 실제 부분 JSON의 읽기 전용 검사 외에 가상 CSV/JSON이나 업무 레코드를 생성하지 않음. 결과는 output/spdm/circuit-review-validation/blank-schema-check.json에 로컬 보관.

### 2026-10-19 — 새 브랜치에 Circuit Review 배포 ZIP 게시

- **요청/브랜치:** 사용자가 새 배포 ZIP을 브랜치를 만들어 게시하도록 명시. 최신 origin/main(b1b2585)을 기준으로 feat/circuit-review-sqlite와 별도 작업 트리를 생성. 기존 feat/spdm-inspection 작업 트리의 미커밋 변경을 보존하고 새 구현·관련 문서·v7 보존 코드를 복사하여 게시 준비. main 직접 수정/병합이나 강제 푸시는 하지 않음.
- **게시 범위:** 현재 14테이블 소스·빈 스키마 테스트·Windows 빈 스키마 CI, 실행/보존 기록, dist/circuit-review-sqlite.zip과 외부 체크섬 및 다운로드 안내. ZIP 내부 10개 파일을 허용 목록/체크섬으로 검토하여 실제 CSV·분석 JSON·DB·보고서가 없음을 확인. 과거 테스트는 보존 코드에만 있으며 새 배포 ZIP에는 포함하지 않음.
- **검증/진행:** 게시할 작업 트리에서 새 빈 스키마 검사와 패키지 무결성을 확인. Windows Python 3.10/3.12와 PowerShell 5.1/7의 CI는 PR 게시 후 결과를 별도 기록. 실제 SPDM CSV가 없어 전체 CSV+JSON 적재는 계속 미검증이며 새 Windows GUI 클릭 성공으로 표현하지 않음.
- **게시 완료/실제 Windows 근거:** 커밋 37f7b2afde565db6e4887cbbf0ecee4ccab60267을 feat/circuit-review-sqlite에 일반 푸시하고 main 대상 [PR #3](https://github.com/doukdoll/circuit-agent/pull/3)을 생성. [run 39188935104](https://github.com/doukdoll/circuit-agent/actions/runs/39188935104)에서 Windows Server 2025, Python 3.10.11/SQLite 3.40.1과 Python 3.12.10/SQLite 3.49.1 각각 PowerShell 5.1.26100.33438/7.6.6 네 조합 성공. 작업 117857225592(pwsh/3.12), 117857225839(powershell/3.12), 117857225855(powershell/3.10), 117857225897(pwsh/3.10) 모두 테스트 10개 및 14테이블 빈 DB CLI 초기화 통과.
- **후속 기록/범위:** CI 근거를 현재 안내·배포 README에 반영하고 ZIP의 문서/버전/체크섬을 갱신. 테스트한 Python/SQL 코드는 그대로이며 문서 갱신을 새 코드 테스트로 표현하지 않음. 각 작업의 최소 검증 보고서는 해당 작업 트리 output/spdm/circuit-review-validation에 로컬 보관하고 Git에 포함하지 않음. 전체 실데이터 적재와 실제 GUI 클릭은 여전히 미검증이며 main 병합은 하지 않음.

### TS-012 — CSV 31번 레코드의 부품 공통 필드 불일치

- **사용자 증상:** 새 배포본의 실제 입력에서 `CSV row 31: Inconsistent shared fields for part` 및 전체 적재 취소 메시지 발생. 사용자가 제공한 오류 로그를 근거로 하며 실제 CSV는 전달되지 않음.
- **확인된 검사:** 제공받은 importer와 현재 코드 모두 A adminno + B seqno를 부품 그룹으로 묶고, C sec_code/D writer/E comp_date/F maker/G maker_pn/S~W LDRC 5개 필드가 같은 그룹의 앞선 레코드와 원문 그대로 같은지 검사. 규칙 레벨 I seqno가 아닌 B seqno를 사용. CSV row는 헤더=1인 레코드 번호이며 셀 내부 줄바꿈을 세는 물리 줄 번호가 아님.
- **원인/미확정:** 같은 그룹에서 위 10개 값 중 하나 이상이 달랐다는 점까지 코드와 로그로 확인. 어떤 컬럼인지, 실제 값 차이인지, 빈값/공백/날짜 표기 차이인지, LDRC를 부품 공통으로 보는 가정이 맞지 않는지는 원본 없이 단정하지 않음. 행별 LDRC가 실제로 다르면 원본 오류가 아니라 저장 수준 설계 문제일 수 있음.
- **대응/상태:** 먼저 동일 그룹의 최초 레코드와 31번 레코드의 해당 컬럼을 로컬에서 비교하도록 안내. 검사 삭제·첫 값 강제 선택·원본 정규화·부품 키 변경을 하지 않음. 이 지점은 CSV 적재 단계이며 JSON 근거 대조 전에 중단. 트랜잭션은 롤백되므로 새 DB는 빈 스키마로 재사용 가능하나 실제 DB 행 수는 별도 확인 필요.
- **검증 범위:** 현재 소스 읽기와 사용자 로그 분석만 수행. 새 데이터/가상 fixture를 생성하지 않았으며 코드 수정·테스트 재실행·ZIP 교체·커밋/푸시는 하지 않음.

- **2026-10-20 추가 확인:** 사용자가 CSV를 표로 붙여 제공. 보이는 23개 데이터 레코드는 부품 그룹별로 표시된 공통 값의 차이가 드러나지 않으며 에러의 31번 레코드까지 식별할 자료는 없음. 표 표시의 과학적 표기·선행 0 생략이 원본 CSV에도 반영됐는지 확인되지 않았으므로 현재 shared-fields 오류의 확정 원인으로 단정하지 않음. 실제 값이 달라도 표시가 반올림되어 같아 보일 수 있음. 원문 및 개인/부품 식별자는 기록에 복제하지 않음.

### 2026-10-20 — 서버 시작 시 SQLite 연결 구조 검토

- **질문/검토:** 사용자가 DB 파일 미존재 시 생성하고 기존 파일이면 데이터를 보존해 연결하는 서버 시작 흐름의 구현 가능 여부를 질문. 실행 흐름 제안만 하며 구현 요청으로 취급하지 않음.
- **설계 설명:** SQLite는 별도 DB 서버 없이 Python 서버에서 연결 가능. 파일 존재 검사는 connect 전에 하거나 연결 후 실제 스키마로 준비 상태를 판단해야 함. 기본 sqlite3.connect는 파일이 없으면 먼저 생성하므로 연결 뒤 파일 존재만 확인하면 신규 파일 구분이 안 됨. 파일 생성과 테이블/원본 데이터 적재는 별도 작업이며 기존 정상 DB는 데이터 보존 후 연결/조회.
- **현재 코드와 차이:** initialize_database는 최초 적재용 빈 DB 도구여서 기존 데이터가 있으면 거부함. 서버 시작 경로는 신규 DB에만 초기화를 적용하고 기존 DB는 connect_database/validate_schema로 연결하도록 분리해야 함. import_files를 서버 재시작마다 호출하지 않으며 기존 스키마를 이 동작만을 위해 바꿀 필요는 없음. 안정된 DB 경로와 연결별 FK 설정은 유지.
- **상태:** 실제 CSV 31번 원인 특정과 서버 연동 구현은 미수행. 문서 기록만 갱신하며 데이터 생성·DB 변경·테스트 실행·커밋/푸시를 하지 않음.

### 2026-10-20 — 공통 필드 비교·진단 수정 및 Python 파일 정리

- **요청/범위:** 사용자가 수정을 진행하고 불필요한 Python 파일을 정리하도록 명시. 기존 TS-012/설계 검토의 미커밋 문서 변경을 보존하고, 현재 feat/circuit-review-sqlite 작업 트리에서 비교 로직과 배포본을 수정. 서버 시작 연동은 이번 구현 범위에 추가하지 않음.
- **비교 보완:** 선택 공통 컬럼의 빈 문자열/공백만 있는 문자열을 미제공으로 비교하고 첫 부품 INSERT의 해당 선택 필드에도 NULL을 일관되게 사용. 작성일/확인일은 유한 Decimal의 정확한 수치로 동등성만 비교. SEC·사번·비어 있지 않은 메이커/부품번호 등은 앞뒤 공백·대소문자를 포함해 그대로 비교. 원본 CSV와 각 raw_row_json은 수정하지 않으며 날짜를 float로 반올림하지 않음.
- **진단 보완:** 그룹의 최초 레코드 번호와 최초 원문 공통 값을 보관하고, 실제 불일치가 나면 최초/현재 CSV 레코드 번호·컬럼 문자/이름·이전/현재 값의 repr을 오류 창/CLI에 표시. 긴 값은 메시지 표시만 제한. 전체 롤백과 A adminno+B seqno 그룹 키는 유지. 실제 31번 값이 없으므로 LDRC를 체크포인트로 이동하거나 참값 충돌을 무시하지 않음.
- **정리:** 실행 폴더는 setup_rules.py/import_data.py/init_db.py/db_common.py 네 개만 유지. test_schema.py는 tests/test_spdm_schema.py로 옮기고 리소스 경로·CI 검색 경로를 갱신. 과거 v7 Python 파일 8개와 사용하지 않는 계약 JSON은 현재 트리에서 제거하고 README/보존 문서에 커밋 118e3cd의 불변 원본 링크를 남김. 이전 요구사항은 삭제하지 않음.
- **검증:** `python -S -m unittest discover -s tests -p 'test_spdm_schema.py' -v` 15개 통과. 기존 빈 스키마 10개와 스칼라 비교 5개로 동등 날짜/정밀한 날짜 차이/선택 빈값/원문 식별자 비교/레코드·컬럼·공백 표현을 확인. 합성 CSV·분석 JSON·업무 레코드는 생성하지 않았고 SQL 정의·DB 형식도 변경하지 않음. 현재 수정의 실제 Windows 실행과 실제 CSV 31번 적재 성공은 아직 확인하지 않음.
- **배포/상태:** 현재 실행 안내와 보존 기록을 갱신하고 동일 네 실행 파일로 ZIP을 재구성. 원본 CSV/기존 DB를 삭제할 필요가 없으며 실패 뒤 빈 DB를 재사용할 수 있음. 현재 작업에서는 커밋·푸시·PR 생성/재오픈을 수행하지 않음.
- **분리된 배포본 확인:** 수정 ZIP의 파일별 SHA-256과 네 Python 파일 허용 목록을 확인한 뒤 한글/공백/# 경로의 별도 pip 없는 venv에 압축 해제. 이동한 tests 경로와 CIRCUIT_REVIEW_APP_DIR로 패키지 코드를 대상으로 동일 15개 검사 통과 및 CLI 빈 DB 생성/14테이블 0행을 확인. Python 3.10 문법과 기존 HEAD 대비 SQL 정의 무변경도 확인. CSV/JSON/업무 레코드는 생성하지 않음. 검증 보고서는 output/spdm/shared-fields-validation/checks.json에 로컬 보관.

### 2026-10-20 — 공통 필드 수정 및 정리한 배포본 게시

- **게시 승인/대상:** 사용자가 이번 수정의 Git 푸시까지 명시적으로 요청. 기존 feat/circuit-review-sqlite 브랜치에 비교·진단 수정, 테스트 이동, 과거 실행 파일 정리, 관련 문서와 갱신 ZIP만 커밋해 일반 푸시하는 범위. 닫힌 PR #3은 다시 열지 않고 새 PR 생성·main 병합·강제 푸시도 하지 않음.
- **검증 근거:** 직전 구현과 분리된 ZIP에서 완료한 Linux 검사 15개 및 패키지 검사 결과를 재사용. 게시 준비 중 변경한 것은 배포 안내·버전 표기·기록이며 Python/SQL은 재검증된 상태 그대로 유지. 실제 CSV/분석 JSON·DB·로컬 보고서와 회사 식별자는 게시하지 않음.
- **게시 전 확인/한계:** 원격 브랜치와 기준 118e3cd가 같은 상태임을 확인. ZIP의 파일별/전체 체크섬과 코드 일치·허용 파일 목록을 다시 확인하고 게시함. 새 Windows 실행과 실제 원본 31번 적재 성공은 여전히 미확인이며 이전 Windows CI 결과를 이번 수정의 결과로 표현하지 않음.

### TS-012 후속 — 실제로 다른 LDRC 등록 정보 확인

- **사용자 근거:** 수정 배포본 01322a6 사용 후 상세 오류에 최초 CSV 레코드 30/현재 31과 T열 ldrc_regist_tp, W열 ldrc_id의 차이가 표시됨. 회사 원본 값은 이 기록에 복제하지 않음. 새 진단이 적용된 사실과 서로 다른 등록 상태·ID 유무가 중단 원인이라는 점을 사용자 로그로 확인.
- **확인된 원인:** 현재 A adminno+B seqno 그룹의 LDRC 5개 컬럼을 parts의 공통 값으로 저장하는 구조에서 위 두 컬럼이 같아야 한다는 검사가 실패함. 빈값끼리의 표기 차이나 날짜 동등성 문제가 아니므로 직전 비교 보완으로 통과시킬 대상이 아님. 실제 원본 전체를 받지 않아 어느 행이 업무적으로 잘못됐는지는 판단하지 않음.
- **권고/구현 구분:** 원본이 체크포인트별 LDRC 상태를 표현한 것이라면 해당 정보를 checkpoints에 행별로 보존하고 부품 공통 필드 비교에서 제외하도록 SQL과 importer를 함께 변경하는 방안을 권고. 원본 CSV 값을 임의로 통일하거나 검사만 삭제하면 첫 행의 상태가 부품 전체를 대표하여 다른 행의 구조화된 값이 사라질 수 있음. 5개 LDRC 정보의 저장 단위도 함께 검토하되 실제로 모두 달랐다고 단정하지 않음.
- **상태/검증:** 이번 요청은 오류 보고이므로 원인 분석과 기록만 수행. 런타임·SQL·ZIP·DB 수정, 테스트 재실행, 커밋·푸시는 하지 않음. 전체 적재는 롤백되는 경로이며 실제 사내 DB 행 수는 직접 확인하지 않음.

### 2026-10-20 — LDRC 정보를 체크포인트별로 저장하도록 수정

- **요청/권한:** 사용자가 TS-012 상세 원인을 확인한 뒤 코드 수정과 푸시를 명시적으로 요청. 기존 feat/circuit-review-sqlite와 앞선 미커밋 원인 분석 기록을 유지. 닫힌 PR #3은 다시 열지 않고 새 PR 생성·main 병합·강제 푸시도 하지 않음.
- **확인된 문제/변경:** 같은 부품 그룹의 서로 다른 체크포인트에서 LDRC 등록 상태/ID가 다른 실제 로그를 근거로, LDRC 5개 정보를 부품 공통 속성으로 저장하던 가정을 수정. S~W열을 parts에서 checkpoints로 이동하고 INSERT 바인딩도 각 원본 CSV 레코드의 5개 값을 사용하도록 변경. 공통 필드 비교는 C~G열에만 적용. 검사만 제거하거나 첫 행 값으로 통일하지 않음.
- **유지한 정책:** 원본 CSV/raw_row_json, SEC의 원문 일치, A adminno+B seqno 부품 그룹 키, SQL 허용 값/외래키, 전체 입력 대응/근거 인용 검사, 최초 전체 적재와 오류 시 전체 롤백은 유지. 선택 LDRC의 빈값은 NULL, 나머지 문자열은 날짜를 포함해 원문 보존. 나머지 테이블과 검증 결과 트리거의 역할은 변경하지 않음.
- **버전/전환:** 구조 변경을 구분해 Circuit Review SCHEMA_VERSION을 1→2로 올림. 이전 형식 DB는 빈 DB도 자동 변환하거나 덮어쓰지 않음. GUI 기본 파일명을 circuit_review_v2.db로 변경하고 전체 ZIP을 새 폴더에 풀어 실제 CSV+JSON을 새 파일에 재적재하는 순서/조회 SQL을 실행 안내 9장에 추가. 이는 이전 JSON 전용 v7과 별도의 형식 번호임.
- **검증:** Linux/Python 3.12에서 `python -S -m unittest discover -s tests -p 'test_spdm_schema.py' -v` 총 18개 통과. LDRC 5개 컬럼의 checkpoints 소유, 형식 버전 2, 이전 버전 DB 보호, 실제 importer의 9개 INSERT/UPDATE SQL을 새 스키마에서 EXPLAIN으로 컴파일 확인. 기존 빈 스키마/FK/트리거/DDL 롤백/읽기 쿼리/스칼라 비교 검사도 통과. 합성 CSV/JSON·업무 레코드는 생성하지 않음.
- **배포본 확인:** 코드·SQL·문서·VERSION·체크섬의 10개 파일로 ZIP 갱신. 한글/공백/# 경로의 pip 없는 venv에 풀어 패키지 코드로 동일 18개 검사, CLI 버전 2/14테이블 0행, 파일별 체크섬/소스 바이트 일치, Python 3.10 문법을 확인. 이전 커밋의 실제 버전 1 SQL로 만든 빈 DB를 새 CLI가 거부하고 바이트를 유지하는 것도 별도 확인. 로컬 근거는 output/spdm/ldrc-checkpoint-validation/checks.json이며 게시하지 않음.
- **한계/게시 범위:** 실제 사내 CSV+JSON 전체 파일은 없어 해당 입력의 전체 적재 성공은 사용자 환경 확인 대기. 이번 수정의 Windows 실행/GUI 클릭 성공으로 표현하지 않으며 과거 Windows CI를 재사용하지 않음. 회사 원본 값·식별자·DB·보고서를 제외하고 수정 코드·회귀 검사·문서·ZIP만 현재 브랜치에 일반 푸시하는 범위.

### TS-013 — CSV 481번 레코드의 savefolder 불일치

- **사용자 증상:** LDRC 수정본 안내 후 실제 적재에서 `CSV row 481: savefolder mismatch`를 보고. 실제 481번 레코드의 I열/O열 값이나 전체 입력 파일은 제공되지 않음.
- **확인된 검사/원인 범위:** importer는 오른쪽 I열 규칙 seqno를 정수로 읽고 O열 savefolder가 그 정수의 10진 문자열+L과 정확히 같은지 검사함. 현재 SQL의 checkpoints.savefolder 역시 checkpoint_seqno로부터 생성하는 STORED 컬럼. 따라서 두 값이 현재 식과 다르다는 점은 확인되지만 공백/다른 표기/실제 별도 폴더값 중 무엇인지는 미확정. B열 부품 그룹 seqno와 혼동하지 않음.
- **추가 확인/대안:** 해당 CSV 레코드의 I열 원문과 O열 원문을 확인해야 함. 단순 표기 차이라면 허용 범위를 정의하고 원문 보존을 유지하며 처리할 수 있음. savefolder가 실제로 독립적인 원본 값이라면 generated 컬럼을 일반 TEXT로 바꾸고 importer에서 각 행의 원문을 저장하는 방안을 검토. 검사만 지우면 구조화 컬럼은 계속 자동 생성되어 원본과 다른 값이 저장될 수 있으므로 무조건 우회하지 않음.
- **상태/검증:** 원인 분석과 기록만 수행. 새 런타임·SQL·ZIP·DB 변경이나 테스트 재실행, 커밋·푸시는 하지 않음. 적재는 전체 롤백 경로이며 앞선 레코드가 DB에 부분 저장됐다는 뜻이 아님. 실제 사내 DB 상태와 전체 적재 성공은 직접 확인하지 않음.

- **실제 두 값 확인:** 사용자가 I열 규칙 번호와 O열 폴더값을 추가 제공했으며, 폴더의 숫자 부분이 규칙 번호와 다름을 확인. 단순 공백/동일 숫자 표기 문제가 아니고 현재의 seqno+L 가정에 맞지 않는 실제 값 조합임. 다만 어느 원본 값이 업무적으로 잘못됐는지, 폴더가 별도 규칙으로 부여되는지는 이 한 쌍만으로 확정하지 않음. 원본을 유지해 적재하려면 규칙 번호는 그대로 두고 savefolder를 원본 TEXT로 저장하도록 SQL/importer를 함께 바꾸는 방안을 설명. 이번 후속도 설명·기록만이며 코드는 수정하지 않음.

### 2026-10-20 — savefolder의 원본 저장 및 강제 일치 검사 제거

- **요청/권한:** 사용자가 두 seqno와 savefolder의 의미를 확인한 뒤 오류 수정·커밋·푸시를 명시적으로 요청. 기존 feat/circuit-review-sqlite와 TS-013의 미커밋 원인 분석 기록을 보존. 닫힌 PR #3은 재오픈하지 않고 새 PR 생성·main 병합·강제 푸시도 하지 않음.
- **원인/최종 변경:** 실제 CSV에서 규칙 번호와 폴더값의 숫자가 다를 수 있는데 기존 코드와 generated 컬럼이 seqno+L을 강제했음. savefolder를 일반 TEXT 컬럼으로 바꾸고 importer의 일치 검사를 제거한 뒤 O열 원문을 INSERT에 직접 바인딩. 규칙 seqno는 그대로 유지하고 빈 문자열/공백도 원문대로 보존. 원본 값의 업무상 옳고 그름이나 폴더의 실제 용도는 추정하지 않음.
- **유지 범위:** LDRC의 체크포인트별 저장, A adminno+B seqno 부품 키, C~G 공통 값 검사, SEC 원문 일치, 전체 CSV+JSON 대응/근거 인용, SQL/FK 제약 및 오류 시 전체 롤백 유지. 원본 CSV/raw_row_json을 변경하거나 번호를 폴더값에 맞춰 재작성하지 않음. SEC 조회 SQL에 checkpoint_seqno/savefolder를 추가해 각 원본 값을 조회할 수 있도록 함.
- **전환/설명서:** DB 구조 변경에 따라 형식 버전 2→3, GUI 기본 파일명 circuit_review_v3.db로 변경. 이전 형식 1/2의 빈 DB도 자동 변환하지 않고 새 파일에 원본 CSV+JSON을 재적재. 실행 안내 9장의 교체 순서와 PRAGMA user_version/해당 레코드 조회 SQL, 개발 가이드·배포 README·목차를 함께 갱신.
- **검증:** Linux/Python 3.12에서 `python -S -m unittest discover -s tests -p 'test_spdm_schema.py' -v` 18개 통과. savefolder가 generated가 아닌 일반 TEXT인지, 형식 버전 3/LDRC 위치/이전 형식 1·2 거부, 실제 importer 9개 INSERT/UPDATE의 EXPLAIN 컴파일, 기존 빈 스키마/SQL/롤백/스칼라 검사를 확인. 합성 CSV/JSON·업무 레코드는 생성하지 않음.
- **배포본 검증:** 10개 허용 파일·네 Python 실행 파일로 ZIP 갱신. 한글/공백/# 경로의 pip 없는 venv에 풀어 패키지 코드로 같은 18개 검사와 CLI 버전 3/14테이블 0행·savefolder 일반 TEXT를 확인. 파일별 체크섬/소스 바이트 일치와 Python 3.10 문법도 확인. 실제 과거 커밋의 버전 1/2 SQL로 만든 빈 DB가 새 CLI에서 거부되고 바이트가 유지됨을 별도 검증. 로컬 근거는 output/spdm/savefolder-validation/checks.json이며 게시하지 않음.
- **한계/게시 범위:** 원문 seqno/savefolder 관계를 강제하던 코드와 저장 구조를 수정한 것이며 실제 사내 전체 CSV+JSON 적재 성공이나 이번 수정의 Windows 실행은 아직 미확인. 과거 Windows CI 결과를 새 검증으로 재사용하지 않음. 회사 데이터·DB·보고서를 제외한 코드·검사·문서·배포 ZIP만 현재 브랜치에 일반 푸시하는 범위.
