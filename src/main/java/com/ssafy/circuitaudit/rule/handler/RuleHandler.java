package com.ssafy.circuitaudit.rule.handler;

import com.ssafy.circuitaudit.result.domain.RuleResult;
import com.ssafy.circuitaudit.rule.domain.RuleContext;
import com.ssafy.circuitaudit.rule.domain.RuleDefinition;

public interface RuleHandler {
    boolean supports(RuleDefinition rule);
    RuleResult evaluate(RuleContext context);
}
