package com.ssafy.circuitaudit.rule.domain;

import java.math.BigDecimal;
import java.util.regex.Pattern;

public final class ElectricalValue {
    private static final Pattern VALUE = Pattern.compile(
            "^([+-]?(?:\\d+(?:[.,]\\d*)?|[.,]\\d+)(?:[eE][+-]?\\d+)?)\\s*([pnumkKMµμ]?)\\s*(Ω|[Oo]hms?|[Ff])?$");

    private ElectricalValue() {}

    public static BigDecimal resistanceOhms(String raw) {
        return parse(raw, false);
    }

    public static BigDecimal capacitanceFarads(String raw) {
        return parse(raw, true);
    }

    private static BigDecimal parse(String raw, boolean capacitance) {
        if (raw == null || raw.isBlank()) throw new IllegalArgumentException("Missing component value");
        var match = VALUE.matcher(raw.trim());
        if (!match.matches()) throw new IllegalArgumentException("Unsupported value: " + raw);
        String unit = match.group(3);
        if (capacitance ? unit == null || !unit.equalsIgnoreCase("F") : unit != null && unit.equalsIgnoreCase("F")) {
            throw new IllegalArgumentException("Unexpected or missing unit: " + raw);
        }
        int exponent = switch (match.group(2)) {
            case "p" -> -12;
            case "n" -> -9;
            case "u", "µ", "μ" -> -6;
            case "m" -> -3;
            case "k", "K" -> 3;
            case "M" -> 6;
            default -> 0;
        };
        var value = new BigDecimal(match.group(1).replace(',', '.')).scaleByPowerOfTen(exponent);
        if (value.signum() < 0) throw new IllegalArgumentException("Negative passive component value: " + raw);
        return value;
    }
}
