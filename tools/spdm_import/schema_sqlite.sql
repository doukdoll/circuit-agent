-- Circuit-review AI: SQLite 3.31+ with JSON1.
-- PRAGMA foreign_keys must be enabled on every application connection.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS parts (
    part_id INTEGER PRIMARY KEY,
    adminno TEXT NOT NULL CHECK (length(adminno) = 10 AND adminno NOT GLOB '*[^0-9]*'),
    part_seqno INTEGER NOT NULL CHECK (part_seqno >= 0),
    sec_code TEXT NOT NULL,
    writer_emp_no TEXT NOT NULL CHECK (length(writer_emp_no) = 8 AND writer_emp_no NOT GLOB '*[^0-9]*'),
    comp_date_serial TEXT NOT NULL,
    maker TEXT,
    maker_pn TEXT,
    ldrc_check_tp TEXT CHECK (ldrc_check_tp IS NULL OR ldrc_check_tp IN ('Y', 'N')),
    ldrc_regist_tp TEXT CHECK (ldrc_regist_tp IS NULL OR ldrc_regist_tp IN ('Y', 'N', 'B')),
    ldrc_check_date_serial TEXT,
    ldrc_checker_emp_no TEXT CHECK (ldrc_checker_emp_no IS NULL OR length(ldrc_checker_emp_no) = 8),
    ldrc_id TEXT,
    UNIQUE (adminno, part_seqno)
);
CREATE INDEX IF NOT EXISTS idx_parts_sec_code ON parts(sec_code);
CREATE INDEX IF NOT EXISTS idx_parts_maker_pn ON parts(maker, maker_pn);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id INTEGER PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(part_id) ON DELETE CASCADE,
    checkpoint_seqno INTEGER NOT NULL CHECK (checkpoint_seqno >= 0),
    checkpoint_text TEXT,
    specification_text TEXT,
    design_template_text TEXT,
    reference_document TEXT,
    input_emp_no TEXT NOT NULL CHECK (length(input_emp_no) = 8 AND input_emp_no NOT GLOB '*[^0-9]*'),
    savefolder TEXT GENERATED ALWAYS AS (CAST(checkpoint_seqno AS TEXT) || 'L') STORED,
    ref_date_serial TEXT NOT NULL,
    category TEXT CHECK (category IS NULL OR category IN ('a', 'b', 'c')),
    pin_info TEXT,
    external_checkpoint_id TEXT,
    source_row_uid TEXT UNIQUE,
    source_file_name TEXT,
    source_row_no INTEGER,
    raw_row_json TEXT CHECK (raw_row_json IS NULL OR json_valid(raw_row_json)),
    UNIQUE (part_id, checkpoint_seqno)
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_part ON checkpoints(part_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_category ON checkpoints(category);

CREATE TABLE IF NOT EXISTS checkpoint_analyses (
    analysis_id INTEGER PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
    summary TEXT,
    model_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'normalized', 'needs_review', 'error')),
    raw_analysis_json TEXT CHECK (raw_analysis_json IS NULL OR json_valid(raw_analysis_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (checkpoint_id, version_no)
);
CREATE INDEX IF NOT EXISTS idx_checkpoint_analyses_status ON checkpoint_analyses(status);

CREATE TABLE IF NOT EXISTS analysis_checks (
    analysis_check_id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES checkpoint_analyses(analysis_id) ON DELETE CASCADE,
    requirement_id TEXT NOT NULL,
    rule_seq INTEGER NOT NULL CHECK (rule_seq >= 1),
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'power_pin','input_pin','control_pin','bidirectional_pin',
        'signal','component','circuit','unknown'
    )),
    target_description TEXT NOT NULL,
    applicability TEXT,
    requirement_text TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('mandatory','recommended','informational')),
    archetype TEXT NOT NULL DEFAULT 'other' CHECK (archetype IN (
        'power_rail','decap','pull_up_down','unused_pin',
        'power_sequencing','signal_integrity','other'
    )),
    UNIQUE (analysis_id, requirement_id),
    UNIQUE (analysis_id, rule_seq)
);
CREATE INDEX IF NOT EXISTS idx_analysis_checks_analysis ON analysis_checks(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_checks_archetype ON analysis_checks(archetype);

CREATE TABLE IF NOT EXISTS check_parameters (
    parameter_id INTEGER PRIMARY KEY,
    analysis_check_id INTEGER NOT NULL REFERENCES analysis_checks(analysis_check_id) ON DELETE CASCADE,
    param_seq INTEGER NOT NULL CHECK (param_seq >= 1),
    param_name TEXT NOT NULL,
    value_text TEXT,
    numeric_value REAL,
    min_value REAL,
    max_value REAL,
    unit TEXT,
    role TEXT NOT NULL CHECK (role IN ('expected','limit','recommended','unknown')),
    qualifier TEXT CHECK (qualifier IS NULL OR qualifier IN ('<','<=','=','>=','>','typical','range')),
    UNIQUE (analysis_check_id, param_seq),
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);
CREATE INDEX IF NOT EXISTS idx_check_parameters_check ON check_parameters(analysis_check_id);

CREATE TABLE IF NOT EXISTS check_required_facts (
    required_fact_id INTEGER PRIMARY KEY,
    analysis_check_id INTEGER NOT NULL REFERENCES analysis_checks(analysis_check_id) ON DELETE CASCADE,
    fact_seq INTEGER NOT NULL CHECK (fact_seq >= 1),
    fact_name TEXT NOT NULL,
    UNIQUE (analysis_check_id, fact_seq)
);

CREATE TABLE IF NOT EXISTS check_evidence (
    evidence_id INTEGER PRIMARY KEY,
    analysis_check_id INTEGER NOT NULL REFERENCES analysis_checks(analysis_check_id) ON DELETE CASCADE,
    evidence_seq INTEGER NOT NULL CHECK (evidence_seq >= 1),
    source_field TEXT NOT NULL CHECK (source_field IN (
        'checkpoint','specification','design_template','reference_document'
    )),
    quote_text TEXT NOT NULL,
    UNIQUE (analysis_check_id, evidence_seq)
);

CREATE TABLE IF NOT EXISTS analysis_issues (
    issue_id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES checkpoint_analyses(analysis_id) ON DELETE CASCADE,
    issue_seq INTEGER NOT NULL CHECK (issue_seq >= 1),
    code TEXT NOT NULL CHECK (code IN (
        'contradiction','missing_scope','missing_reference_table',
        'ambiguous','missing_design_context','other'
    )),
    description TEXT NOT NULL,
    UNIQUE (analysis_id, issue_seq)
);

CREATE TABLE IF NOT EXISTS designs (
    design_id INTEGER PRIMARY KEY,
    design_name TEXT NOT NULL,
    revision TEXT NOT NULL,
    description TEXT,
    UNIQUE (design_name, revision)
);

CREATE TABLE IF NOT EXISTS design_instances (
    instance_id INTEGER PRIMARY KEY,
    design_id INTEGER NOT NULL REFERENCES designs(design_id) ON DELETE CASCADE,
    part_id INTEGER NOT NULL REFERENCES parts(part_id),
    refdes TEXT NOT NULL,
    UNIQUE (design_id, refdes)
);
CREATE INDEX IF NOT EXISTS idx_design_instances_part ON design_instances(part_id);

CREATE TABLE IF NOT EXISTS design_artifacts (
    artifact_id INTEGER PRIMARY KEY,
    design_id INTEGER NOT NULL REFERENCES designs(design_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('BOM','NETLIST','SCHEMATIC','PCB_LAYOUT','DATASHEET','OTHER')),
    file_name TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64),
    uploaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_design_artifacts_design ON design_artifacts(design_id);

CREATE TABLE IF NOT EXISTS verification_runs (
    run_id INTEGER PRIMARY KEY,
    design_id INTEGER NOT NULL REFERENCES designs(design_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED')),
    model_name TEXT,
    config_json TEXT CHECK (config_json IS NULL OR json_valid(config_json)),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_verification_runs_design ON verification_runs(design_id);

CREATE TABLE IF NOT EXISTS verification_results (
    result_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES verification_runs(run_id) ON DELETE CASCADE,
    instance_id INTEGER NOT NULL REFERENCES design_instances(instance_id),
    analysis_check_id INTEGER NOT NULL REFERENCES analysis_checks(analysis_check_id),
    verdict TEXT NOT NULL CHECK (verdict IN (
        'PASS','FAIL','INSUFFICIENT_EVIDENCE','NOT_APPLICABLE','NEEDS_REVIEW','ERROR'
    )),
    reason_text TEXT,
    decided_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (run_id, instance_id, analysis_check_id)
);
CREATE INDEX IF NOT EXISTS idx_verification_results_check ON verification_results(analysis_check_id);
CREATE INDEX IF NOT EXISTS idx_verification_results_verdict ON verification_results(verdict);

CREATE TABLE IF NOT EXISTS verification_facts (
    verification_fact_id INTEGER PRIMARY KEY,
    result_id INTEGER NOT NULL REFERENCES verification_results(result_id) ON DELETE CASCADE,
    required_fact_id INTEGER REFERENCES check_required_facts(required_fact_id),
    source_artifact_id INTEGER REFERENCES design_artifacts(artifact_id),
    subject_refdes TEXT,
    observed_text TEXT,
    numeric_value REAL,
    unit TEXT,
    source_locator TEXT,
    evidence_excerpt TEXT,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);
CREATE INDEX IF NOT EXISTS idx_verification_facts_result ON verification_facts(result_id);

CREATE TRIGGER IF NOT EXISTS trg_verification_result_match_insert
BEFORE INSERT ON verification_results
BEGIN
    SELECT CASE WHEN
      (SELECT design_id FROM verification_runs WHERE run_id = NEW.run_id) <>
      (SELECT design_id FROM design_instances WHERE instance_id = NEW.instance_id)
      THEN RAISE(ABORT, 'verification result run / instance design mismatch')
    END;
    SELECT CASE WHEN
      (SELECT part_id FROM design_instances WHERE instance_id = NEW.instance_id) <>
      (SELECT cp.part_id
         FROM analysis_checks c
         JOIN checkpoint_analyses ca ON ca.analysis_id = c.analysis_id
         JOIN checkpoints cp ON cp.checkpoint_id = ca.checkpoint_id
        WHERE c.analysis_check_id = NEW.analysis_check_id)
      THEN RAISE(ABORT, 'verification rule is not defined for instance part')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trg_verification_result_match_update
BEFORE UPDATE OF run_id, instance_id, analysis_check_id ON verification_results
BEGIN
    SELECT CASE WHEN
      (SELECT design_id FROM verification_runs WHERE run_id = NEW.run_id) <>
      (SELECT design_id FROM design_instances WHERE instance_id = NEW.instance_id)
      THEN RAISE(ABORT, 'verification result run / instance design mismatch')
    END;
    SELECT CASE WHEN
      (SELECT part_id FROM design_instances WHERE instance_id = NEW.instance_id) <>
      (SELECT cp.part_id
         FROM analysis_checks c
         JOIN checkpoint_analyses ca ON ca.analysis_id = c.analysis_id
         JOIN checkpoints cp ON cp.checkpoint_id = ca.checkpoint_id
        WHERE c.analysis_check_id = NEW.analysis_check_id)
      THEN RAISE(ABORT, 'verification rule is not defined for instance part')
    END;
END;
