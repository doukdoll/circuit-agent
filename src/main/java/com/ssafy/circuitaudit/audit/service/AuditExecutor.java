package com.ssafy.circuitaudit.audit.service;

import com.ssafy.circuitaudit.audit.domain.AuditRun;
import com.ssafy.circuitaudit.circuit.graph.Diagnostic;
import com.ssafy.circuitaudit.file.netlist.DniPolicy;
import com.ssafy.circuitaudit.file.netlist.QcvParser;
import com.ssafy.circuitaudit.result.domain.Verdict;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import com.ssafy.circuitaudit.rule.engine.RuleEngine;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;

public final class AuditExecutor {
    public AuditRun execute(Path file, RuleDefinition rule, DniPolicy dni) throws IOException {
        byte[] bytes = Files.readAllBytes(file);
        var graph = new QcvParser().parse(file, bytes, dni);
        var results = new RuleEngine().evaluate(graph, rule);
        int pass = (int) results.stream().filter(r -> r.verdict() == Verdict.PASS).count();
        int fail = (int) results.stream().filter(r -> r.verdict() == Verdict.FAIL).count();
        int review = (int) results.stream().filter(r -> r.verdict() == Verdict.NEEDS_REVIEW).count();
        int na = (int) results.stream().filter(r -> r.verdict() == Verdict.NOT_APPLICABLE).count();
        int errors = (int) graph.diagnostics().stream().filter(d -> d.severity() == Diagnostic.Severity.ERROR).count();
        int warnings = graph.diagnostics().size() - errors;
        var summary = new AuditRun.Summary(graph.components().size() + graph.exclusions().size(),
                graph.components().size(), graph.exclusions().size(), graph.nets().size(),
                results.size(), pass + fail, pass, fail, review, na, errors, warnings);
        try {
            String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            return new AuditRun(Instant.now().toString(), file.toString(), hash,
                    errors == 0 ? "COMPLETED" : "FAILED", rule, graph, results, summary);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
