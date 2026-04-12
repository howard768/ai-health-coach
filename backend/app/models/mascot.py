"""Mascot customization — earned accessories that overlay on the SquatBlob.

Users earn accessories by hitting milestones (streaks, achievements, usage
levels). Once earned, an accessory is "unlocked" and the user can equip it
on the iOS home screen mascot whenever they like. Equipping is independent
of unlocking — you might unlock 12 accessories but only equip 2 at a time.

Schema decisions:
- One row per (user_id, accessory_id) pair. Unique constraint enforces
  no double-unlocks.
- `unlocked_at` records when the user earned it (for "you got this on
  April 11" celebration text + sortability in the wardrobe).
- `equipped` is a boolean — currently any number of accessories can be
  equipped at once. If we later need exclusivity (e.g. only one head
  accessory), the iOS layer enforces it; the DB stays permissive.
- No FK to a separate "accessories" table because the catalog is
  client-defined: iOS knows the full list, the backend just tracks
  what each user has unlocked. This avoids two-step migrations every
  time we add a new accessory — just ship the new ID in the iOS enum
  and the unlock detector starts using it.
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.core.time import utcnow_naive


class UserMascotState(Base):
    """One row per (user, accessory) pair. Tracks unlock + equip state.

    accessory_id is a string from the client-side `MascotAccessory` enum
    (e.g. "armothy_arms", "pounding_heart", "shield_and_sword"). The
    backend treats it as opaque — the iOS app maps the string to a
    rendering implementation.
    """
    __tablename__ = "user_mascot_state"
    __table_args__ = (
        # Each accessory can be unlocked exactly once per user.
        UniqueConstraint("user_id", "accessory_id", name="uq_user_mascot_accessory"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    accessory_id: Mapped[str] = mapped_column(String(64))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    # True if the user has it equipped on the active home-screen mascot.
    # Multiple accessories can be equipped simultaneously.
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
