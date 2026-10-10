package com.ssafy.circuitaudit.rule.engine;

import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;
import com.ssafy.circuitaudit.result.domain.RuleResult;
import com.ssafy.circuitaudit.result.domain.Verdict;
import com.ssafy.circuitaudit.rule.domain.RuleContext;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import com.ssafy.circuitaudit.rule.handler.NominalFeedbackDividerHandler;
import com.ssafy.circuitaudit.rule.handler.RuleHandler;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class RuleEngine {
    private final List<RuleHandler> handlers;

    public RuleEngine() {
        this(List.of(new NominalFeedbackDividerHandler()));
    }

    public RuleEngine(List<RuleHandler> handlers) {
        this.handlers = List.copyOf(handlers);
    }

    public List<RuleResult> evaluate(CircuitGraph graph, RuleDefinition rule) {
        var results = new ArrayList<RuleResult>();
        // Enumerate every applicable instance before retrieval or evaluation.
        var targets = new TargetResolver().resolve(graph, rule);
        var matching = handlers.stream().filter(h -> h.supports(rule)).toList();
        for (var target : targets) {
            if (graph.hasErrors() || matching.size() != 1) {
                String reason = graph.hasErrors() ? "QCV contains parsing/reference errors; resolve diagnostics first."
                        : "Unsupported or ambiguous Rule handler; confirm the Rule implementation.";
                results.add(new RuleResult(target.id(), rule.id(), Verdict.NEEDS_REVIEW, reason, Map.of(),
                        List.of(new RuleResult.Evidence(target.source().display(), "Target component"))));
            } else {
                results.add(matching.getFirst().evaluate(new RuleContext(graph, target, rule)));
            }
        }
        return List.copyOf(results);
    }
}
