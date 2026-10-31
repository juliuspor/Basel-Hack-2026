"""The rule that turns classifier readings into slot states, in one place and without I/O."""

from dataclasses import replace
from datetime import datetime

from classification.classifier import Reading
from occupancy.model import SlotOccupancy, SlotState

# A reading this sure changes the state at once. An unsure one only counts
# when the next reading of the same slot agrees with it.
CONFIDENT_READING = 0.85


def decide(slot: SlotOccupancy, reading: Reading, at: datetime) -> SlotOccupancy:
    confirmed = reading.confidence >= CONFIDENT_READING or slot.pending_taken == reading.taken
    if not confirmed:
        return replace(slot, pending_taken=reading.taken)
    state = SlotState.TAKEN if reading.taken else SlotState.FREE
    return replace(
        slot,
        state=state,
        confidence=reading.confidence,
        pending_taken=None,
        changed_at=at if state != slot.state else slot.changed_at,
    )
