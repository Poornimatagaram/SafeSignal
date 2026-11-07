"""Constrained extraction into coded fields (PV-02, SE-01 to SE-03, VC-10). Not built yet (task A3).

Maps filtered answers to schema/enums.json term codes (unmapped -> SE_OTHER_REVIEW, D-015), severity and onset,
and sets known_side_effect from term_cache.known_for_program (D-007). Local model with JSON-schema output only;
anything outside the schema is dropped.
"""
