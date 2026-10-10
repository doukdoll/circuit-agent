package com.ssafy.circuitaudit.audit.domain;

import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;
import com.ssafy.circuitaudit.result.domain.RuleResult;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import java.util.List;

public record AuditRun(String executedAt, String inputFile, String inputSha256, String executionStatus,
                       RuleDefinition rule, CircuitGraph graph, List<RuleResult> results, Summary summary) {
    public AuditRun {
        results = List.copyOf(results);
    }

    public record Summary(int parsedComponents, int includedComponents, int excludedComponents, int nets,
                          int targets, int completed, int pass, int fail, int needsReview,
                          int notApplicable, int errors, int warnings) {}
}
