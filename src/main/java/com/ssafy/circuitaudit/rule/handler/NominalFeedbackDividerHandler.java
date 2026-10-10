package com.ssafy.circuitaudit.rule.handler;

import com.ssafy.circuitaudit.circuit.component.CircuitComponent;
import com.ssafy.circuitaudit.circuit.connection.PinRef;
import com.ssafy.circuitaudit.circuit.index.CircuitIndex;
import com.ssafy.circuitaudit.result.domain.RuleResult;
import com.ssafy.circuitaudit.result.domain.Verdict;
import com.ssafy.circuitaudit.rule.domain.ElectricalValue;
import com.ssafy.circuitaudit.rule.domain.RuleContext;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;
import java.math.BigDecimal;
import java.math.MathContext;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Nominal DC divider calculation only; no device, resistor-tolerance or dynamic simulation. */
public final class NominalFeedbackDividerHandler implements RuleHandler {
    @Override
    public boolean supports(RuleDefinition rule) {
        return rule.type().equals("FB_DIVIDER_NOMINAL");
    }

    @Override
    public RuleResult evaluate(RuleContext context) {
        var rule = context.rule();
        var target = context.target();
        var graph = context.graph();
        var evidence = new ArrayList<RuleResult.Evidence>();
        evidence.add(new RuleResult.Evidence(target.source().display(), target.id() + " model=" + target.model()));
        rule.sources().forEach(s -> evidence.add(new RuleResult.Evidence(
                s.url() + "#page=" + s.page(), s.section() + ": " + s.description())));
        String fb = target.pinNets().get(rule.feedbackPin());
        String ground = target.pinNets().get(rule.groundPin());
        if (fb == null || ground == null) return review(context, "Missing target FB or ground pin; confirm connectivity.", evidence);
        if (!ground.equals(rule.groundNet()) || fb.equals(ground) || fb.equals(rule.outputNet())) {
            return review(context, "Unsupported FB/ground topology; confirm the reference ground and divider.", evidence);
        }
        var index = new CircuitIndex(graph);
        var tops = index.betweenNets(fb, rule.outputNet()).stream().filter(this::isSupportedResistor).toList();
        var bottoms = index.betweenNets(fb, ground).stream().filter(this::isSupportedResistor).toList();
        evidence.add(new RuleResult.Evidence(graph.nets().get(fb).source().display(),
                "FB net " + fb + " endpoints=" + graph.nets().get(fb).pins()));
        graph.nets().get(fb).pins().stream().map(pin -> pin.componentId()).distinct()
                .filter(id -> !id.equals(target.id())).sorted().forEach(id -> {
                    var component = graph.components().get(id);
                    evidence.add(new RuleResult.Evidence(component.source().display(),
                            id + " model=" + component.model() + " pins=" + component.pinNets()));
                });
        if (tops.size() != 1 || bottoms.size() != 1) {
            return review(context, "Expected one supported upper and lower resistor; found "
                    + tops.size() + "/" + bottoms.size() + ". Confirm missing or ambiguous connections.", evidence);
        }
        var top = tops.getFirst();
        var bottom = bottoms.getFirst();
        for (var resistor : List.of(top, bottom)) {
            evidence.add(new RuleResult.Evidence(resistor.source().display(), resistor.id() + " pins=" + resistor.pinNets()));
            var valueSource = resistor.propertySources().get("Value");
            evidence.add(new RuleResult.Evidence(valueSource == null ? resistor.source().display() : valueSource.display(),
                    resistor.id() + " Value=" + resistor.properties().get("Value")));
        }
        var allowed = Set.of(new PinRef(target.id(), rule.feedbackPin()),
                onNet(top, fb), onNet(bottom, fb));
        if (!Set.copyOf(graph.nets().get(fb).pins()).equals(allowed)) {
            return review(context, "Additional FB branches are outside the supported nominal divider model; review them.", evidence);
        }
        try {
            var upper = ElectricalValue.resistanceOhms(top.properties().get("Value"));
            var lower = ElectricalValue.resistanceOhms(bottom.properties().get("Value"));
            if (lower.signum() == 0) return review(context, "Lower resistor is zero; divider calculation is undefined.", evidence);
            var voltage = rule.referenceVoltageV().multiply(
                    BigDecimal.ONE.add(upper.divide(lower, MathContext.DECIMAL128)), MathContext.DECIMAL128);
            var error = voltage.subtract(rule.targetVoltageV()).abs()
                    .divide(rule.targetVoltageV(), MathContext.DECIMAL128);
            var verdict = error.compareTo(rule.toleranceFraction()) <= 0 ? Verdict.PASS : Verdict.FAIL;
            return new RuleResult(target.id(), rule.id(), verdict,
                    "Nominal divider result only; acceptance threshold is defined by the development fixture.",
                    Map.of("referenceVoltageV", rule.referenceVoltageV(), "upperResistanceOhm", upper,
                            "lowerResistanceOhm", lower, "outputVoltageV", voltage,
                            "targetVoltageV", rule.targetVoltageV(), "relativeError", error,
                            "toleranceFraction", rule.toleranceFraction()), evidence);
        } catch (IllegalArgumentException exception) {
            return review(context, exception.getMessage() + "; provide an unambiguous resistance value.", evidence);
        }
    }

    private boolean isSupportedResistor(CircuitComponent component) {
        return component.id().matches("R[0-9]+")
                && (component.model().matches("R[0-9]{4}") || component.model().equals("RESISTOR"));
    }

    private PinRef onNet(CircuitComponent component, String net) {
        return component.pinNets().entrySet().stream().filter(e -> e.getValue().equals(net))
                .map(e -> new PinRef(component.id(), e.getKey())).findFirst().orElseThrow();
    }

    private RuleResult review(RuleContext context, String reason, List<RuleResult.Evidence> evidence) {
        return new RuleResult(context.target().id(), context.rule().id(), Verdict.NEEDS_REVIEW, reason, Map.of(), evidence);
    }
}
