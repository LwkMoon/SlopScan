from __future__ import annotations

import json

from typer.testing import CliRunner

from slopscan.cli.app import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "slopscan" in result.output


def test_help_shows_analyze_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output


def test_rules_list_command():
    result = runner.invoke(app, ["rules", "list"])
    assert result.exit_code == 0
    assert "visual.gradient.overuse" in result.output


def test_rules_show_valid_rule():
    result = runner.invoke(app, ["rules", "show", "visual.gradient.overuse"])
    assert result.exit_code == 0
    assert "Gradients are not inherently AI-generated" in result.output


def test_rules_show_invalid_rule_exits_with_usage_error():
    result = runner.invoke(app, ["rules", "show", "nonexistent.rule"])
    assert result.exit_code == 2


def test_analyze_local_dir_terminal_format(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir)])
    assert result.exit_code == 0
    assert "AI-SLOP LIKELIHOOD" in result.output
    assert "CONFIDENCE" in result.output
    assert "does NOT prove AI authorship" in result.output.replace("\n", " ")


def test_analyze_json_format_is_valid_json(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "slop_score" in data
    assert "confidence" in data
    assert isinstance(data["findings"], list)


def test_analyze_nonexistent_path_exits_3():
    result = runner.invoke(app, ["analyze", "/path/does/not/exist/xyz123"])
    assert result.exit_code == 3


def test_analyze_invalid_format_exits_2(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "yaml"])
    assert result.exit_code == 2


def test_analyze_fail_under_triggers_exit_1(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--fail-under", "1", "--format", "json"])
    assert result.exit_code == 1


def test_analyze_fail_under_not_triggered_exits_0(human_portfolio_dir):
    result = runner.invoke(app, ["analyze", str(human_portfolio_dir), "--fail-under", "90", "--format", "json"])
    assert result.exit_code == 0


def test_analyze_output_to_file(generic_saas_dir, tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "json", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "slop_score" in data


def test_analyze_markdown_format(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "markdown"])
    assert result.exit_code == 0
    assert "# SlopScan report" in result.output


def test_analyze_html_format(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "html"])
    assert result.exit_code == 0
    assert "<!doctype html>" in result.output.lower()


def test_analyze_severity_filter(generic_saas_dir):
    result = runner.invoke(app, ["analyze", str(generic_saas_dir), "--format", "json", "--severity", "high"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    for f in data["findings"]:
        assert f["severity"] in ("high", "critical")


def test_doctor_command_runs():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "rules registered" in result.output
