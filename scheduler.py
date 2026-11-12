"""Card scheduling for Ankikado: show the card most likely to be forgotten.

Each card that has been answered has a *stability*: the number of seconds
after which the chance of still remembering it is estimated to have dropped
to RETENTION (90%). A card is *due* once that much time has passed.

    correct answer  -> stability grows by GROWTH x the gap just survived
    wrong answer    -> stability drops to MISS_STABILITY (due in a minute)

To pick the next card, every card gets an estimated chance of having been
forgotten:

    answered before  -> 1 - RETENTION ** (time since answered / stability)
    never seen       -> 1 - NEW_RECALL

The most forgotten card is shown. Answered cards at least TIE_MARGIN as
forgotten as it count as ties and one of them is drawn at random; new cards
are drawn at random from the next NEW_BLOCK in deck order. That way the
order of the cards never becomes a clue to the answer.

A card just shown is held back until MIN_GAP other cards have been shown.
When nothing is due and nothing is new, it is held back for a third of the
deck instead, so that the session becomes a rotation through the deck
(weakest cards coming round soonest) rather than a loop over a few cards.

So a deck being learned from nothing is cycled through as one big stack,
cards that keep being answered correctly drop out of the way for longer and
longer, and whatever is weakest gets the time that frees up.

Nothing here touches the disk or the terminal. `Scheduler.progress` is a
plain dict that the caller loads and saves.
"""
import math
import random
import time
from collections import deque

# Recall probability that defines a card's stability.
RETENTION = 0.9
# Stability after a wrong answer, in seconds.
MISS_STABILITY = 60.0
# Stability after answering a never-seen card correctly. Getting it right
# with no help means it was already known, so it can wait.
FIRST_TRY_STABILITY = 7 * 24 * 3600.0
# A correct answer adds this many seconds of stability per second of gap.
GROWTH = 1.5
# Recall estimate given to never-seen cards. A missed card outranks new
# cards once its own estimate has decayed below this (about 11 minutes
# after the miss), which keeps huge decks from being introduced all at once.
NEW_RECALL = 0.3
# A card is never shown again until this many other cards have been shown.
MIN_GAP = 3
# Cards at least this forgotten, relative to the most forgotten one, are
# treated as ties and drawn from at random.
TIE_MARGIN = 0.5
# New cards are introduced in deck order, shuffled within blocks of this
# size. The blocks are large because decks tend to list related cards
# together (a row of kana), which would make the next card easy to guess.
NEW_BLOCK = 50
# Cards whose stability has reached this are reported as "known".
KNOWN_AFTER = 24 * 3600.0
MAX_STABILITY = 365 * 24 * 3600.0

# How overdue (time since answered / stability) a card with NEW_RECALL is.
_NEW_OVERDUE = math.log(NEW_RECALL) / math.log(RETENTION)


def card_key(card):
    """Identifies a card in the progress dict, independent of its deck."""
    return card["front"] + "\t" + card["back"]


class Scheduler:
    def __init__(self, cards, progress=None, now=None, rng=None):
        """
        cards:    list of {"front": ..., "back": ...} dicts, in teaching order
        progress: dict of card_key -> state, updated in place by record()
        now:      function returning the current time in seconds
                  (default: time.time)
        rng:      random.Random instance (for repeatable tests)
        """
        self._cards = []
        self._keys = []
        for card in cards:
            key = card_key(card)
            if key not in self._keys:
                self._cards.append(card)
                self._keys.append(key)
        if not self._cards:
            raise ValueError("deck has no cards")

        self.progress = {} if progress is None else progress
        self._now = now or time.time
        self._rng = rng or random.Random()
        self._recent = deque(maxlen=max(MIN_GAP, len(self._cards) // 3))

    # -- questions about a card ---------------------------------------------

    def is_new(self, card):
        return card_key(card) not in self.progress

    def stability(self, card):
        """Seconds until recall drops to RETENTION, or None for a new card."""
        state = self.progress.get(card_key(card))
        return state["stability"] if state else None

    def counts(self):
        """How many of this deck's cards are new, being learned, and known."""
        result = {"new": 0, "learning": 0, "known": 0}
        for key in self._keys:
            state = self.progress.get(key)
            if state is None:
                result["new"] += 1
            elif state["stability"] < KNOWN_AFTER:
                result["learning"] += 1
            else:
                result["known"] += 1
        return result

    # -- choosing the next card ---------------------------------------------

    def next_card(self):
        now = self._now()
        deck_size = len(self._cards)
        gap = min(MIN_GAP, deck_size - 1)
        seen, new = self._rank(now, gap)

        if not seen or (new and seen[0][0] < _NEW_OVERDUE):
            # No answered card is more forgotten than a new card would be.
            return self._rng.choice(new)

        if seen[0][0] < 1.0:
            # Nothing is due or new: rotate through the deck instead of
            # looping over whichever few cards are weakest.
            rest = min(max(MIN_GAP, deck_size // 3), deck_size - 1)
            if rest > gap:
                seen, new = self._rank(now, rest)

        most_forgotten = self._forgotten(seen[0][0])
        ties = [
            card for overdue, card in seen
            if self._forgotten(overdue) >= TIE_MARGIN * most_forgotten
        ]
        return self._rng.choice(ties)

    def _rank(self, now, gap):
        """Cards that may be shown now, as (seen, new).

        `seen` is (how overdue, card) for the answered cards, worst first,
        leaving out the `gap` most recently shown. Overdue is time since
        answered / stability, so 1.0 means due.
        `new` is the next NEW_BLOCK never-seen cards in deck order.
        """
        recent = set(list(self._recent)[-gap:]) if gap else set()
        seen = []
        new = []
        new_block = None
        for position, (card, key) in enumerate(zip(self._cards, self._keys)):
            state = self.progress.get(key)
            if state is None:
                if new_block is None:
                    new_block = position // NEW_BLOCK
                if position // NEW_BLOCK == new_block:
                    new.append(card)
            elif key not in recent:
                elapsed = max(0.0, now - state["last_seen"])
                seen.append((elapsed / state["stability"], card))
        seen.sort(key=lambda entry: entry[0], reverse=True)
        return seen, new

    @staticmethod
    def _forgotten(overdue):
        """Estimated chance that a card this overdue has been forgotten."""
        return 1.0 - RETENTION ** overdue

    # -- recording an answer -------------------------------------------------

    def record(self, card, correct):
        """Update the card's memory state after it was answered."""
        now = self._now()
        key = card_key(card)
        state = self.progress.get(key)

        if state is None:
            state = {"stability": 0.0, "last_seen": now, "seen": 0, "missed": 0}
            self.progress[key] = state
            stability = FIRST_TRY_STABILITY if correct else MISS_STABILITY
        elif correct:
            stability = state["stability"]
            elapsed = max(0.0, now - state["last_seen"])
            if elapsed > stability:
                # Overdue: one correct answer after a long gap is only
                # partly trusted, so credit the geometric mean of the
                # expected and the actual gap.
                elapsed = math.sqrt(elapsed * stability)
            stability += GROWTH * elapsed
        else:
            stability = MISS_STABILITY

        state["stability"] = min(stability, MAX_STABILITY)
        state["last_seen"] = now
        state["seen"] += 1
        if not correct:
            state["missed"] += 1

        self._recent.append(key)
