# Java QCV 검사 데모 개발 가이드

공개 샘플을 읽어 부품·핀·넷을 구성하고, TPS56C230의 명목 FB 분압 Rule 하나를 계산한 뒤 JSON·HTML 보고서를 만듭니다. [최신 MVP 방향](MVP_REQUIREMENTS.md)을 위한 실행 가능한 출발점입니다. [샘플 안내](../samples/README.md)에 원본·직접 작성한 회로·기대 결과·개발용 허용 기준을 구분했습니다.

## 준비와 빌드

전체 JDK 21과 Maven 3.9 이상을 설치하고 저장소 루트에서 실행합니다. 최초 빌드는 Maven Central 연결이 필요합니다. 프록시 환경에서는 개인 Maven `settings.xml`에 해당 환경의 프록시를 설정하세요.

```bash
java -version
mvn -version
mvn clean package
```

JUnit 테스트도 함께 실행되고, 의존성을 포함한 `target/circuit-audit-demo.jar`가 생성됩니다. 보고서와 빌드 결과가 저장되는 `output/`·`target/`은 Git에서 제외됩니다.

## 공개 원본 파싱

```bash
java -jar target/circuit-audit-demo.jar \
  --qcv samples/qcv/ansys-pyaedt/Schematic1.qcv \
  --inspect --output output/public-qcv
```

`graph.json`에서 부품 11개·넷 6개·경고 3개와 원본 위치를 확인합니다. `--inspect`는 엔지니어링 Rule을 실행하지 않습니다.

## Windows에서 줄바꿈 때문에 테스트가 실패할 때

저장소의 `.gitattributes`는 소스와 작성한 테스트 파일을 LF로 유지하고, 해시가 고정된 공개 QCV 원본·라이선스에는 Git의 줄바꿈 변환을 적용하지 않습니다. 파서와 저항값 검증 테스트는 LF·CRLF 입력 모두를 검증합니다. 원본 해시 검사는 바이트 단위 비교를 유지합니다.

이 설정이 추가되기 전에 Windows에서 받은 파일은 CRLF로 남아 있을 수 있습니다. 공개 QCV의 기대 해시가 `4a2bd1...`인데 실제 해시가 `2aa5b6...`이고, `unsafeLowerValueRequiresReview`도 문자열 변경 실패로 보고되면 줄바꿈 변환에 해당합니다.

**아래 샘플을 직접 수정하지 않았다면**, 저장소 루트의 PowerShell에서 세 파일을 Git 원본으로 복원한 후 빌드합니다. 세 샘플의 작업 사본은 이 명령으로 교체됩니다.

```powershell
git -c core.autocrlf=false restore --source=HEAD --worktree -- samples/qcv/ansys-pyaedt/Schematic1.qcv samples/qcv/ansys-pyaedt/LICENSE samples/ti/tps56c230/cases/normal.qcv
mvn clean package
```

이 명령은 커밋·푸시하거나 전역 Git 설정을 변경하지 않습니다. 샘플 내용 자체를 변경했거나 다른 오류가 있다면 해당 변경·오류를 먼저 확인하세요.

## 정상·위반·사람 검토 사례

```bash
java -jar target/circuit-audit-demo.jar \
  --qcv samples/ti/tps56c230/cases/normal.qcv \
  --rule samples/ti/tps56c230/rule.json --output output/normal

java -jar target/circuit-audit-demo.jar \
  --qcv samples/ti/tps56c230/cases/violation.qcv \
  --rule samples/ti/tps56c230/rule.json --output output/violation

java -jar target/circuit-audit-demo.jar \
  --qcv samples/ti/tps56c230/cases/missing-value.qcv \
  --rule samples/ti/tps56c230/rule.json --output output/review
```

각 출력 디렉토리의 `report.html`을 브라우저로 열고, `audit.json`을 코드에서 사용할 수 있습니다. 정상은 PASS/1.2V, 위반은 FAIL/1.32V, 누락은 NEEDS_REVIEW입니다. 위반·보류 종료 코드는 예상된 결과이며 아래 표를 참고하세요.

```bash
java -jar target/circuit-audit-demo.jar \
  --qcv samples/ti/tps56c230/cases/dni.qcv \
  --rule samples/ti/tps56c230/rule.json --output output/dni \
  --dni-property DNI --dni-value yes
```

DNI 필드·값을 명시했을 때만 검사 모델에서 R99를 제외합니다. 원본은 보존하고 제외 대상·이유·위치를 기록합니다. 두 옵션을 생략하면 R99가 남아 연결 모호성으로 보류됩니다. 실제 회사 DNI 필드와 제외 단위가 확인되면 정책을 맞춰야 합니다.

| 종료 코드 | 의미 |
| --- | --- |
| 0 | 파싱 모드 성공 또는 현재 Rule의 자동 판정 완료 및 FAIL 없음 |
| 1 | FAIL 존재, 보류·파싱 오류 없음 |
| 2 | 입력·파싱·참조·파일 입출력 오류 |
| 3 | 사람 검토 존재 또는 적용 대상 없음 |

오류와 보류가 함께 있으면 2, FAIL과 보류가 함께 있으면 3을 반환합니다. 상세 판정은 JSON을 확인하세요. 사용법은 `--help`로 볼 수 있습니다.

## 패키지와 호출 흐름

기존에 제안한 회로·Rule·검사·결과 경계를 유지하면서 실행에 필요한 부분부터 구현했습니다.

```text
com.ssafy.circuitaudit
├── AuditDemo                 CLI 옵션 및 파일 출력
├── file.netlist              QcvParser, DniPolicy
├── circuit
│   ├── component / net / connection   부품·넷·핀 모델
│   ├── graph                 파싱 모델·진단·제외 기록
│   ├── index                 연결 부품·두 넷 사이 부품 조회
│   └── source                원본 줄·블록 위치
├── rule
│   ├── domain                Rule 입력·단위 해석·실행 문맥
│   ├── engine                전체 대상 열거 및 handler 선택
│   └── handler               명목 분압 계산
├── audit
│   ├── domain                실행 메타데이터와 집계
│   └── service               파싱 → 검사 → 집계
└── result
    ├── domain                판정·근거·계산 결과
    └── report                독립 HTML 보고서
```

`file.netlist`는 입력 책임, `circuit`은 공통 회로 모델의 책임입니다. QCV 외의 넷리스트를 추가하면 별도 파서에서 같은 회로 모델로 변환하면 됩니다. 웹 연동 시 `AuditExecutor`를 서비스에서 호출할 수 있습니다. 현재 project/controller/repository 계층은 생성하지 않았으며 저장 기능과 웹 인터페이스는 후속 구현 대상입니다.

입력 바이트 한 번을 파싱과 SHA-256 계산에 함께 사용합니다. 전체 파일의 연결 참조를 해결하고 명시된 DNI를 적용한 뒤, `targetModel`과 정확히 일치하는 **모든** 인스턴스를 먼저 열거합니다. 인덱스로 관련 저항을 찾아 등록된 계산 코드로 판정합니다. LLM·벡터 DB가 없어도 재현할 수 있는 기본 검사입니다.

## 지원 문법과 판정 조건

현재 파서는 공개 PyAEDT 샘플에서 확인한 UTF-8 문법을 지원합니다.

```text
NET : 'FB' U1-14 R4-2 R6-1
COMP: 'R0603' 'R4'
Property: Value=10.0k
  Explicit Pin: '2' '2' 'FB'
```

- NET의 `부품ID-핀번호`는 마지막 `-`에서 구분합니다. NET과 COMP의 파일 내 순서는 달라도 됩니다.
- COMP는 `'모델' '부품ID'` 또는 심볼·계층 경로를 추가한 네 필드 형식을 지원합니다.
- Property는 키·값을 보존합니다. Explicit Pin의 핀번호와 넷을 대조합니다. 별칭은 현재 연결 모델에 저장하지 않습니다.
- 빈 줄과 `#` 주석은 건너뜁니다. 지원하지 않는 줄, 중복 부품·속성·명시 핀, 참조 누락·충돌은 오류로 기록합니다.
- 핀이 없는 부품은 경고로 남깁니다. 파싱 오류가 있으면 적용 대상 전부를 NEEDS_REVIEW로 보내고 실행 상태를 FAILED로 기록합니다.
- 모든 QCV 변형·이스케이프·멀티라인 속성을 지원하는 일반 파서는 아닙니다. 실제 도구 출력과 대조하여 확장해야 합니다.

현재 handler는 `FB_DIVIDER_NOMINAL` 하나입니다. `rule.json`은 ID/버전/type, 대상 모델·FB/접지 핀, 출력/접지 넷, 기준/목표 전압, 허용 오차, 범위, 기준 출처와 문서 근거를 요구합니다. 기존 회사 Rule 스키마와의 어댑터는 별도로 필요합니다.

저항은 `R숫자` ID와 `R0603` 같은 `R`+네 숫자 또는 `RESISTOR` 모델을 가진 두 핀 부품만 인식합니다. FB↔출력과 FB↔접지 사이에 각각 저항 하나가 있어야 하며, FB 넷은 대상 핀·상단 저항 핀·하단 저항 핀만 포함해야 합니다. 다른 모델·추가 분기·값 누락·단위 오류·0Ω 하단 저항은 보류합니다. `10k`, `1MΩ`, `1m`, `0,1uF` 등 일부 SI 표기를 지원하며 `4K7`·부품 공차 포함 표기 등은 임의 해석하지 않습니다.

`PASS / FAIL / NEEDS_REVIEW / NOT_APPLICABLE` 판정 타입이 있습니다. 현재 Rule의 적용 대상만 열거하므로 NOT_APPLICABLE 결과는 생성하지 않습니다. 대상 없음은 PASS 0개와 종료 코드 3으로 표현합니다. 자동 판정 완료 수는 PASS+FAIL이며 경고·보류·제외는 PASS에 합산하지 않습니다.

## 검증과 후속 작업

`mvn test`는 공개 원본의 해시·부품·핀·넷·위치, 단위 변환, 참조 오류, 명시적 DNI, 여섯 기대 시나리오, 경계 오차, 모든 대상 열거, CLI 결과·종료 코드·HTML 이스케이프를 확인합니다. 샘플이 작으므로 이 결과로 만 줄 이상 실제 QCV의 성능이나 검사 정확도를 주장하지 않습니다.

2026-10-10 검증에서는 테스트 33개와 실행 JAR의 여섯 검사 사례·공개 원본 파싱이 통과했습니다. 사용한 관리 환경의 Java 21 런타임에는 `ct.sym`이 없어, 해당 환경에서만 Maven에 `-Dmaven.compiler.release= -Dmaven.compiler.source=21 -Dmaven.compiler.target=21`을 지정했습니다. 일반적인 전체 JDK 21에서는 위의 기본 빌드 명령을 사용합니다.

같은 날 줄바꿈 회귀 검증을 추가한 후 테스트 38개가 통과했습니다. Linux 환경에서 `core.autocrlf=true` 체크아웃 시 공개 원본의 바이트 보존과 작성한 파일의 LF 유지를 확인했고, 작성한 QCV 샘플을 CRLF로 바꾼 별도 작업 사본에서도 38개 테스트와 패키징이 통과했습니다. Windows 운영체제 자체에서 실행한 결과는 아닙니다.

다음 단계는 실제 EDA 형식 명세와 공개 출력 확보, 하드웨어 담당자와 Rule·정답 확인, 대용량/지원 범위 평가입니다. 제공 generate 모듈·기존 Rule/BOM 어댑터, Gemini 실행 경로, 웹/System 인증·API는 입력과 인터페이스가 확정되면 연결합니다. 현재 구현은 모델 호출, PDF 출력, 사람 답변 저장·재검증 이력, DB, 웹 서버를 포함하지 않습니다.
