package com.ssafy.circuitaudit.file.netlist;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.connection.PinRef;
import com.ssafy.circuitaudit.circuit.graph.CircuitGraph;
import com.ssafy.circuitaudit.circuit.graph.Diagnostic;
import com.ssafy.circuitaudit.circuit.net.CircuitNet;
import com.ssafy.circuitaudit.circuit.source.SourceLocation;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/** Parser for the documented NET/COMP/Property/Explicit Pin dialect in the public fixture. */
public final class QcvParser {
    private static final Pattern NET = Pattern.compile("^NET\\s*:\\s*'([^']+)'(?:\\s+(.+))?$");
    private static final Pattern COMP = Pattern.compile(
            "^COMP\\s*:\\s*'([^']+)'\\s+'([^']+)'(?:\\s+'([^']*)'\\s+'([^']*)')?\\s*$");
    private static final Pattern PROPERTY = Pattern.compile("^Property\\s*:\\s*([^=]+)=(.*)$");
    private static final Pattern PIN = Pattern.compile(
            "^Explicit Pin\\s*:\\s*'([^']+)'\\s+'([^']*)'\\s+'([^']+)'\\s*$");

    public CircuitGraph parse(Path file) throws IOException {
        return parse(file, DniPolicy.none());
    }

    public CircuitGraph parse(Path file, DniPolicy dni) throws IOException {
        return parse(file, Files.readAllBytes(file), dni);
    }

    /** Parse the same byte snapshot used to identify the input in the report. */
    public CircuitGraph parse(Path file, byte[] bytes, DniPolicy dni) throws IOException {
        var lines = StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(bytes)).toString().lines().toList();
        var components = new LinkedHashMap<String, Builder>();
        var nets = new LinkedHashMap<String, LinkedHashSet<PinRef>>();
        var netSources = new LinkedHashMap<String, SourceLocation>();
        var assignments = new LinkedHashMap<PinRef, Assignment>();
        var issues = new ArrayList<Diagnostic>();
        Builder current = null;

        for (int index = 0; index < lines.size(); index++) {
            int lineNumber = index + 1;
            var source = new SourceLocation(file.toString(), lineNumber, lineNumber);
            String line = lines.get(index).trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            var net = NET.matcher(line);
            var comp = COMP.matcher(line);
            var property = PROPERTY.matcher(line);
            var pin = PIN.matcher(line);
            if (net.matches()) {
                if (current != null) current.end = lineNumber - 1;
                current = null;
                String name = net.group(1);
                nets.computeIfAbsent(name, ignored -> new LinkedHashSet<>());
                netSources.putIfAbsent(name, source);
                if (net.group(2) != null) {
                    for (String token : net.group(2).trim().split("\\s+")) {
                        int split = token.lastIndexOf('-');
                        if (split <= 0 || split == token.length() - 1) {
                            error(issues, "INVALID_ENDPOINT", "Invalid NET endpoint: " + token, source);
                            continue;
                        }
                        var ref = new PinRef(token.substring(0, split), token.substring(split + 1));
                        nets.get(name).add(ref);
                        assign(assignments, ref, name, source, issues);
                    }
                }
            } else if (comp.matches()) {
                if (current != null) current.end = lineNumber - 1;
                String id = comp.group(2);
                current = new Builder(id, comp.group(1), comp.group(3), comp.group(4), source);
                if (components.putIfAbsent(id, current) != null) {
                    error(issues, "DUPLICATE_COMPONENT", "Duplicate component: " + id, source);
                    current = null;
                }
            } else if (property.matches() && current != null) {
                String key = property.group(1).trim();
                if (current.properties.putIfAbsent(key, property.group(2).trim()) != null) {
                    error(issues, "DUPLICATE_PROPERTY", "Duplicate property: " + current.id + "." + key, source);
                }
                current.propertySources.putIfAbsent(key, source);
            } else if (pin.matches() && current != null) {
                String number = pin.group(1);
                String name = pin.group(3);
                if (current.explicitPins.putIfAbsent(number, name) != null) {
                    error(issues, "DUPLICATE_PIN", "Duplicate explicit pin: " + current.id + "-" + number, source);
                }
                current.explicitSources.putIfAbsent(number, source);
            } else {
                error(issues, "UNSUPPORTED_LINE", "Unsupported QCV line: " + line, source);
            }
        }
        if (current != null) current.end = lines.size();
        if (components.isEmpty() || nets.isEmpty()) {
            error(issues, "INCOMPLETE_INPUT", "The supported dialect requires COMP and NET records.",
                    new SourceLocation(file.toString(), 1, Math.max(1, lines.size())));
        }

        // Resolve references only after reading the whole file: NET records may precede COMP blocks.
        for (var entry : assignments.entrySet()) {
            var builder = components.get(entry.getKey().componentId());
            if (builder == null) {
                error(issues, "UNKNOWN_COMPONENT", "NET references unknown component: " + entry.getKey().display(),
                        entry.getValue().source);
            } else {
                builder.pins.put(entry.getKey().pin(), entry.getValue().net);
                builder.pinSources.put(entry.getKey().pin(), entry.getValue().source);
            }
        }
        for (var builder : components.values()) {
            for (var explicit : builder.explicitPins.entrySet()) {
                var source = builder.explicitSources.get(explicit.getKey());
                var ref = new PinRef(builder.id, explicit.getKey());
                var assignment = assignments.get(ref);
                if (!nets.containsKey(explicit.getValue())) {
                    error(issues, "UNKNOWN_NET", "Explicit pin references unknown net: " + explicit.getValue(), source);
                } else if (assignment == null) {
                    error(issues, "MISSING_NET_MEMBERSHIP", "Explicit pin missing from NET list: " + ref.display(), source);
                } else if (!assignment.net.equals(explicit.getValue())) {
                    error(issues, "CONFLICTING_PIN", "NET and Explicit Pin disagree: " + ref.display(), source);
                }
                builder.pinSources.put(explicit.getKey(), source);
            }
        }

        var included = new LinkedHashMap<String, CircuitComponent>();
        var excluded = new ArrayList<CircuitGraph.Exclusion>();
        for (var builder : components.values()) {
            var component = builder.build();
            if (dni.excludes(component.properties())) {
                excluded.add(new CircuitGraph.Exclusion(component,
                        dni.property() + "=" + component.properties().get(dni.property())));
            } else {
                included.put(component.id(), component);
                if (component.pinNets().isEmpty()) {
                    issues.add(new Diagnostic(Diagnostic.Severity.WARNING, "COMPONENT_WITHOUT_PINS",
                            "No connectivity is provided for " + component.id(), component.source()));
                }
            }
        }
        var excludedIds = excluded.stream().map(e -> e.component().id()).collect(java.util.stream.Collectors.toSet());
        var resolvedNets = new LinkedHashMap<String, CircuitNet>();
        for (var entry : nets.entrySet()) {
            var pins = entry.getValue().stream().filter(p -> !excludedIds.contains(p.componentId())).toList();
            resolvedNets.put(entry.getKey(), new CircuitNet(entry.getKey(), pins, netSources.get(entry.getKey())));
        }
        return new CircuitGraph(included, resolvedNets, issues, excluded);
    }

    private static void assign(Map<PinRef, Assignment> assignments, PinRef ref, String net,
                               SourceLocation source, List<Diagnostic> issues) {
        var previous = assignments.putIfAbsent(ref, new Assignment(net, source));
        if (previous != null && !previous.net.equals(net)) {
            error(issues, "MULTIPLE_NETS", "Pin belongs to different nets: " + ref.display(), source);
        }
    }

    private static void error(List<Diagnostic> issues, String code, String message, SourceLocation source) {
        issues.add(new Diagnostic(Diagnostic.Severity.ERROR, code, message, source));
    }

    private record Assignment(String net, SourceLocation source) {}

    private static final class Builder {
        final String id;
        final String model;
        final String symbol;
        final String hierarchy;
        final SourceLocation start;
        int end;
        final Map<String, String> properties = new LinkedHashMap<>();
        final Map<String, String> explicitPins = new LinkedHashMap<>();
        final Map<String, String> pins = new LinkedHashMap<>();
        final Map<String, SourceLocation> propertySources = new LinkedHashMap<>();
        final Map<String, SourceLocation> explicitSources = new LinkedHashMap<>();
        final Map<String, SourceLocation> pinSources = new LinkedHashMap<>();

        Builder(String id, String model, String symbol, String hierarchy, SourceLocation start) {
            this.id = id;
            this.model = model;
            this.symbol = symbol;
            this.hierarchy = hierarchy;
            this.start = start;
            this.end = start.startLine();
        }

        CircuitComponent build() {
            return new CircuitComponent(id, model, properties, pins, propertySources, pinSources,
                    new SourceLocation(start.file(), start.startLine(), end), symbol, hierarchy);
        }
    }
}
