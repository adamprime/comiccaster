"""Tests for check_vulnerabilities.py.

The OSV database and `pip list` are mocked throughout, so the suite never
touches the network or the real venv. OSV payloads below are trimmed copies of
real responses for the brotli advisory that motivated this check (#243).

Two behaviours matter more than the rest:

  * an audit that could not finish must never read as clean, and
  * an OSV outage must only warn (exit 75), never open an issue.
"""

import os
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts import check_vulnerabilities as cv
from scripts.check_vulnerabilities import (
    EX_UNREACHABLE,
    OSV_QUERYBATCH_URL,
    AuditError,
    AuditUnreachable,
    audit,
    evaluate,
    list_installed,
    main,
    osv_request,
    parse_pip_list,
    query_osv,
)

PYTHON = '/host/venv/bin/python'

BROTLI_GHSA = {
    'id': 'GHSA-9v8h-qqgm-4m35',
    'summary': 'Brotli: Out-of-bounds write in the Brotli decoder',
    'aliases': ['CVE-2026-111497', 'PYSEC-2026-4322', 'PYSEC-2026-4323'],
    'withdrawn': None,
    'affected': [
        {
            'package': {'name': 'brotli', 'ecosystem': 'PyPI'},
            'ranges': [{'type': 'ECOSYSTEM',
                        'events': [{'introduced': '1.0.3'}, {'fixed': '1.2.1'}]}],
        },
        {
            'package': {'name': 'brotlicffi', 'ecosystem': 'PyPI'},
            'ranges': [{'type': 'ECOSYSTEM',
                        'events': [{'introduced': '1.0.3'}, {'fixed': '1.2.1.0'}]}],
        },
    ],
}

BROTLI_PYSEC = {
    'id': 'PYSEC-2026-4322',
    'summary': 'Out-of-bounds write in the Brotli decoder',
    'aliases': ['CVE-2026-111497', 'GHSA-9v8h-qqgm-4m35', 'PYSEC-2026-4323'],
    'withdrawn': None,
    'affected': [{
        'package': {'name': 'brotli', 'ecosystem': 'PyPI'},
        'ranges': [{'type': 'ECOSYSTEM',
                    'events': [{'introduced': '0'}, {'fixed': '1.2.1'}]}],
    }],
}

BROTLI_HITS = {'vulns': [
    {'id': 'GHSA-9v8h-qqgm-4m35', 'modified': '2026-10-24T10:55:42Z'},
    {'id': 'PYSEC-2026-4322', 'modified': '2026-10-24T10:55:42Z'},
]}

PACKAGES = [('brotli', '1.2.0'), ('requests', '2.34.2')]


class FakeOsv:
    """Stands in for `osv_request`: answers the batch query and vuln lookups."""

    def __init__(self, batch=None, vulns=None, fail=None):
        self.batch = batch
        self.vulns = vulns or {}
        self.fail = fail or {}
        self.calls = []

    def __call__(self, url, payload=None):
        self.calls.append((url, payload))
        if url in self.fail:
            raise self.fail[url]
        if url == OSV_QUERYBATCH_URL:
            return self.batch
        return self.vulns[url.rsplit('/', 1)[-1]]


@pytest.fixture
def osv(monkeypatch):
    """Install a FakeOsv; tests fill in its answers."""
    fake = FakeOsv()
    monkeypatch.setattr(cv, 'osv_request', fake)
    return fake


class TestParsePipList:
    def test_names_are_canonicalized_for_osv(self):
        raw = ('[{"name": "Brotli", "version": "1.2.0"},'
               ' {"name": "typing_extensions", "version": "4.16.0"}]')
        assert parse_pip_list(raw) == [
            ('brotli', '1.2.0'),
            ('typing-extensions', '4.16.0'),
        ]

    @pytest.mark.parametrize('raw', ['', 'not json', '{"name": "x"}', '[{"name": "x"}]'])
    def test_unparseable_output_is_an_error(self, raw):
        with pytest.raises(AuditError):
            parse_pip_list(raw)


class TestListInstalled:
    def test_lists_the_given_interpreter_without_editables(self, monkeypatch):
        """--exclude-editable matters: comiccaster itself is not on PyPI, so
        querying its name could match an unrelated project's advisories."""
        seen = {}

        def fake_run(cmd, **kwargs):
            seen['cmd'] = cmd
            return _completed(stdout='[{"name": "requests", "version": "2.34.2"}]')

        monkeypatch.setattr(cv.subprocess, 'run', fake_run)
        assert list_installed(PYTHON) == [('requests', '2.34.2')]
        assert seen['cmd'] == [
            PYTHON, '-m', 'pip', 'list', '--format=json', '--exclude-editable',
        ]

    def test_pip_failure_is_an_error(self, monkeypatch):
        monkeypatch.setattr(
            cv.subprocess, 'run',
            lambda cmd, **kw: _completed(returncode=1, stderr='No module named pip'),
        )
        with pytest.raises(AuditError, match='No module named pip'):
            list_installed(PYTHON)

    def test_missing_interpreter_is_an_error(self, monkeypatch):
        def boom(cmd, **kwargs):
            raise FileNotFoundError(cmd[0])

        monkeypatch.setattr(cv.subprocess, 'run', boom)
        with pytest.raises(AuditError):
            list_installed(PYTHON)


class TestQueryOsv:
    def test_sends_one_pypi_query_per_package(self, osv):
        osv.batch = {'results': [{}, {}]}
        query_osv(PACKAGES)
        url, payload = osv.calls[0]
        assert url == OSV_QUERYBATCH_URL
        assert payload == {'queries': [
            {'package': {'name': 'brotli', 'ecosystem': 'PyPI'}, 'version': '1.2.0'},
            {'package': {'name': 'requests', 'ecosystem': 'PyPI'}, 'version': '2.34.2'},
        ]}

    def test_returns_only_packages_with_known_vulns(self, osv):
        osv.batch = {'results': [BROTLI_HITS, {}]}
        assert query_osv(PACKAGES) == {
            ('brotli', '1.2.0'): ['GHSA-9v8h-qqgm-4m35', 'PYSEC-2026-4322'],
        }

    def test_short_results_list_is_an_error(self, osv):
        """Zipping a short answer would silently drop packages from the audit."""
        osv.batch = {'results': [{}]}
        with pytest.raises(AuditError, match='1 results for 2 packages'):
            query_osv(PACKAGES)

    @pytest.mark.parametrize('batch', [
        {},
        {'results': 'nope'},
        {'results': [{'vulns': [{'no-id': 1}]}, {}]},
        [],
    ])
    def test_malformed_response_is_an_error(self, osv, batch):
        osv.batch = batch
        with pytest.raises(AuditError):
            query_osv(PACKAGES)


class TestAudit:
    def test_clean_venv_has_no_findings(self, osv):
        osv.batch = {'results': [{}, {}]}
        assert audit(PACKAGES) == []

    def test_aliases_collapse_into_one_finding(self, osv):
        """GHSA and PYSEC both describe CVE-2026-111497: report it once."""
        osv.batch = {'results': [BROTLI_HITS, {}]}
        osv.vulns = {'GHSA-9v8h-qqgm-4m35': BROTLI_GHSA, 'PYSEC-2026-4322': BROTLI_PYSEC}

        [(name, version, findings)] = audit(PACKAGES)

        assert (name, version) == ('brotli', '1.2.0')
        assert len(findings) == 1
        assert findings[0]['label'] == 'CVE-2026-111497'
        assert findings[0]['id'] == 'GHSA-9v8h-qqgm-4m35'
        # Only brotli's own fix version, not brotlicffi's from the same advisory.
        assert findings[0]['fixed'] == ['1.2.1']
        # The alias was already covered, so its details were never fetched.
        assert [u for u, _ in osv.calls if 'PYSEC' in u] == []

    def test_withdrawn_advisory_is_ignored(self, osv):
        osv.batch = {'results': [{'vulns': [{'id': 'GHSA-gone'}]}, {}]}
        osv.vulns = {'GHSA-gone': {'id': 'GHSA-gone', 'withdrawn': '2026-10-01T00:00:00Z'}}
        assert audit(PACKAGES) == []

    def test_unfetchable_details_still_report_the_vuln(self, osv):
        """The batch query already proved the finding; details only make it
        actionable, so losing them must not lose the finding."""
        osv.batch = {'results': [{'vulns': [{'id': 'GHSA-9v8h-qqgm-4m35'}]}, {}]}
        osv.fail = {
            cv.OSV_VULN_URL.format('GHSA-9v8h-qqgm-4m35'): AuditUnreachable('timed out'),
        }
        [(name, _, findings)] = audit(PACKAGES)
        assert name == 'brotli'
        assert findings[0]['label'] == 'GHSA-9v8h-qqgm-4m35'
        assert findings[0]['fixed'] == []

    def test_empty_package_list_is_an_error(self, osv):
        """An audit of nothing is not a clean audit."""
        with pytest.raises(AuditError):
            audit([])
        assert osv.calls == []

    def test_unreachable_batch_query_propagates(self, osv):
        osv.fail = {OSV_QUERYBATCH_URL: AuditUnreachable('connection refused')}
        with pytest.raises(AuditUnreachable):
            audit(PACKAGES)


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=''):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError('not json')
        return self._body


class TestOsvRequest:
    """Which failures are transient (warn) and which mean the check is broken
    (alert). A broken check that only warned would leave the host unaudited
    indefinitely while every run read green."""

    def test_posts_payload_and_returns_json(self, monkeypatch):
        seen = {}

        def fake_post(url, json=None, timeout=None):
            seen.update(url=url, json=json, timeout=timeout)
            return FakeResponse(body={'results': []})

        monkeypatch.setattr(cv.requests, 'post', fake_post)
        assert osv_request(OSV_QUERYBATCH_URL, {'queries': []}) == {'results': []}
        assert seen['json'] == {'queries': []}
        assert seen['timeout']

    def test_get_without_payload(self, monkeypatch):
        monkeypatch.setattr(
            cv.requests, 'get', lambda url, timeout=None: FakeResponse(body={'id': 'X'})
        )
        assert osv_request('https://api.osv.dev/v1/vulns/X') == {'id': 'X'}

    @pytest.mark.parametrize('exc', [
        requests.ConnectionError('Failed to resolve api.osv.dev'),
        requests.Timeout('read timed out'),
        requests.exceptions.ChunkedEncodingError('connection reset'),
    ])
    def test_network_errors_are_unreachable(self, monkeypatch, exc):
        def boom(*args, **kwargs):
            raise exc

        monkeypatch.setattr(cv.requests, 'post', boom)
        with pytest.raises(AuditUnreachable):
            osv_request(OSV_QUERYBATCH_URL, {})

    @pytest.mark.parametrize('status', [429, 500, 502, 503])
    def test_server_side_trouble_is_unreachable(self, monkeypatch, status):
        monkeypatch.setattr(
            cv.requests, 'post', lambda *a, **k: FakeResponse(status_code=status)
        )
        with pytest.raises(AuditUnreachable):
            osv_request(OSV_QUERYBATCH_URL, {})

    def test_rejected_query_is_a_broken_check(self, monkeypatch):
        """A 4xx repeats every day: our request is wrong, not the network."""
        monkeypatch.setattr(
            cv.requests, 'post', lambda *a, **k: FakeResponse(status_code=400)
        )
        with pytest.raises(AuditError) as info:
            osv_request(OSV_QUERYBATCH_URL, {})
        assert not isinstance(info.value, AuditUnreachable)

    def test_tls_failure_is_a_broken_check(self, monkeypatch):
        """SSLError subclasses ConnectionError in requests, but a certificate
        failure is not transient, so it must alert rather than warn."""
        def boom(*args, **kwargs):
            raise requests.exceptions.SSLError('certificate verify failed')

        monkeypatch.setattr(cv.requests, 'post', boom)
        with pytest.raises(AuditError) as info:
            osv_request(OSV_QUERYBATCH_URL, {})
        assert not isinstance(info.value, AuditUnreachable)

    def test_non_json_body_is_a_broken_check(self, monkeypatch):
        monkeypatch.setattr(
            cv.requests, 'post', lambda *a, **k: FakeResponse(text='<html>')
        )
        with pytest.raises(AuditError) as info:
            osv_request(OSV_QUERYBATCH_URL, {})
        assert not isinstance(info.value, AuditUnreachable)


class TestEvaluate:
    def test_clean_report_names_what_was_audited(self):
        status, detail = evaluate([], 47, PYTHON)
        assert status == 'ok'
        assert '47 packages' in detail
        assert PYTHON in detail

    def test_vulnerable_report_says_what_to_upgrade(self):
        findings = [{
            'id': 'GHSA-9v8h-qqgm-4m35', 'label': 'CVE-2026-111497',
            'summary': 'Out-of-bounds write in the Brotli decoder', 'fixed': ['1.2.1'],
        }]
        status, detail = evaluate([('brotli', '1.2.0', findings)], 47, PYTHON)
        assert status == 'vulnerable'
        assert 'brotli 1.2.0' in detail
        assert 'CVE-2026-111497' in detail
        assert 'GHSA-9v8h-qqgm-4m35' in detail
        assert 'fixed in 1.2.1' in detail
        assert 'constraints.txt' in detail

    def test_no_known_fix_is_said_plainly(self):
        findings = [{'id': 'GHSA-x', 'label': 'GHSA-x', 'summary': '', 'fixed': []}]
        _, detail = evaluate([('brotli', '1.2.0', findings)], 1, PYTHON)
        assert 'no fixed version' in detail


class TestMain:
    @pytest.fixture
    def installed(self, monkeypatch):
        seen = {}

        def fake_list(python):
            seen['python'] = python
            return list(PACKAGES)

        monkeypatch.setattr(cv, 'list_installed', fake_list)
        return seen

    def test_exit_zero_when_clean(self, installed, osv, capsys):
        osv.batch = {'results': [{}, {}]}
        assert main(['--python', PYTHON]) == 0
        out = capsys.readouterr().out
        assert '✅' in out
        assert PYTHON in out
        assert installed['python'] == PYTHON

    def test_defaults_to_the_running_interpreter(self, installed, osv):
        """The pipeline runs this from the activated host venv."""
        osv.batch = {'results': [{}, {}]}
        main([])
        assert installed['python'] == sys.executable

    def test_exit_one_when_vulnerable(self, installed, osv, capsys):
        osv.batch = {'results': [BROTLI_HITS, {}]}
        osv.vulns = {'GHSA-9v8h-qqgm-4m35': BROTLI_GHSA, 'PYSEC-2026-4322': BROTLI_PYSEC}
        assert main(['--python', PYTHON]) == 1
        out = capsys.readouterr().out
        assert '❌' in out
        assert 'brotli 1.2.0' in out

    def test_unreachable_database_only_warns(self, installed, osv, capsys):
        osv.fail = {OSV_QUERYBATCH_URL: AuditUnreachable('Failed to resolve api.osv.dev')}
        assert main(['--python', PYTHON]) == EX_UNREACHABLE == 75
        out = capsys.readouterr().out
        assert '⚠️' in out
        assert 'Failed to resolve api.osv.dev' in out

    def test_broken_audit_alerts(self, monkeypatch, capsys):
        """A probe that failed to run must never read as healthy."""
        def broken(python):
            raise AuditError('pip list failed')

        monkeypatch.setattr(cv, 'list_installed', broken)
        assert main(['--python', PYTHON]) == 1
        assert '❌' in capsys.readouterr().out

    def test_has_no_detail_only_flag(self, installed, osv):
        """Security guard, not a style preference.

        The alert this drives opens an issue on a public repository, and the
        specifics -- which package on the host is exploitable, by which CVE --
        are exactly what should not be advertised there while the hole is open.
        Like check_host_config.py, the findings stay in the local run log.
        """
        osv.batch = {'results': [{}, {}]}
        with pytest.raises(SystemExit):
            main(['--detail-only'])


class TestPipelineWiring:
    """The audit's alert only closes itself if Pass 1 lists the slug as covered."""

    SCRIPT = Path(__file__).parent.parent / 'scripts' / 'local_master_update.sh'

    def test_pass1_covers_the_vulnaudit_slug(self):
        covered = next(
            line for line in self.SCRIPT.read_text().splitlines()
            if line.startswith('ALERT_COVERED=')
        )
        assert 'vulnaudit' in covered.split('=', 1)[1].strip('"').split(',')

    def test_pass1_runs_the_audit(self):
        assert 'scripts/check_vulnerabilities.py' in self.SCRIPT.read_text()


def _completed(returncode=0, stdout='', stderr=''):
    import subprocess
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)
