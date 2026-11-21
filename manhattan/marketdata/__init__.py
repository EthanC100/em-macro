"""Manhattan market data: canonical schema, validation, vendor adapters, immutable datasets and point-in-time
availability for historical futures, currencies, bonds and commodities.

Design: docs/manhattan/marketdata/DESIGN.md. Nothing here fetches data, holds credentials or reads a licensed
file it is not handed; every test runs on synthetic fixtures.

    schema       Instrument, Contract, Observation, AdjustmentEvent
    provenance   SourceDescriptor, DatasetManifest (immutable dataset identity MD-<16 hex>)
    timing       observation, publication and research-availability times; the research clock
    validate     missing, duplicate, stale, timestamp and look-ahead checks
    fence        manhattan.roles applied at parse time (reserve/forward rows never read without authorisation)
    adapters     fixture CSV, Norgate export layout, Databento statistics records
    ingest       the pipeline
    store        content-addressed, read-only dataset store with a hash-chained registry
    vintages     first-seen history, revisions, as-of reads, bridge to manhattan.engine.pit
    continuous   continuous futures series built as of a date
"""
