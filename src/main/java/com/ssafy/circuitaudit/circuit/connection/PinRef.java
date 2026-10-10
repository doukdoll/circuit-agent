package com.ssafy.circuitaudit.circuit.connection;

public record PinRef(String componentId, String pin) {
    public String display() {
        return componentId + "-" + pin;
    }
}
