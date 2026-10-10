package com.ssafy.circuitaudit.rule.domain;

import java.math.BigDecimal;
import java.util.List;

public record RuleDefinition(
        String id, String version, String type, String targetModel, String feedbackPin, String groundPin,
        String outputNet, String groundNet, BigDecimal referenceVoltageV, BigDecimal targetVoltageV,
        BigDecimal toleranceFraction, String scope, String acceptanceOrigin, List<RuleSource> sources) {
    public RuleDefinition {
        for (String required : new String[]{id, version, type, targetModel, feedbackPin, groundPin,
                outputNet, groundNet, scope, acceptanceOrigin}) {
            if (required == null || required.isBlank()) throw new IllegalArgumentException("Incomplete rule configuration");
        }
        if (referenceVoltageV == null || referenceVoltageV.signum() <= 0
                || targetVoltageV == null || targetVoltageV.signum() <= 0
                || toleranceFraction == null || toleranceFraction.signum() < 0
                || toleranceFraction.compareTo(BigDecimal.ONE) > 0) {
            throw new IllegalArgumentException("Invalid rule voltage or tolerance");
        }
        if (outputNet.equals(groundNet) || feedbackPin.equals(groundPin)) {
            throw new IllegalArgumentException("Output/ground nets and FB/ground pins must be distinct");
        }
        if (sources == null || sources.isEmpty() || sources.stream().anyMatch(java.util.Objects::isNull)) {
            throw new IllegalArgumentException("Rule evidence is required");
        }
        sources = List.copyOf(sources);
    }

    public record RuleSource(String url, int page, String section, String description) {
        public RuleSource {
            if (url == null || url.isBlank() || page <= 0 || section == null || section.isBlank()
                    || description == null || description.isBlank()) {
                throw new IllegalArgumentException("Incomplete Rule source citation");
            }
        }
    }
}
