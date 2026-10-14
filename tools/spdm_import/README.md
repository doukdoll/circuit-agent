# SPDM 로컬 점검 도구 — 사내 반입용

이미 병합/정제된 SPDM xlsx에서 설정으로 선택한 컬럼을 점검하고 원문/최소 정제값을 비교합니다. 원본 파일은 변경하지 않으며 서버·외부 API·인터넷 연결을 사용하지 않습니다. SQLite 저장과 DRM 해제 기능은 아직 포함하지 않습니다.

## 준비

이 폴더의 코드·설정·테스트를 반입하고, 폴더에서 PowerShell을 엽니다. Python 3와 사내 환경에 설치된 `openpyxl`이 필요합니다.

```powershell
python -c "import openpyxl; print(openpyxl.__version__)"
```

의존성이 없으면 사내 승인된 설치 경로를 사용합니다. `requirements.txt`는 필요한 패키지 명세이며 이 배포에는 패키지 자체나 Python 실행 파일이 포함되지 않습니다.

## 실제 파일 없이 먼저 검증

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

테스트는 임시 폴더에 가상 Excel을 만들고 실행 후 제거합니다. 실제 회사 파일과 인터넷 연결이 필요하지 않습니다. 11개 테스트가 통과하는지 확인합니다. 이 결과는 실제 SPDM 파일이나 DRM 접근의 성공을 의미하지 않습니다.

## 사내 실제 파일 점검

```powershell
python .\inspect_rules.py `
  "C:\Users\d7983.lee\Downloads\Data\spdm_checkpoint_merged_20261012_160751.xlsx" `
  --report .\local-output\inspection.json `
  --preview 20

$LASTEXITCODE
```

실제 파일 경로가 다르면 첫 인수를 바꿉니다. `--mapping .\my_mapping.json`으로 별도 컬럼 설정을 사용할 수 있습니다. `mapping.json`의 기본 13개 컬럼 선택은 제공된 명세 기반의 초기 제안입니다. 정제 결과 컬럼 이름이 확정되면 해당 필드의 `header`와 필요시 `column`을 수정합니다. 고유 헤더는 `column`을 생략하고 선택할 수 있습니다.

출력 JSON의 `preview`에서 선택된 `raw`와 `selected`를 나란히 비교하고, `issues`와 `duplicate_candidates`를 확인합니다. `--preview 0`은 원문 미리보기만 끄며 전체 행 점검은 유지합니다. 보고서에는 파일명·헤더·문제 위치 정보가 남으므로 이 옵션을 외부 공유용 익명화로 간주하지 않습니다.

종료 코드 0은 변환 오류 없이 점검 완료, 2는 변환 오류 또는 입력/설정 오류입니다. 경고·중복 후보는 자동 삭제하지 않습니다. 데이터 변환 오류가 있으면 보고서를 만들지만 입력 파일·시트·헤더를 읽지 못하면 만들지 않습니다. 이번 실행의 종료 코드를 확인하고 이전 보고서와 혼동하지 않습니다.

## 반출 없이 개발·검증하는 흐름

외부에서는 제공된 구조 명세와 가상 데이터로 구현하고, 사내에서는 실제 파일로 실행하여 매핑·정제 결과를 확인합니다. 실제 xlsx, 점검 보고서, 원문을 포함한 로그는 사내에 유지합니다. 반출 승인이 없는 정보는 가져올 필요가 없습니다. 후속 수정은 공개 가능한 일반적인 증상이나 가상 재현 사례로 검증할 수 있습니다.

`openpyxl`이 파일을 읽지 못하면 사내 Python 실행 환경에서 DRM 보호 파일을 읽을 수 있는지 먼저 확인합니다. 이 도구가 DRM 보호를 해제하거나 우회하지는 않습니다.
