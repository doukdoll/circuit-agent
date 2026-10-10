package com.ssafy.circuitaudit.circuit.component;

import com.ssafy.circuitaudit.circuit.source.SourceLocation;
import java.util.Map;

public record CircuitComponent(
        String id, String model, Map<String, String> properties, Map<String, String> pinNets,
        Map<String, SourceLocation> propertySources, Map<String, SourceLocation> pinSources,
        SourceLocation source, String symbol, String hierarchy) {
    public CircuitComponent {
        properties = Map.copyOf(properties);
        pinNets = Map.copyOf(pinNets);
        propertySources = Map.copyOf(propertySources);
        pinSources = Map.copyOf(pinSources);
    }
}
