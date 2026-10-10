package com.ssafy.circuitaudit.circuit.index;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

public final class CircuitIndex {
    private final CircuitGraph graph;

    public CircuitIndex(CircuitGraph graph) {
        this.graph = graph;
    }

    public Set<String> connectedComponents(String componentId) {
        var component = graph.components().get(componentId);
        if (component == null) {
            throw new IllegalArgumentException("Unknown component: " + componentId);
        }
        var connected = new TreeSet<String>();
        for (String netName : component.pinNets().values()) {
            var net = graph.nets().get(netName);
            if (net != null) {
                net.pins().forEach(pin -> connected.add(pin.componentId()));
            }
        }
        connected.remove(componentId);
        return Set.copyOf(connected);
    }

    public List<CircuitComponent> betweenNets(String first, String second) {
        if (first.equals(second)) {
            return List.of();
        }
        var firstNet = graph.nets().get(first);
        if (firstNet == null) return List.of();
        var required = Set.of(first, second);
        return firstNet.pins().stream().map(pin -> pin.componentId()).distinct()
                .map(id -> graph.components().get(id)).filter(java.util.Objects::nonNull)
                .filter(c -> c.pinNets().size() == 2)
                .filter(c -> Set.copyOf(c.pinNets().values()).equals(required))
                .sorted(java.util.Comparator.comparing(CircuitComponent::id)).toList();
    }
}
