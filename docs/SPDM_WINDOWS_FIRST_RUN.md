# Windows에서 SPDM JSON 처음 실행하기

Python 3.12와 새 JSON 전용 ZIP을 준비합니다. [전체 실행 가이드](SPDM_JSON_RUN.md)의 순서대로 Python 경로·JSON 경로를 지정하고 실행합니다. 인터넷은 설치 자료 준비에 사용할 수 있으며 프로그램은 외부 API 없이 동작합니다. 추가 Python 패키지는 필요 없습니다.

압축을 푼 코드 폴더에서 PowerShell을 열고 실제 Python 경로로 다음을 실행합니다.

```powershell
$SpdmPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
& $SpdmPython -S .\verify_environment.py --expect-windows --input "실제 JSON 경로" --report .\local-output\environment.json
$LASTEXITCODE
```

상태 passed, system Windows, windows_verified true와 모든 checks 항목의 성공을 확인합니다. 이 값은 실행 중인 실제 OS에서 계산하며 Linux에서 Windows 검증으로 기록하지 않습니다. 실패하면 보고서의 error와 unit_test_log를 확인합니다.

이 검증은 임시 폴더와 가상 테스트를 사용하고 원본은 수정하지 않습니다. 실제 JSON이 없으면 --input을 생략할 수 있습니다. 가상 테스트 성공과 사내 실제 입력 성공을 구분합니다. 코드 테스트는 QCV/BOM 사실 추출이나 Gemini 판정을 포함하지 않습니다.
