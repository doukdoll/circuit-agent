package com.ssafy.circuitaudit;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.ssafy.circuitaudit.audit.service.AuditExecutor;
import com.ssafy.circuitaudit.file.netlist.DniPolicy;
import com.ssafy.circuitaudit.file.netlist.QcvParser;
import com.ssafy.circuitaudit.result.report.HtmlReportWriter;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Set;

public final class AuditDemo {
    private static final String USAGE = """
            Usage:
              java -jar target/circuit-audit-demo.jar --qcv FILE --output DIRECTORY --inspect
              java -jar target/circuit-audit-demo.jar --qcv FILE --rule RULE.json --output DIRECTORY
                [--dni-property FIELD --dni-value VALUE]
            Exit codes: 0=completed, 1=rule violation, 2=input/parse error, 3=review or no targets.
            """;

    public static void main(String[] args) {
        int code = run(args, System.out, System.err);
        if (code != 0) System.exit(code);
    }

    public static int run(String[] args, PrintStream out, PrintStream err) {
        try {
            if (args.length == 1 && args[0].equals("--help")) {
                out.print(USAGE);
                return 0;
            }
            boolean inspect = false;
            var options = new HashMap<String, String>();
            var allowed = Set.of("--qcv", "--output", "--rule", "--dni-property", "--dni-value");
            for (int index = 0; index < args.length; index++) {
                String name = args[index];
                if (name.equals("--inspect")) {
                    if (inspect) throw new IllegalArgumentException("Duplicate --inspect");
                    inspect = true;
                } else if (!allowed.contains(name) || index + 1 >= args.length || args[index + 1].startsWith("--")) {
                    throw new IllegalArgumentException("Invalid option: " + name);
                } else if (options.putIfAbsent(name, args[++index]) != null) {
                    throw new IllegalArgumentException("Duplicate option: " + name);
                }
            }
            if (!options.containsKey("--qcv") || !options.containsKey("--output")
                    || (!inspect && !options.containsKey("--rule")) || (inspect && options.containsKey("--rule"))) {
                throw new IllegalArgumentException("Provide --qcv and --output, and either --rule or --inspect");
            }
            if (options.containsKey("--dni-property") != options.containsKey("--dni-value")) {
                throw new IllegalArgumentException("DNI field and value must be specified together");
            }
            var dni = options.containsKey("--dni-property")
                    ? new DniPolicy(options.get("--dni-property"), Set.of(options.get("--dni-value"))) : DniPolicy.none();
            var mapper = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT)
                    .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);
            var input = Path.of(options.get("--qcv"));
            var output = Path.of(options.get("--output"));
            if (inspect) {
                var graph = new QcvParser().parse(input, dni);
                Files.createDirectories(output);
                mapper.writeValue(output.resolve("graph.json").toFile(), graph);
                out.println("Parsed " + graph.components().size() + " included components, " + graph.nets().size()
                        + " nets, " + graph.diagnostics().size() + " diagnostics. No engineering Rule was executed.");
                return graph.hasErrors() ? 2 : 0;
            }
            var rule = mapper.readValue(Path.of(options.get("--rule")).toFile(), RuleDefinition.class);
            var run = new AuditExecutor().execute(input, rule, dni);
            Files.createDirectories(output);
            mapper.writeValue(output.resolve("audit.json").toFile(), run);
            Files.writeString(output.resolve("report.html"), new HtmlReportWriter().render(run), StandardCharsets.UTF_8);
            out.println("Status=" + run.executionStatus() + ", targets=" + run.summary().targets()
                    + ", PASS=" + run.summary().pass() + ", FAIL=" + run.summary().fail()
                    + ", NEEDS_REVIEW=" + run.summary().needsReview() + ", excluded=" + run.summary().excludedComponents());
            out.println("Report: " + output.resolve("report.html"));
            if (run.graph().hasErrors()) return 2;
            if (run.summary().targets() == 0 || run.summary().needsReview() > 0) return 3;
            return run.summary().fail() > 0 ? 1 : 0;
        } catch (IOException | IllegalArgumentException exception) {
            err.println("Error: " + exception.getMessage());
            err.print(USAGE);
            return 2;
        }
    }
}
