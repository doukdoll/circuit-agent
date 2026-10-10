package com.ssafy.circuitaudit.result.report;

import com.ssafy.circuitaudit.audit.domain.AuditRun;
import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import java.util.Comparator;
import java.util.TreeMap;

public final class HtmlReportWriter {
    public String render(AuditRun run) {
        var summary = run.summary();
        var html = new StringBuilder("""
                <!doctype html>
                <html lang="ko"><head><meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>CircuitAgent 검사 보고서</title>
                <style>
                body{font-family:system-ui,sans-serif;background:#f5f7fb;color:#1d2739;margin:0}
                main{max-width:1100px;margin:auto;padding:32px}h1{margin-bottom:8px}h2{margin-top:32px}
                .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
                .card,section{background:white;border:1px solid #dbe1ed;border-radius:10px;padding:16px}
                .card strong{display:block;font-size:28px}.note{background:#fff4d6;padding:14px;border-radius:8px}
                table{width:100%;border-collapse:collapse;margin:12px 0}th,td{text-align:left;border-bottom:1px solid #dbe1ed;padding:10px;vertical-align:top}
                code{overflow-wrap:anywhere}li{margin-bottom:6px}.PASS{color:#17643d}.FAIL{color:#b42318}
                .NEEDS_REVIEW{color:#875a00}.NOT_APPLICABLE{color:#526071}.table-wrap{overflow-x:auto}
                </style></head><body><main><h1>CircuitAgent 검사 보고서</h1>
                """);
        html.append("<p>실행 상태: <strong>").append(escape(run.executionStatus())).append("</strong> · ")
                .append(escape(run.executedAt())).append("</p>");
        html.append("<p class=\"note\">").append(escape(run.rule().scope()))
                .append("<br>허용 기준 출처: ").append(escape(run.rule().acceptanceOrigin())).append("</p>");
        html.append("<div class=\"cards\">");
        card(html, "검사 대상", summary.targets());
        card(html, "자동 판정 완료", summary.completed());
        card(html, "사람 확인 필요", summary.needsReview());
        card(html, "파싱·참조 오류", summary.errors());
        card(html, "지정 DNI 제외", summary.excludedComponents());
        html.append("</div><p>집계 단위: 현재 Rule × 적용 인스턴스. 자동 판정 완료는 PASS + FAIL이며, ")
                .append("보류·제외·오류는 PASS에 포함하지 않습니다. 회로 전체의 적합성을 판정한 보고서가 아닙니다.</p>");
        if (summary.targets() == 0) {
            html.append("<p class=\"note\">적용 모델과 일치하는 검사 대상이 없습니다. 검사를 통과한 것으로 해석하지 마세요.</p>");
        }
        html.append("<h2>입력과 검사 범위</h2><section><dl>");
        detail(html, "입력 파일", run.inputFile());
        detail(html, "입력 SHA-256", run.inputSha256());
        detail(html, "Rule / 버전", run.rule().id() + " / " + run.rule().version());
        detail(html, "전체 / 포함 부품", summary.parsedComponents() + " / " + summary.includedComponents());
        detail(html, "NET 레코드의 넷 수", String.valueOf(summary.nets()));
        detail(html, "판정별 개수", "PASS=" + summary.pass() + ", FAIL=" + summary.fail()
                + ", NEEDS_REVIEW=" + summary.needsReview() + ", NOT_APPLICABLE=" + summary.notApplicable());
        detail(html, "경고 개수", String.valueOf(summary.warnings()));
        html.append("</dl></section><h2>인스턴스별 결과</h2>");
        for (var result : run.results()) {
            html.append("<section><h3>").append(escape(result.instanceId())).append(" · <span class=\"")
                    .append(result.verdict()).append("\">").append(result.verdict()).append("</span></h3>")
                    .append("<p>").append(escape(result.reason())).append("</p>");
            if (!result.calculation().isEmpty()) {
                html.append("<p><code>V_OUT = V_REF × (1 + R_TOP / R_BOTTOM)</code></p><table><tr><th>계산 항목</th><th>값</th></tr>");
                new TreeMap<>(result.calculation()).forEach((name, value) -> html.append("<tr><td>")
                        .append(escape(name)).append("</td><td>").append(escape(value.stripTrailingZeros().toPlainString()))
                        .append("</td></tr>"));
                html.append("</table>");
            }
            html.append("<h4>근거</h4><ul>");
            result.evidence().forEach(e -> html.append("<li><code>").append(escape(e.location()))
                    .append("</code> — ").append(escape(e.description())).append("</li>"));
            html.append("</ul></section>");
        }
        html.append("<h2>사람 검토 요청</h2><ul>");
        run.results().stream().filter(r -> r.verdict() == com.ssafy.circuitaudit.result.domain.Verdict.NEEDS_REVIEW)
                .forEach(r -> html.append("<li>").append(escape(r.instanceId() + " / " + r.ruleId() + ": " + r.reason()))
                        .append(" — 위 근거와 원본 입력을 확인한 뒤 재검증하세요.</li>"));
        html.append("</ul><h2>진단과 제외 기록</h2><ul>");
        run.graph().diagnostics().forEach(d -> html.append("<li>").append(escape(d.severity() + " / " + d.code()
                + " / " + d.source().display() + ": " + d.message())).append("</li>"));
        run.graph().exclusions().forEach(e -> html.append("<li>DNI 제외: ")
                .append(escape(e.component().id() + " / " + e.reason() + " / " + e.component().source().display()))
                .append("</li>"));
        html.append("</ul><h2>포함된 회로 연결</h2><div class=\"table-wrap\"><table>")
                .append("<tr><th>부품</th><th>모델 / 값</th><th>핀 → 넷</th><th>원본 위치</th></tr>");
        run.graph().components().values().stream().sorted(Comparator.comparing(CircuitComponent::id)).forEach(c -> {
            html.append("<tr><td>").append(escape(c.id())).append("</td><td>")
                    .append(escape(c.model() + " / " + c.properties().getOrDefault("Value", "값 미제공")))
                    .append("</td><td>").append(escape(new TreeMap<>(c.pinNets()).toString()))
                    .append("</td><td>").append(escape(c.source().display())).append("</td></tr>");
        });
        return html.append("</table></div></main></body></html>\n").toString();
    }

    private void card(StringBuilder html, String title, int count) {
        html.append("<div class=\"card\">").append(escape(title)).append("<strong>").append(count).append("</strong></div>");
    }

    private void detail(StringBuilder html, String label, String value) {
        html.append("<dt>").append(escape(label)).append("</dt><dd><code>").append(escape(value)).append("</code></dd>");
    }

    private String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\"", "&quot;").replace("'", "&#39;");
    }
}
