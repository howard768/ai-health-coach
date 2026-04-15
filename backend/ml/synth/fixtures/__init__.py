"""Deterministic JSON fixtures for the Phase 4.5 synth factory.

These files are checked into git on purpose. They are not DB dumps (DB
schemas drift, fixture files should not), but compact reference data
that the generator modules read at run time and the tests in
``tests/ml/test_synth*`` can diff against.

Files:

- ``personas.json`` — the five coach-chat personas used by
  ``ml.synth.conversations.generate_conversations``. The file is the
  single source of truth for persona names, descriptions, adversarial
  flag, and archetype message seeds. Editing here changes behavior
  everywhere.

- ``demographics_ranges.json`` — informational reference table of the
  NHANES-inspired ranges that ``ml.synth.demographics`` encodes in
  module-level constants. Not read at run time; exists so a future
  maintainer can tell whether a range shift is intentional or a drift.
"""
