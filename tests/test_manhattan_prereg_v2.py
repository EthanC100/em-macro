"""Version 2 of the simulation pre-registration and Protocol v3.1: the recorded hashes and the check that reads
them (manhattan/prereg_v2.py). The companion of tests/test_manhattan_prereg.py, which guards version 1.

Like that file, these checks of hand-edited files fail in a session and skip, with a message, inside a writer's
workflow (manhattan/testing.py).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from manhattan import prereg, prereg_v2
from manhattan.testing import reads_hand_edited_file
from nightshift import protected

ROOT = Path(__file__).resolve().parents[1]
# the lines docs/manhattan/ETHAN_ACTIONS.md item 19 asks Ethan to add to .github/CODEOWNERS
NEW_PROTECTED = ("docs/manhattan/PROTOCOL_v3.1.md", "docs/manhattan/SIM_PREREG_v2.md", "docs/manhattan/sim_prereg_v2.sha256",
                 "manhattan/prereg_v2.py", "tests/test_manhattan_prereg_v2.py")


@reads_hand_edited_file
def test_the_v2_record_verifies_and_pins_both_files(tmp_path):
    assert prereg_v2.verify() == []
    rows = dict((rel, h) for h, rel in prereg.read_record(prereg_v2.RECORD))
    assert set(rows) == {prereg_v2.SIM_PREREG_V2, prereg_v2.PROTOCOL_V31}
    assert prereg_v2.prereg_v2_hash() == rows[prereg_v2.SIM_PREREG_V2] != prereg_v2.protocol_v31_hash()
    assert prereg_v2.main(["verify"]) == 0 and prereg_v2.main([]) == 2
    # a copy with one character changed in either file fails, and so does a changed version 1
    for rel in (prereg_v2.SIM_PREREG_V2, prereg_v2.PROTOCOL_V31, "docs/manhattan/SIM_PREREG.md"):
        root = tmp_path / rel.replace("/", "_")
        (root / "docs/manhattan").mkdir(parents=True)
        for name in ("SIM_PREREG.md", "sim_prereg.sha256", "SIM_PREREG_v2.md", "PROTOCOL_v3.1.md", "sim_prereg_v2.sha256"):
            shutil.copy(ROOT / "docs/manhattan" / name, root / "docs/manhattan" / name)
        assert prereg_v2.verify(root) == []
        (root / rel).write_text((root / rel).read_text(encoding="utf-8").replace("0.06", "0.07", 1), encoding="utf-8")
        errs = prereg_v2.verify(root)
        assert len(errs) == 1 and rel in errs[0]
        if rel != "docs/manhattan/SIM_PREREG.md":
            with pytest.raises(RuntimeError, match="does not match its recorded hash"):
                prereg_v2.prereg_v2_hash(root)


@reads_hand_edited_file
def test_version_1_and_its_protocol_are_byte_for_byte_what_they_were():
    """Version 2 is written beside version 1, never over it: the two frozen files still match the hashes
    recorded before this revision."""
    assert prereg.verify(prereg.RECORDS[0], ROOT) == []
    assert prereg.read_record(prereg.RECORDS[0]) == [("e4bbcc44bebbc601b8bccc0e609131ad5185982f3047108dfaaf2fe2908c21e6",
                                                      "docs/manhattan/SIM_PREREG.md")]
    assert prereg.sha256(ROOT / "docs/manhattan/PROTOCOL_v3.md") == "4fbb5c72ad7214710aea7417fbf2fe131edb56f4eb83bffccac97478472f3a9f"


@reads_hand_edited_file
def test_the_codeowners_lines_of_item_19_protect_the_five_new_files(tmp_path):
    """The lines are quoted in ETHAN_ACTIONS.md for Ethan to paste; added to a copy of CODEOWNERS they protect
    exactly the five new paths and nothing else that this revision added."""
    actions = (ROOT / "docs/manhattan/ETHAN_ACTIONS.md").read_text(encoding="utf-8")
    item = actions[actions.index("## 19. Adopt Protocol v3.1"):]
    block = item[item.index("```\n# Manhattan, version 2") + 4:]
    block = block[: block.index("```")]
    lines = [l for l in block.splitlines() if l and not l.startswith("#")]
    assert lines == [f"/{p} @EthanC100" for p in NEW_PROTECTED]
    owners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    copy = tmp_path / "CODEOWNERS"
    copy.write_text(owners.replace("# protected:end", block + "\n# protected:end"), encoding="utf-8")
    pats = protected.patterns(copy)
    others = ["manhattan/stats/spa_hedged.py", "manhattan/stats/hier_analytic.py", "manhattan/sim/pipeline_v2.py",
              "manhattan/sim/hb_v2.py", "docs/manhattan/SIM_PREREG_AMENDMENTS.md", "results/manhattan_sim/v2/REPORT.md",
              "tests/test_manhattan_v2.py", "scripts/manhattan_sim_run.sh"]
    assert protected.protected(list(NEW_PROTECTED) + others, pats) == sorted(NEW_PROTECTED)
    # until Ethan pastes them, a session can still write these files: that is how this revision was made
    already = protected.protected(list(NEW_PROTECTED))
    assert already in ([], sorted(NEW_PROTECTED))
