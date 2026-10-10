package com.ssafy.circuitaudit.circuit.source;

public record SourceLocation(String file, int startLine, int endLine) {
    public String display() {
        return file + ":" + startLine + (endLine == startLine ? "" : "-" + endLine);
    }
}
