# circuit-agent

공개 QCV 파일로 회로 연결을 파싱하고, 기본 Rule을 계산하여 JSON·HTML 보고서를 생성하는 Java 21 데모입니다.

- [개발 및 실행 가이드](docs/DEVELOPMENT_GUIDE.md)
- [공개 샘플·출처·기대 결과](samples/README.md)
- [프로젝트 문서 목차](docs/README.md)

JDK 21과 Maven 3.9 이상이 필요합니다. 저장소 루트에서 실행하세요.

```bash
mvn clean package
java -jar target/circuit-audit-demo.jar \
  --qcv samples/ti/tps56c230/cases/normal.qcv \
  --rule samples/ti/tps56c230/rule.json \
  --output output/normal
```

`output/normal/report.html`을 브라우저에서 열면 결과와 근거를 볼 수 있습니다. 이 PASS는 축약된 회로의 명목 분압 계산에 대한 개발용 판정입니다. 삼성전자 내부 QCV와의 호환성이나 전체 회로 적합성은 확인되지 않았습니다.
