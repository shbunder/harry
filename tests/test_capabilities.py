"""The `.harry/` format, tested by breaking it.

A filesystem format costs the guarantee an import gave for free: that a broken declaration
fails loudly and immediately. `scripts/check_capabilities.py` is that guarantee moved to
the gate, so it is tested the way a gate is — by making each rule fail.
"""

from __future__ import annotations

import textwrap

import pytest

import check_capabilities as cap

CONNECTOR = """\
---
name: remarkable
description: The reMarkable Paper Pro
requires_env: [REMARKABLE_DEVICE_TOKEN]
expires: manual
enabled: true
---

How to re-pair when the token stops working.
"""

CLAUDE_JOB = """\
---
name: morning-page
description: The day's page, on the tablet by 07:00
trigger: claude
deadline: "07:00"
requires: [remarkable]
enabled: true
---

Pick the six that matter and call build_digest.
"""

SCHEDULED_JOB = """\
---
name: refresh-feeds
description: Re-fetch every configured feed
trigger: schedule
schedule: "0 5 * * *"
timezone: Europe/Brussels
enabled: true
---
"""


@pytest.fixture
def harry(tmp_path, monkeypatch):
    """A throwaway `.harry/` tree. Returns a writer for either kind."""
    root = tmp_path / '.harry'
    for kind in ('connectors', 'jobs', 'tools'):
        (root / kind).mkdir(parents=True)
    monkeypatch.setattr(cap, 'ROOT', tmp_path)
    monkeypatch.setattr(cap, 'HARRY', root)

    def write(kind: str, name: str, body: str):
        filename = {'connectors': 'CONNECTOR.md', 'jobs': 'JOB.md', 'tools': 'TOOL.md'}[kind]
        folder = root / kind / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(textwrap.dedent(body), encoding='utf-8')
        return folder

    return write


def test_an_empty_tree_is_fine(harry, capsys):
    assert cap.main([]) == 0
    assert 'empty' in capsys.readouterr().out


def test_a_valid_connector_and_both_kinds_of_job_pass(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('jobs', 'morning-page', CLAUDE_JOB)
    harry('jobs', 'refresh-feeds', SCHEDULED_JOB)
    assert cap.main([]) == 0
    assert '1 connector(s), 2 job(s)' in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Every rule, made to fail
# ---------------------------------------------------------------------------


def test_a_folder_with_no_declaration_is_caught(harry, capsys):
    """The failure the filesystem format adds: it looks present and does nothing."""
    (harry('jobs', 'morning-page', CLAUDE_JOB).parent / 'ghost').mkdir()
    assert cap.main([]) == 1
    assert 'no JOB.md' in capsys.readouterr().err


def test_frontmatter_that_is_never_closed_is_caught(harry, capsys):
    harry('jobs', 'x', '---\nname: x\n')
    assert cap.main([]) == 1
    assert 'never closed' in capsys.readouterr().err


def test_a_file_with_no_frontmatter_is_caught(harry, capsys):
    harry('jobs', 'x', 'just some prose\n')
    assert cap.main([]) == 1
    assert 'no YAML frontmatter' in capsys.readouterr().err


def test_broken_yaml_is_caught(harry, capsys):
    harry('jobs', 'x', '---\nname: [unclosed\n---\n')
    assert cap.main([]) == 1
    assert 'not valid YAML' in capsys.readouterr().err


def test_a_name_that_disagrees_with_its_folder_is_caught(harry, capsys):
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('name: morning-page', 'name: evening-page'))
    assert cap.main([]) == 1
    assert 'they must match' in capsys.readouterr().err


def test_an_unknown_trigger_is_caught(harry, capsys):
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('trigger: claude', 'trigger: whenever'))
    assert cap.main([]) == 1
    assert '`trigger` must be one of' in capsys.readouterr().err


def test_a_scheduled_job_with_no_schedule_is_caught(harry, capsys):
    harry('jobs', 'refresh-feeds', SCHEDULED_JOB.replace('schedule: "0 5 * * *"\n', ''))
    assert cap.main([]) == 1
    assert 'no idea when to run it' in capsys.readouterr().err


def test_a_scheduled_job_with_no_timezone_is_caught(harry, capsys):
    """06:30 is a local time. A schedule without a zone moves twice a year."""
    harry('jobs', 'refresh-feeds', SCHEDULED_JOB.replace('timezone: Europe/Brussels\n', ''))
    assert cap.main([]) == 1
    assert '06:30 is a local time' in capsys.readouterr().err


def test_a_claude_triggered_job_may_not_also_carry_a_schedule(harry, capsys):
    """Two clocks that can disagree is the failure the split was designed to remove."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('trigger: claude', 'trigger: claude\nschedule: "30 6 * * *"'))
    assert cap.main([]) == 1
    assert 'a second one that disagrees' in capsys.readouterr().err


def test_a_claude_triggered_job_without_a_deadline_is_caught(harry, capsys):
    """The watchdog is the only thing that notices a trigger that never fired."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('deadline: "07:00"\n', ''))
    assert cap.main([]) == 1
    assert 'cannot report its own absence' in capsys.readouterr().err


def test_a_malformed_deadline_is_caught(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('deadline: "07:00"', 'deadline: "7am"'))
    assert cap.main([]) == 1
    assert '`deadline` must be HH:MM' in capsys.readouterr().err


def test_a_job_requiring_a_connector_that_does_not_exist_is_caught(harry, capsys):
    """Otherwise it is found out at 06:30, by nothing arriving."""
    harry('jobs', 'morning-page', CLAUDE_JOB)
    assert cap.main([]) == 1
    err = capsys.readouterr().err
    assert 'requires connectors that do not exist: remarkable' in err
    assert 'none are declared yet' in err


def test_a_connector_that_does_not_say_whether_it_expires_is_caught(harry, capsys):
    """Two of Harry's three credentials expire. One that nobody declared is one nobody
    watches, and the failure is three quiet weeks."""
    harry('connectors', 'remarkable', CONNECTOR.replace('expires: manual\n', ''))
    assert cap.main([]) == 1
    assert '`expires` is required' in capsys.readouterr().err


def test_an_unknown_expiry_is_caught(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR.replace('expires: manual', 'expires: sometimes'))
    assert cap.main([]) == 1
    assert '`expires` must be one of' in capsys.readouterr().err


def test_requires_env_must_be_environment_variable_names(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR.replace('[REMARKABLE_DEVICE_TOKEN]', '[remarkable_token]'))
    assert cap.main([]) == 1
    assert 'environment variable names' in capsys.readouterr().err


def test_enabled_must_be_a_boolean_not_a_word(harry, capsys):
    """`enabled: "yes"` is a string, and a string is truthy whatever it says."""
    harry('connectors', 'remarkable', CONNECTOR.replace('enabled: true', "enabled: 'no'"))
    assert cap.main([]) == 1
    assert '`enabled` must be bool' in capsys.readouterr().err


def test_every_problem_is_reported_not_just_the_first(harry, capsys):
    """A gate that stops at the first fault costs a round trip per fault."""
    harry('connectors', 'remarkable', CONNECTOR.replace('expires: manual\n', ''))
    harry('jobs', 'morning-page', CLAUDE_JOB.replace('trigger: claude', 'trigger: nonsense'))
    assert cap.main([]) == 1
    err = capsys.readouterr().err
    assert '2 problem(s)' in err


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

TOOL = """\
---
name: digest_list_candidates
namespace: digest
description: Today's weather, agenda and headlines, as a menu to choose from
requires: [remarkable]
always_load: true
annotations:
  readOnlyHint: true
  idempotentHint: true
enabled: true
---

Returns everything today could contain: the weather, the day's agenda, and up to 40
headlines with their summaries and ids. Nothing is chosen for you — pick the six to eight
that matter and pass their ids to `digest_build`. Reach for this first, every morning.
"""


def test_a_valid_tool_passes(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL)
    assert cap.main([]) == 0
    assert '1 tool(s) — 1 always loaded' in capsys.readouterr().out


def test_a_tool_name_must_carry_its_namespace(harry, capsys):
    """The prefix is how the model tells one owner's tools from another's."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'list_candidates', TOOL.replace('name: digest_list_candidates', 'name: list_candidates'))
    assert cap.main([]) == 1
    assert 'must start with its namespace' in capsys.readouterr().err


def test_a_dotted_tool_name_is_refused(harry, capsys):
    """MCP permits dots; the Claude API's own validation is narrower. Underscores travel."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest.list', TOOL.replace('name: digest_list_candidates', 'name: digest.list'))
    assert cap.main([]) == 1
    assert 'lowercase letters, digits and underscores' in capsys.readouterr().err


def test_a_tool_with_no_read_only_hint_is_refused(harry, capsys):
    """Nothing else carries the signal that separates a feed read from a tablet push."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL.replace('  readOnlyHint: true\n', ''))
    assert cap.main([]) == 1
    assert 'readOnlyHint' in capsys.readouterr().err


def test_an_unknown_annotation_is_refused(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL.replace('idempotentHint: true', 'safeHint: true'))
    assert cap.main([]) == 1
    assert 'unknown annotation' in capsys.readouterr().err


def test_a_tool_with_an_empty_description_body_is_refused(harry, capsys):
    """The body is what Claude reads to decide whether to call this tool — the
    highest-leverage prose in the repo, and the easiest to leave blank."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL.partition('---\n\n')[0] + '---\n\nTODO\n')
    assert cap.main([]) == 1
    assert 'nearly empty' in capsys.readouterr().err


def test_deferring_every_tool_is_refused(harry, capsys):
    """The API rejects a roster with nothing loaded. Catching it here beats catching it on
    the first call of the morning."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL.replace('always_load: true', 'always_load: false'))
    assert cap.main([]) == 1
    assert 'every tool is deferred' in capsys.readouterr().err


def test_one_loaded_tool_is_enough(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL)
    harry(
        'tools',
        'digest_build',
        TOOL.replace('name: digest_list_candidates', 'name: digest_build').replace(
            'always_load: true', 'always_load: false'
        ),
    )
    assert cap.main([]) == 0
    assert '2 tool(s) — 1 always loaded' in capsys.readouterr().out


def test_a_disabled_tool_does_not_count_as_loaded(harry, capsys):
    """`always_load: true, enabled: false` is not in the roster at all."""
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL.replace('enabled: true', 'enabled: false'))
    assert cap.main([]) == 1
    assert 'every tool is deferred or disabled' in capsys.readouterr().err


def test_a_tool_requiring_a_connector_that_does_not_exist_is_caught(harry, capsys):
    harry('tools', 'digest_list_candidates', TOOL)
    assert cap.main([]) == 1
    assert 'requires connectors that do not exist: remarkable' in capsys.readouterr().err


def test_a_tool_folder_with_no_declaration_is_caught(harry, capsys):
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL)
    ((harry('tools', 'digest_build', TOOL)).parent / 'ghost').mkdir()
    assert cap.main([]) == 1
    assert 'no TOOL.md' in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Config per implementation — a capability declares, the deployment supplies
# ---------------------------------------------------------------------------

CONFIGURED = """\
---
name: icloud
description: Apple calendar and reminders over CalDAV
expires: manual
enabled: true
config:
  username:
    description: Your Apple ID
    required: true
  app_password:
    description: App-specific password from appleid.apple.com
    secret: true
    required: true
  calendars:
    description: Which calendars to read. Empty means all.
    default: []
---

How to renew the app-specific password when it stops working.
"""


def test_a_capability_declares_its_own_settings(harry, capsys):
    harry('connectors', 'icloud', CONFIGURED)
    assert cap.main([]) == 0


def test_the_env_key_is_derived_from_the_implementation_name():
    """Two connectors can both want `api_key` and never collide, and a third party can add
    one without knowing which names are taken."""
    from harry.config import env_key

    assert env_key('icloud', 'app_password') == 'HARRY_ICLOUD_APP_PASSWORD'
    assert env_key('daily-digest', 'article_limit') == 'HARRY_DAILY_DIGEST_ARTICLE_LIMIT'


def test_the_validator_and_harry_derive_the_same_key():
    """One definition, imported — not two implementations of the same rule."""
    from harry.config import env_key as canonical

    assert cap.env_key is canonical


def test_a_setting_with_no_description_is_refused(harry, capsys):
    """It becomes the comment beside the key in the generated .env, and that file is the
    only place anyone finds out the setting exists."""
    harry('connectors', 'icloud', CONFIGURED.replace('    description: Your Apple ID\n', ''))
    assert cap.main([]) == 1
    err = capsys.readouterr().err
    assert '`description` is required' in err
    assert 'HARRY_ICLOUD_USERNAME' in err


def test_a_required_setting_may_not_also_have_a_default(harry, capsys):
    """Required means Harry cannot start this capability without a value."""
    both = CONFIGURED.replace(
        '  username:\n    description: Your Apple ID\n    required: true\n',
        '  username:\n    description: Your Apple ID\n    required: true\n    default: someone@example.com\n',
    )
    harry('connectors', 'icloud', both)
    assert cap.main([]) == 1
    assert 'so it is not `required`' in capsys.readouterr().err


def test_a_secret_may_not_carry_a_default(harry, capsys):
    """That default is a credential, in a committed file."""
    harry(
        'connectors',
        'icloud',
        CONFIGURED.replace('    secret: true\n    required: true', '    secret: true\n    default: hunter2'),
    )
    assert cap.main([]) == 1
    assert 'that default is a credential' in capsys.readouterr().err


def test_a_malformed_setting_name_is_refused(harry, capsys):
    harry('connectors', 'icloud', CONFIGURED.replace('  username:', '  User-Name:'))
    assert cap.main([]) == 1
    assert 'lowercase with underscores' in capsys.readouterr().err


def test_a_job_and_a_tool_may_declare_config_too(harry, capsys):
    """`article_limit` is a setting exactly one job reads. It has no business being global."""
    job = SCHEDULED_JOB.replace(
        'enabled: true\n',
        'enabled: true\nconfig:\n  article_limit:\n    description: 6-8 is a readable morning\n    default: 8\n',
    )
    harry('jobs', 'refresh-feeds', job)
    harry('connectors', 'remarkable', CONNECTOR)
    harry('tools', 'digest_list_candidates', TOOL)
    assert cap.main([]) == 0
