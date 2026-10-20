-- Read-only examples. Bind :sec_code, :design_id and :run_id in your client.
-- A SEC match finds rules; it does not establish a PASS verdict.

SELECT 'parts' AS table_name, COUNT(*) AS row_count FROM parts
UNION ALL SELECT 'checkpoints', COUNT(*) FROM checkpoints
UNION ALL SELECT 'checkpoint_analyses', COUNT(*) FROM checkpoint_analyses
UNION ALL SELECT 'analysis_checks', COUNT(*) FROM analysis_checks
UNION ALL SELECT 'check_parameters', COUNT(*) FROM check_parameters
UNION ALL SELECT 'check_required_facts', COUNT(*) FROM check_required_facts
UNION ALL SELECT 'check_evidence', COUNT(*) FROM check_evidence
UNION ALL SELECT 'analysis_issues', COUNT(*) FROM analysis_issues
UNION ALL SELECT 'designs', COUNT(*) FROM designs
UNION ALL SELECT 'design_instances', COUNT(*) FROM design_instances
UNION ALL SELECT 'design_artifacts', COUNT(*) FROM design_artifacts
UNION ALL SELECT 'verification_runs', COUNT(*) FROM verification_runs
UNION ALL SELECT 'verification_results', COUNT(*) FROM verification_results
UNION ALL SELECT 'verification_facts', COUNT(*) FROM verification_facts;

-- All matching part groups are retained; SEC is not a unique part_id.
SELECT p.part_id, p.sec_code, p.maker, p.maker_pn,
       cp.checkpoint_id, cp.external_checkpoint_id, cp.source_row_uid,
       cp.checkpoint_text, cp.specification_text, cp.design_template_text,
       cp.ldrc_check_tp, cp.ldrc_regist_tp, cp.ldrc_check_date_serial,
       cp.ldrc_checker_emp_no, cp.ldrc_id,
       ca.analysis_id, ca.version_no, ca.status, ca.summary,
       c.analysis_check_id, c.requirement_id, c.target_kind,
       c.target_description, c.applicability, c.requirement_text, c.level, c.archetype
FROM parts AS p
JOIN checkpoints AS cp ON cp.part_id = p.part_id
JOIN checkpoint_analyses AS ca ON ca.checkpoint_id = cp.checkpoint_id
LEFT JOIN analysis_checks AS c ON c.analysis_id = ca.analysis_id
WHERE p.sec_code = :sec_code
ORDER BY p.part_id, cp.source_row_no, ca.version_no, c.rule_seq;

SELECT p.sec_code, c.requirement_id, v.param_seq, v.param_name,
       v.value_text, v.numeric_value, v.min_value, v.max_value,
       v.unit, v.role, v.qualifier
FROM parts AS p
JOIN checkpoints AS cp ON cp.part_id = p.part_id
JOIN checkpoint_analyses AS ca ON ca.checkpoint_id = cp.checkpoint_id
JOIN analysis_checks AS c ON c.analysis_id = ca.analysis_id
JOIN check_parameters AS v ON v.analysis_check_id = c.analysis_check_id
WHERE p.sec_code = :sec_code
ORDER BY cp.source_row_no, c.rule_seq, v.param_seq;

SELECT p.sec_code, c.requirement_id, f.fact_seq, f.fact_name
FROM parts AS p
JOIN checkpoints AS cp ON cp.part_id = p.part_id
JOIN checkpoint_analyses AS ca ON ca.checkpoint_id = cp.checkpoint_id
JOIN analysis_checks AS c ON c.analysis_id = ca.analysis_id
JOIN check_required_facts AS f ON f.analysis_check_id = c.analysis_check_id
WHERE p.sec_code = :sec_code
ORDER BY cp.source_row_no, c.rule_seq, f.fact_seq;

SELECT cp.source_row_no, ca.status, ca.summary,
       json_extract(ca.raw_analysis_json, '$.error') AS source_error
FROM checkpoint_analyses AS ca
JOIN checkpoints AS cp ON cp.checkpoint_id = ca.checkpoint_id
WHERE ca.status <> 'normalized'
   OR json_type(ca.raw_analysis_json, '$.error') IS NOT NULL
ORDER BY cp.source_row_no;

SELECT r.run_id, i.refdes, p.sec_code, c.requirement_id,
       r.verdict, r.reason_text, r.decided_at
FROM verification_results AS r
JOIN verification_runs AS run ON run.run_id = r.run_id
JOIN design_instances AS i ON i.instance_id = r.instance_id
JOIN parts AS p ON p.part_id = i.part_id
JOIN analysis_checks AS c ON c.analysis_check_id = r.analysis_check_id
WHERE run.design_id = :design_id AND r.run_id = :run_id
ORDER BY i.refdes, c.analysis_check_id;
