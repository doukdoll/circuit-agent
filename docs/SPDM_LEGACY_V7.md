# 보존: JSON 전용 SQLite v7 요구사항과 코드

보존일: 2026-10-19

사용자가 기존 방식을 기록으로 남기고 새 CSV+JSON/14테이블 요구로 전환하도록 요청했습니다. 아래는 **이전 방식**이며 현재 기준은 [Circuit Review 실행 안내](CIRCUIT_REVIEW_RUN.md)입니다.

## 이전 요구사항

- 입력은 전처리 완료 JSON만 받으며 Excel/CSV 입력은 사용하지 않았습니다.
- SQLite v7의 checkpoints/rules 두 업무 테이블을 사용했습니다.
- 최신 전체 JSON으로 교체하고 가져오기 이력/batch를 쌓지 않았습니다.
- 비어 있지 않은 SEC 문자열을 원문 그대로 저장하고 정확히 조회했습니다.
- null applicability와 최상위 error, 파라미터/요구 사실/근거/이슈를 보존했습니다.
- 두 ID는 AUTOINCREMENT였으며 교체 시 새 부모·자식 ID를 연결했습니다.
- PowerShell CLI와 setup_rules.py의 JSON/DB 선택 실행기를 제공했습니다.

## 보존 위치와 기존 근거

기존 Python 코드·계약·테스트·실행기는 [tools/spdm_legacy_v7](../tools/spdm_legacy_v7)에 이동해 보존했습니다. 이동 전 미커밋이던 Python 실행기와 34개 테스트도 함께 보존했습니다. 이 코드의 테스트를 새 버전 검증으로 재실행하지 않았습니다.

이전 [JSON 실행 안내](SPDM_JSON_RUN.md), [Python 실행 안내](SPDM_PYTHON_START.md), [팀 배포 안내](SPDM_TEAM_START.md), 개발 이력의 Windows/사내 확인 기록은 당시 버전의 기록입니다. 핵심 v7 구현 3b27940의 Windows CI 25개와 이후 Python 실행기의 Linux 34개 결과를 구분합니다.

새 버전은 CSV+JSON 전체 대응, 14테이블, 최초 적재 정책을 사용합니다. 이전 DB를 변형하거나 자동 교체하지 않으며 새 파일이 필요합니다. 이전 방식의 최신 교체 정책과 AUTOINCREMENT를 새 코드에 암묵적으로 적용하지 않습니다.
