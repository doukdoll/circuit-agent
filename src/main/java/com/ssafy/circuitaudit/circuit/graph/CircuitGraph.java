package com.ssafy.circuitaudit.circuit.graph;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.net.CircuitNet;
import java.util.List;
import java.util.Map;

public record CircuitGraph(Map<String, CircuitComponent> components, Map<String, CircuitNet> nets,
                           List<Diagnostic> diagnostics, List<Exclusion> exclusions) {
    public CircuitGraph {
        components = Map.copyOf(components);
        nets = Map.copyOf(nets);
        diagnostics = List.copyOf(diagnostics);
        exclusions = List.copyOf(exclusions);
    }

    public boolean hasErrors() {
        return diagnostics.stream().anyMatch(d -> d.severity() == Diagnostic.Severity.ERROR);
    }

    public record Exclusion(CircuitComponent component, String reason) {}
}
