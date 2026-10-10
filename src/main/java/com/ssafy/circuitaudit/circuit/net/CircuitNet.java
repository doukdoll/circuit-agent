package com.ssafy.circuitaudit.circuit.net;

import com.ssafy.circuitaudit.circuit.connection.PinRef;
import com.ssafy.circuitaudit.circuit.source.SourceLocation;
import java.util.List;

public record CircuitNet(String name, List<PinRef> pins, SourceLocation source) {
    public CircuitNet {
        pins = List.copyOf(pins);
    }
}
