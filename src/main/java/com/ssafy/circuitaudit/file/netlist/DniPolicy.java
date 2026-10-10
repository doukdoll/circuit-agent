package com.ssafy.circuitaudit.file.netlist;

import java.util.Map;
import java.util.Set;

/** DNI markers are configured explicitly; no company-specific convention is assumed. */
public record DniPolicy(String property, Set<String> values) {
    public DniPolicy {
        values = Set.copyOf(values);
    }

    public static DniPolicy none() {
        return new DniPolicy(null, Set.of());
    }

    public boolean excludes(Map<String, String> properties) {
        String value = property == null ? null : properties.get(property);
        return value != null && values.contains(value);
    }
}
