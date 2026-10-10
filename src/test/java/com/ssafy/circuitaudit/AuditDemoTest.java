package com.ssafy.circuitaudit;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;

class AuditDemoTest {
    private final Path directory = Path.of("samples/ti/tps56c230");
    @TempDir Path temporary;

    @ParameterizedTest
    @CsvSource({"normal, 0, PASS", "violation, 1, FAIL", "missing-value, 3, NEEDS_REVIEW"})
    void cliProducesMachineReadableAndVisualReports(String scenario, int code, String verdict) throws Exception {
        var qcv = directory.resolve("cases/" + scenario + ".qcv");
        assertEquals(code, run("--qcv", qcv.toString(), "--rule", directory.resolve("rule.json").toString(),
                "--output", temporary.toString()));
        var report = new ObjectMapper().readTree(temporary.resolve("audit.json").toFile());
        assertEquals(verdict, report.get("results").get(0).get("verdict").asText());
        assertEquals(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(qcv))),
                report.get("inputSha256").asText());
        String html = Files.readString(temporary.resolve("report.html"));
        assertTrue(html.contains(verdict));
        assertTrue(html.contains("R4"));
        assertTrue(html.contains("NEEDS_REVIEW"));
        assertTrue(html.contains("SHA-256"));
    }

    @Test
    void parseFailureProducesFailedReportWithNoCompletedChecks() throws Exception {
        var input = temporary.resolve("bad.qcv");
        Files.writeString(input, Files.readString(directory.resolve("cases/normal.qcv")) + "unrecognized line\n");
        assertEquals(2, run("--qcv", input.toString(), "--rule", directory.resolve("rule.json").toString(),
                "--output", temporary.toString()));
        var report = new ObjectMapper().readTree(temporary.resolve("audit.json").toFile());
        assertEquals("FAILED", report.get("executionStatus").asText());
        assertEquals(0, report.get("summary").get("completed").asInt());
    }

    @Test
    void zeroTargetsIsNotReportedAsPass() throws Exception {
        assertEquals(3, run("--qcv", "samples/qcv/ansys-pyaedt/Schematic1.qcv",
                "--rule", directory.resolve("rule.json").toString(), "--output", temporary.toString()));
        var report = new ObjectMapper().readTree(temporary.resolve("audit.json").toFile());
        assertEquals(0, report.get("summary").get("targets").asInt());
        assertEquals(0, report.get("summary").get("pass").asInt());
    }

    @Test
    void inspectParsesPublicSourceWithoutExecutingRule() throws Exception {
        assertEquals(0, run("--qcv", "samples/qcv/ansys-pyaedt/Schematic1.qcv",
                "--inspect", "--output", temporary.toString()));
        var graph = new ObjectMapper().readTree(temporary.resolve("graph.json").toFile());
        assertEquals(11, graph.get("components").size());
        assertFalse(Files.exists(temporary.resolve("report.html")));
    }

    @Test
    void rejectsIncompleteDniAndEscapesUserControlledHtml() throws Exception {
        assertEquals(2, run("--qcv", directory.resolve("cases/normal.qcv").toString(),
                "--rule", directory.resolve("rule.json").toString(), "--output", temporary.toString(), "--dni-property", "DNI"));
        assertFalse(Files.exists(temporary.resolve("audit.json")));
        var mapper = new ObjectMapper();
        var rule = (com.fasterxml.jackson.databind.node.ObjectNode) mapper.readTree(directory.resolve("rule.json").toFile());
        rule.put("scope", "<script>alert('x')</script> & scope");
        var input = temporary.resolve("rule.json");
        mapper.writeValue(input.toFile(), rule);
        assertEquals(0, run("--qcv", directory.resolve("cases/normal.qcv").toString(),
                "--rule", input.toString(), "--output", temporary.toString()));
        String html = Files.readString(temporary.resolve("report.html"));
        assertFalse(html.contains("<script>"));
        assertTrue(html.contains("&lt;script&gt;"));
        assertTrue(html.contains("&amp; scope"));
    }

    private int run(String... args) {
        var output = new PrintStream(new ByteArrayOutputStream());
        return AuditDemo.run(args, output, output);
    }

    @Test
    void incompleteRuleCitationIsAnInputError() throws Exception {
        var mapper = new ObjectMapper();
        var rule = (com.fasterxml.jackson.databind.node.ObjectNode) mapper.readTree(directory.resolve("rule.json").toFile());
        ((com.fasterxml.jackson.databind.node.ObjectNode) rule.get("sources").get(0)).remove("description");
        var file = temporary.resolve("incomplete-rule.json");
        mapper.writeValue(file.toFile(), rule);
        assertEquals(2, run("--qcv", directory.resolve("cases/normal.qcv").toString(),
                "--rule", file.toString(), "--output", temporary.toString()));
        assertFalse(Files.exists(temporary.resolve("audit.json")));
    }
}
