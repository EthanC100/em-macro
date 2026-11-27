"""Duplicate keys inside YAML merge sources must be refused before SafeLoader flattens them (#105 follow-up).

Reproduced on #105's reviewed head ae7d4b6: a repeated ``windows:`` inside an inline ``<<:`` mapping was flattened
(the last one won), so the reserve window vanished and a reserve date of fx_daily read as exploration. #105's final
head (6f356a6, merged) refuses it. These tests pin that end to end (loader, ``roles.Fence.from_config`` through
``access._fence_of``) for inline merges, merge sequences, aliases, nested merges and nested mappings, and check that
legitimate merges and explicit overrides still parse exactly as ``yaml.safe_load`` does. Synthetic text only.
"""
from __future__ import annotations

from datetime import date

import pytest
import yaml

from manhattan import access, roles
from manhattan import config as MC

WINDOW = "fx_daily: {start: 2010-01-01, end: 2018-12-31}"

ATTACKS = {
    # the reviewed reproduction, verbatim: block-style inline merge with a repeated key
    "inline_block_merge": ("exploration:\n  data_end: 2019-12-31\nreserve:\n  enabled: false\n  <<:\n    windows:\n"
                           "      fx_daily: {start: 2010-01-01, end: 2018-12-31}\n    windows: {}\n"),
    "inline_flow_merge": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                          f"  <<: {{windows: {{{WINDOW}}}, windows: {{}}}}\n"),
    "merge_sequence_first_source": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                                    f"  <<: [{{windows: {{{WINDOW}}}, windows: {{}}}}, {{mode: shared_window}}]\n"),
    "merge_sequence_later_source": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                                    f"  <<: [{{mode: shared_window}}, {{windows: {{{WINDOW}}}, windows: {{}}}}]\n"),
    "anchor_defined_inside_merge": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                                    f"  <<: &w {{windows: {{{WINDOW}}}, windows: {{}}}}\nother: {{<<: *w}}\n"),
    "alias_to_anchor_used_only_in_merges": (f"x: &w\n  windows: {{{WINDOW}}}\n  windows: {{}}\n"
                                            "exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                                            "  <<: *w\n"),
    "nested_merge_inside_merge_source": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n  <<:\n"
                                         f"    <<: {{windows: {{{WINDOW}}}, windows: {{}}}}\n"),
    "nested_mapping_inside_merge_source": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n  <<:\n"
                                           "    windows:\n"
                                           "      fx_daily: {start: 2010-01-01, end: 2018-12-31, end: 2011-01-01}\n"),
    "duplicate_domain_inside_merge_source": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n  <<:\n"
                                             "    windows:\n      fx_daily: {start: 2010-01-01, end: 2018-12-31}\n"
                                             "      fx_daily: {start: 2030-01-01, end: 2030-12-31}\n"),
}


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_a_duplicate_inside_a_merge_source_is_refused_by_the_loader(name):
    with pytest.raises(MC.DuplicateKeyError, match="duplicate"):
        MC.loads(ATTACKS[name])


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_the_fence_parser_refuses_it_and_never_reads_the_window_as_exploration(name):
    """The consumer path: ``access._fence_of`` parses the authoritative file and must fail closed."""
    with pytest.raises(access.AccessError) as exc:
        access._fence_of(ATTACKS[name].encode("utf-8"))
    assert isinstance(exc.value.__cause__, MC.DuplicateKeyError)


def test_the_reviewed_reproduction_no_longer_turns_a_reserve_date_into_exploration():
    """On ae7d4b6 this text parsed, the window was discarded, and fx_daily on 2015-01-05 was exploration."""
    text = ATTACKS["inline_block_merge"]
    unsafe = roles.Fence.from_config(yaml.safe_load(text))
    assert roles.role_of(date(2015, 1, 5), "fx_daily", unsafe) == roles.EXPLORATION
    with pytest.raises(MC.DuplicateKeyError):
        MC.loads(text)


LEGITIMATE = {
    "merge_then_explicit_override": ("base: &b {enabled: true, windows: {" + WINDOW + "}}\n"
                                     "exploration: {data_end: 2019-12-31}\nreserve:\n  <<: *b\n  enabled: false\n"),
    "merge_sequence_precedence": ("a: &a {mode: shared_window}\nb: &b {mode: disjoint_slices, store: imac_only}\n"
                                  "exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n"
                                  "  windows: {" + WINDOW + "}\n  <<: [*a, *b]\n"),
    "inline_merge_without_duplicates": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n  <<:\n"
                                        "    windows:\n      fx_daily: {start: 2010-01-01, end: 2018-12-31}\n"),
    "nested_merge_without_duplicates": ("exploration: {data_end: 2019-12-31}\nreserve:\n  enabled: false\n  <<:\n"
                                        "    <<: {windows: {" + WINDOW + "}}\n    mode: shared_window\n"),
    "same_key_in_two_sibling_mappings": ("a: {windows: {}}\nb: {windows: {}}\nexploration: {data_end: 2019-12-31}\n"
                                         "reserve:\n  enabled: false\n  windows: {" + WINDOW + "}\n"),
}


@pytest.mark.parametrize("name", sorted(LEGITIMATE))
def test_legitimate_merges_and_explicit_overrides_parse_exactly_as_safe_load(name):
    text = LEGITIMATE[name]
    assert MC.loads(text) == yaml.safe_load(text)


@pytest.mark.parametrize("name", sorted(LEGITIMATE))
def test_a_legitimately_merged_window_still_protects_its_dates(name):
    fence = roles.Fence.from_config(MC.loads(LEGITIMATE[name]))
    assert fence.reserve["fx_daily"] == (date(2010, 1, 1), date(2018, 12, 31))
    assert roles.role_of(date(2015, 1, 5), "fx_daily", fence) != roles.EXPLORATION


@pytest.mark.parametrize("text", [
    "reserve: { !!merge '<<': {windows: {}, windows: {}} }",
    "reserve: !!map {windows: {}, windows: {}}",
    "items: [{<<: {windows: {}, windows: {}}}]",
    "x: {true: 1, 1: 2}",
    "x: {1: a, 1.0: b}",
])
def test_tagged_sequence_and_type_variant_duplicates_are_refused(text):
    with pytest.raises(MC.DuplicateKeyError):
        MC.loads(text)
    with pytest.raises(access.AccessError) as exc:
        access._fence_of(text.encode())
    assert isinstance(exc.value.__cause__, MC.DuplicateKeyError)
