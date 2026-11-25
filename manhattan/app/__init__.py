"""Project Manhattan operations app, v1: a static, outcome-blind view of frozen batches and the private ledger.

    python -m manhattan.app build --batches DIR [--ledger-clone DIR | --remote PATH] --out DIR
    python -m manhattan.app demo --out DIR

``model`` builds the view model (a dict) from an allow-list of fields and checks it with ``assert_no_outcomes``;
``render`` turns it into one self-contained HTML page and a JSON export; ``demo`` builds a fully synthetic batch and
ledger in a temporary directory. Nothing here reveals performance: see ``docs/manhattan/ops/APP.md``.
"""
