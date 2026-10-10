package com.ssafy.circuitaudit.circuit.graph;

import com.ssafy.circuitaudit.circuit.source.SourceLocation;

public record Diagnostic(Severity severity, String code, String message, SourceLocation source) {
    public enum Severity { WARNING, ERROR }
}
