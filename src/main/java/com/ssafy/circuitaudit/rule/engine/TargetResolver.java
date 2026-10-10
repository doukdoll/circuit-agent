package com.ssafy.circuitaudit.rule.engine;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import java.util.Comparator;
import java.util.List;

public final class TargetResolver {
    public List<CircuitComponent> resolve(CircuitGraph graph, RuleDefinition rule) {
        return graph.components().values().stream().filter(c -> c.model().equals(rule.targetModel()))
                .sorted(Comparator.comparing(CircuitComponent::id)).toList();
    }
}
