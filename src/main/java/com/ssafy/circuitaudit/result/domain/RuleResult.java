package com.ssafy.circuitaudit.result.domain;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public record RuleResult(String instanceId, String ruleId, Verdict verdict, String reason,
                         Map<String, BigDecimal> calculation, List<Evidence> evidence) {
    public RuleResult {
        calculation = Map.copyOf(calculation);
        evidence = List.copyOf(evidence);
    }

    public record Evidence(String location, String description) {}
}
