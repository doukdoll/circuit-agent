package com.ssafy.circuitaudit;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.circuitaudit.circuit.graph.Diagnostic;
import com.ssafy.circuitaudit.circuit.index.CircuitIndex;
import com.ssafy.circuitaudit.file.netlist.QcvParser;
import com.ssafy.circuitaudit.rule.domain.ElectricalValue;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PublicQcvTest {
    private final Path directory = Path.of("samples/qcv/ansys-pyaedt");

    @Test
    void originalAndLicenseMatchPinnedSourceHashes() throws Exception {
        var manifest = new ObjectMapper().readTree(directory.resolve("provenance.json").toFile());
        assertEquals(manifest.get("sha256").asText(), hash(directory.resolve("Schematic1.qcv")));
        assertEquals(manifest.get("licenseSha256").asText(), hash(directory.resolve("LICENSE")));
        assertTrue(Files.readString(directory.resolve("LICENSE")).contains("ANSYS"));
    }

    @Test
    void parsesEveryComponentPinNetAndSourceAgainstIndependentOracle() throws Exception {
        var expected = new ObjectMapper().readTree(directory.resolve("expected.json").toFile());
        var graph = new QcvParser().parse(directory.resolve("Schematic1.qcv"));
        assertFalse(graph.hasErrors(), graph.diagnostics().toString());
        assertEquals(expected.get("componentCount").asInt(), graph.components().size());
        assertEquals(expected.get("netCount").asInt(), graph.nets().size());
        assertEquals(expected.get("pinCount").asInt(), graph.components().values().stream()
                .mapToInt(component -> component.pinNets().size()).sum());
        var components = expected.get("components").fields();
        while (components.hasNext()) {
            var entry = components.next();
            var component = graph.components().get(entry.getKey());
            var oracle = entry.getValue();
            assertNotNull(component, entry.getKey());
            assertEquals(oracle.get("model").asText(), component.model());
            assertEquals(oracle.get("value").isNull() ? null : oracle.get("value").asText(),
                    component.properties().get("Value"));
            assertEquals(new ObjectMapper().convertValue(oracle.get("pinNets"), java.util.Map.class), component.pinNets());
            assertEquals(oracle.get("startLine").asInt(), component.source().startLine());
            assertEquals(oracle.get("endLine").asInt(), component.source().endLine());
        }
        var nets = expected.get("nets").fields();
        while (nets.hasNext()) {
            var entry = nets.next();
            var endpoints = graph.nets().get(entry.getKey()).pins().stream().map(pin -> pin.display()).collect(Collectors.toSet());
            assertEquals(new ObjectMapper().convertValue(entry.getValue(), Set.class), endpoints);
        }
        var values = expected.get("normalizedValues").fields();
        while (values.hasNext()) {
            var entry = values.next();
            String raw = graph.components().get(entry.getKey()).properties().get("Value");
            BigDecimal actual = entry.getValue().get("unit").asText().equals("F")
                    ? ElectricalValue.capacitanceFarads(raw) : ElectricalValue.resistanceOhms(raw);
            assertEquals(0, entry.getValue().get("value").decimalValue().compareTo(actual), entry.getKey());
        }
        assertEquals(Set.of("R2", "C2", "R4", "R5"), new CircuitIndex(graph).connectedComponents("R3"));
        assertEquals(3, graph.diagnostics().size());
        assertTrue(graph.diagnostics().stream().allMatch(issue -> issue.severity() == Diagnostic.Severity.WARNING
                && issue.code().equals("COMPONENT_WITHOUT_PINS")));
        assertEquals("transistor:NPN.1", graph.components().get("V1007").symbol());
        assertEquals("$6I42/$1I3500/$1I8846", graph.components().get("V1007").hierarchy());
    }

    private String hash(Path file) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file)));
    }
}
