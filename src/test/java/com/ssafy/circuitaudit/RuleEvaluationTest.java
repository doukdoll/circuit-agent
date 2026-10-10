package com.ssafy.circuitaudit;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.circuitaudit.audit.service.AuditExecutor;
import com.ssafy.circuitaudit.file.netlist.DniPolicy;
import com.ssafy.circuitaudit.file.netlist.QcvParser;
import com.ssafy.circuitaudit.result.domain.Verdict;
import com.ssafy.circuitaudit.rule.domain.ElectricalValue;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import com.ssafy.circuitaudit.rule.engine.RuleEngine;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;

class RuleEvaluationTest {
    private static final Path DIRECTORY = Path.of("samples/ti/tps56c230");
    @TempDir Path temporary;

    static Stream<Arguments> scenarios() throws Exception {
        var root = new ObjectMapper().readTree(DIRECTORY.resolve("expected.json").toFile());
        return java.util.stream.StreamSupport.stream(root.get("cases").spliterator(), false)
                .map(item -> Arguments.of(item.get("name").asText(), item));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("scenarios")
    void matchesIndependentArithmeticAndReviewCases(String name, com.fasterxml.jackson.databind.JsonNode expected) throws Exception {
        var dni = expected.has("dniProperty") ? new DniPolicy(expected.get("dniProperty").asText(),
                Set.of(expected.get("dniValue").asText())) : DniPolicy.none();
        var run = new AuditExecutor().execute(DIRECTORY.resolve(expected.get("file").asText()), rule(), dni);
        assertEquals("COMPLETED", run.executionStatus());
        assertEquals(1, run.summary().targets());
        var result = run.results().getFirst();
        assertEquals(expected.get("verdict").asText(), result.verdict().name());
        assertEquals(expected.get("excluded").asInt(), run.summary().excludedComponents());
        if (!expected.get("outputVoltageV").isNull()) {
            assertEquals(0, expected.get("outputVoltageV").decimalValue().compareTo(result.calculation().get("outputVoltageV")));
            assertEquals(0, expected.get("relativeError").decimalValue().compareTo(result.calculation().get("relativeError")));
            assertEquals(1, run.summary().completed());
            assertTrue(result.evidence().stream().anyMatch(evidence -> evidence.description().startsWith("R4 Value=")));
        } else {
            assertTrue(result.calculation().isEmpty());
            assertEquals(0, run.summary().completed());
            assertFalse(result.reason().isBlank());
        }
        assertFalse(result.evidence().isEmpty());
        if (name.equals("ambiguous") || name.equals("dni-not-configured")) {
            assertTrue(result.evidence().stream().anyMatch(e -> e.description().startsWith("R99 model=")));
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "1uF", "unknown", "-10k"})
    void unsafeLowerValueRequiresReview(String value) throws Exception {
        var normal = writeNormal();
        var file = normal.replace("COMP: 'R0603' 'R6'\nProperty: Value=10.0k",
                "COMP: 'R0603' 'R6'\nProperty: Value=" + value);
        assertNotEquals(normal, file);
        var result = new RuleEngine().evaluate(new QcvParser().parse(write(file)), rule()).getFirst();
        assertEquals(Verdict.NEEDS_REVIEW, result.verdict());
        assertTrue(result.calculation().isEmpty());
    }

    @Test
    void exactThresholdIsInclusiveAndJustOutsideFails() throws Exception {
        for (String value : new String[]{"10.6k", "10.6001k"}) {
            var text = writeNormal().replaceFirst("Value=10.0k", "Value=" + value);
            var result = new RuleEngine().evaluate(new QcvParser().parse(write(text)), rule()).getFirst();
            assertEquals(value.equals("10.6k") ? Verdict.PASS : Verdict.FAIL, result.verdict());
        }
    }

    @Test
    void enumeratesEveryMatchingTargetBeforeDetectingExtraFeedbackBranches() throws Exception {
        String text = writeNormal().replace("'FB' U1-14", "'FB' U2-14 U1-14")
                .replace("'GND' U1-13", "'GND' U2-13 U1-13")
                + "COMP : 'TPS56C230RJER' 'U2'\n";
        var results = new RuleEngine().evaluate(new QcvParser().parse(write(text)), rule());
        assertEquals(java.util.List.of("U1", "U2"), results.stream().map(result -> result.instanceId()).toList());
        assertTrue(results.stream().allMatch(result -> result.verdict() == Verdict.NEEDS_REVIEW));
    }

    @Test
    void anyParsingErrorBlocksPassAndUnknownHandlerRequiresReview() throws Exception {
        var broken = new QcvParser().parse(write(writeNormal() + "unsupported content\n"));
        assertEquals(Verdict.NEEDS_REVIEW, new RuleEngine().evaluate(broken, rule()).getFirst().verdict());
        var valid = new QcvParser().parse(write(writeNormal()));
        assertEquals(Verdict.NEEDS_REVIEW, new RuleEngine(java.util.List.of()).evaluate(valid, rule()).getFirst().verdict());
    }

    @Test
    void distinguishesMilliMegaAndRejectsDimensionMismatch() {
        assertEquals(0, new BigDecimal("0.001").compareTo(ElectricalValue.resistanceOhms("1m")));
        assertEquals(0, new BigDecimal("1000000").compareTo(ElectricalValue.resistanceOhms("1MΩ")));
        assertEquals(0, new BigDecimal("0.0000001").compareTo(ElectricalValue.capacitanceFarads("0,1uF")));
        assertThrows(IllegalArgumentException.class, () -> ElectricalValue.resistanceOhms("10nF"));
        assertThrows(IllegalArgumentException.class, () -> ElectricalValue.capacitanceFarads("10k"));
    }

    private RuleDefinition rule() throws Exception {
        return new ObjectMapper().readValue(DIRECTORY.resolve("rule.json").toFile(), RuleDefinition.class);
    }

    private String writeNormal() throws Exception {
        return Files.readString(DIRECTORY.resolve("cases/normal.qcv"));
    }

    private Path write(String text) throws Exception {
        var file = temporary.resolve("test.qcv");
        Files.writeString(file, text);
        return file;
    }
}
