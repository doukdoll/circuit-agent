package com.ssafy.circuitaudit.rule.domain;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;

public record RuleContext(CircuitGraph graph, CircuitComponent target, RuleDefinition rule) {}
