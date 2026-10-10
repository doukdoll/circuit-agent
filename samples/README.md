# 공개 샘플과 기대 결과

회사 자료 없이 파싱·검색·계산·보류·보고서 흐름을 개발하기 위한 샘플입니다. 출처가 있는 원본과 직접 만든 테스트 회로를 구분합니다. 삼성전자에서 사용하는 형식이나 내부 Rule과의 일치 여부는 확인되지 않았습니다.

## 공개 QCV 원본

[Ansys PyAEDT의 Schematic1.qcv](https://github.com/ansys/pyaedt/blob/dafbb23b697c00eb1d0b653f9d194a3e5df9f970/tests/system/general/example_models/T21/Schematic1.qcv)를 특정 커밋에서 받아 [원본 파일](qcv/ansys-pyaedt/Schematic1.qcv)과 [동일 버전 MIT 라이선스](qcv/ansys-pyaedt/LICENSE)를 보존했습니다. 원본은 수정하지 않았습니다. 커밋·URL·SHA-256은 [provenance.json](qcv/ansys-pyaedt/provenance.json)에 기록했습니다.

[expected.json](qcv/ansys-pyaedt/expected.json)은 원문에서 별도로 기록한 파싱 기대 결과입니다.

- 부품 11개, 넷 6개, 핀 연결 16개
- R3와 같은 넷으로 연결되는 부품: R2, C2, R4, R5
- `1k`, `0,1uF`와 같은 값의 단위 변환
- V1007·V1008·V2005는 핀 연결을 제공하지 않으므로 경고 3개

이 원본에는 아래 TPS56C230 분압 Rule의 적용 대상이 없습니다. 파싱 성공과 회로 검사 PASS는 다른 결과입니다.

## TI 자료를 참고하여 만든 계산 사례

[TI TPS56C230EVM 사용자 가이드 SLVUBJ0B](https://www.ti.com/lit/pdf/SLVUBJ0)의 공개 사실을 참고하여 FB 분압 부분만 직접 표현했습니다. 이 QCV는 TI·Siemens·삼성전자가 내보낸 파일이 아닙니다. 가이드 PDF는 저장소에 복제하지 않았습니다.

| 사실 | 근거 |
| --- | --- |
| 명목 출력 1.2V | 3쪽 Table 2-1 |
| 기준 전압 0.6V 및 분압식 | 4쪽 3.1, Equation 1 |
| U1의 FB 14번, AGND 13번 핀과 분압 연결 | 17쪽 Figure 6-1 |
| R4·R6 각각 10kΩ, 공차 1% | 18쪽 Table 6-1 |

`V_OUT = 0.6 × (1 + R4/R6)`이므로 두 저항이 10kΩ이면 1.2V입니다. **판정 허용 오차 ±3%는 개발용으로 정한 기준**이며 TI 규격이나 회사 요구사항이 아닙니다. 실제 저항 공차·기준 전압 변동·과도 응답·전원 회로 전체는 검사하지 않습니다. 저항의 핀 번호 1/2와 단일 GND 표기는 축약 모델을 위한 선택입니다.

[provenance.json](ti/tps56c230/provenance.json)에 사실과 개발 선택을 구분했습니다. [bom.csv](ti/tps56c230/bom.csv)는 원문 확인용 일부 부품 목록이며 현재 실행기는 BOM을 읽지 않습니다. 계산 값은 QCV의 `Value` 속성에서 읽습니다. [rule.json](ti/tps56c230/rule.json)은 이 데모가 정의한 입력 스키마입니다.

| 사례 | 파일 | 기대 결과 | 근거 |
| --- | --- | --- | --- |
| 정상 | [normal.qcv](ti/tps56c230/cases/normal.qcv) | PASS | 1.2V, 명목 오차 0% |
| 값 위반 | [violation.qcv](ti/tps56c230/cases/violation.qcv) | FAIL | R4=12kΩ → 1.32V, 오차 10% |
| 값 누락 | [missing-value.qcv](ti/tps56c230/cases/missing-value.qcv) | NEEDS_REVIEW | R4 값 확인 필요 |
| 병렬 연결 | [ambiguous.qcv](ti/tps56c230/cases/ambiguous.qcv) | NEEDS_REVIEW | 추가 R99 연결로 기본 모델 적용 보류 |
| DNI 제외 지정 | [dni.qcv](ti/tps56c230/cases/dni.qcv) | PASS, 제외 1개 | `DNI=yes`를 실행 시 지정하여 R99 제외 |
| DNI 미지정 | 같은 dni.qcv | NEEDS_REVIEW, 제외 0개 | 표시만 보고 자동 제외하지 않음 |

[expected.json](ti/tps56c230/expected.json)에 수치와 판정을 별도로 기록했으며 Java 테스트가 이 결과와 비교합니다. 실행 방법은 [개발 가이드](../docs/DEVELOPMENT_GUIDE.md)를 참고하세요.

## 실제 형식으로 확장할 때

회사 원본 대신 사용 EDA 도구의 공개 예제 또는 라이선스가 허용하는 평가보드 자료를 구하고, 같은 도구에서 넷리스트를 내보내 문법 차이를 확인하는 것이 다음 단계입니다. EDA 도구·버전·내보내기 옵션과 익명화된 형식 명세를 확보하기 전까지 `.qcv` 확장자만으로 내부 파일과 호환된다고 판단하지 않습니다. Rule 의미와 정답은 하드웨어 담당자의 검토가 필요합니다.
