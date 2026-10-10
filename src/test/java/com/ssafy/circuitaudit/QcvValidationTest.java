package com.ssafy.circuitaudit;

import com.ssafy.circuitaudit.file.netlist.DniPolicy;
import com.ssafy.circuitaudit.file.netlist.QcvParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;

class QcvValidationTest {
    @TempDir Path temporary;

    @ParameterizedTest
    @CsvSource({
        "unknown-component, UNKNOWN_COMPONENT",
        "conflicting-pin, CONFLICTING_PIN",
        "multiple-nets, MULTIPLE_NETS",
        "duplicate-component, DUPLICATE_COMPONENT",
        "unsupported, UNSUPPORTED_LINE",
        "empty, INCOMPLETE_INPUT",
        "missing-membership, MISSING_NET_MEMBERSHIP"
    })
    void rejectsIncompleteOrContradictoryConnectivity(String name, String code) throws Exception {
        String input = switch (name) {
            case "unknown-component" -> "NET : 'A' R1-1 R9-1\nCOMP : 'R0603' 'R1'\n";
            case "conflicting-pin" -> "NET : 'A' R1-1\nNET : 'B'\nCOMP : 'R0603' 'R1'\nExplicit Pin : '1' '1' 'B'\n";
            case "multiple-nets" -> "NET : 'A' R1-1\nNET : 'B' R1-1\nCOMP : 'R0603' 'R1'\n";
            case "duplicate-component" -> "NET : 'A' R1-1\nCOMP : 'R0603' 'R1'\nCOMP : 'R0603' 'R1'\n";
            case "unsupported" -> "NET : 'A' R1-1\nCOMP : 'R0603' 'R1'\nMystery : 10\n";
            case "missing-membership" -> "NET : 'A' R1-1\nCOMP : 'R0603' 'R1'\nExplicit Pin : '2' '2' 'A'\n";
            default -> "";
        };
        var file = temporary.resolve(name + ".qcv");
        Files.writeString(file, input);
        var graph = new QcvParser().parse(file);
        assertTrue(graph.hasErrors());
        assertTrue(graph.diagnostics().stream().anyMatch(issue -> issue.code().equals(code)), graph.diagnostics().toString());
    }

    @Test
    void resolvesNetsThatFollowComponents() throws Exception {
        var file = temporary.resolve("order.qcv");
        Files.writeString(file, "COMP : 'R0603' 'R1'\nProperty : Value=1k\nExplicit Pin : '1' '1' 'A'\nNET : 'A' R1-1\n");
        var graph = new QcvParser().parse(file);
        assertFalse(graph.hasErrors());
        assertEquals("A", graph.components().get("R1").pinNets().get("1"));
    }

    @Test
    void excludesOnlyExplicitlyConfiguredDniFromGraphAndPreservesOriginal() throws Exception {
        var file = Path.of("samples/ti/tps56c230/cases/dni.qcv");
        byte[] original = Files.readAllBytes(file);
        var defaultGraph = new QcvParser().parse(file);
        assertEquals(4, defaultGraph.components().size());
        assertEquals(0, defaultGraph.exclusions().size());
        var graph = new QcvParser().parse(file, new DniPolicy("DNI", Set.of("yes")));
        assertEquals(3, graph.components().size());
        assertEquals("R99", graph.exclusions().getFirst().component().id());
        assertEquals("DNI=yes", graph.exclusions().getFirst().reason());
        assertTrue(graph.nets().values().stream().flatMap(net -> net.pins().stream())
                .noneMatch(pin -> pin.componentId().equals("R99")));
        assertEquals(defaultGraph.components().get("R4"), graph.components().get("R4"));
        assertArrayEquals(original, Files.readAllBytes(file));
    }
}
