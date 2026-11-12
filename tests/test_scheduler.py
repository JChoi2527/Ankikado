"""Behavioural tests for the card scheduler.

The scheduler is driven with a fake clock and a seeded random generator so
every run is repeatable. Bounds are deliberately loose: they describe how a
study session should feel, not the exact tuning constants.
"""
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scheduler import Scheduler, card_key  # noqa: E402

MINUTE = 60.0
HOUR = 3600.0
DAY = 86400.0


class FakeClock:
    def __init__(self, start=1000000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def load_deck(name):
    with (ROOT / "json" / (name + ".json")).open(encoding="utf-8") as f:
        return json.load(f)["cards"]


def make_deck(n):
    return [{"front": "f%d" % i, "back": "b%d" % i} for i in range(n)]


def make_scheduler(cards, clock, seed=1, progress=None):
    return Scheduler(cards, progress=progress, now=clock, rng=random.Random(seed))


def always_right(card, first_time):
    return True


def wrong_on_first_sight(card, first_time):
    return not first_time


def study(scheduler, clock, learner, steps, pace=3.0):
    """Answer `steps` cards, `pace` seconds each. Returns the fronts shown."""
    shown = []
    for _ in range(steps):
        card = scheduler.next_card()
        correct = learner(card, scheduler.is_new(card))
        clock.advance(pace)
        scheduler.record(card, correct)
        shown.append(card["front"])
    return shown


def seen(stability, last_seen):
    return {"stability": stability, "last_seen": last_seen, "seen": 3, "missed": 0}


def others_before_return(shown, index):
    """How many other cards were shown before shown[index] came back."""
    front = shown[index]
    later = shown[index + 1:]
    if front not in later:
        return None
    return later.index(front)


class MemoryUpdateTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.deck = make_deck(20)
        self.card = self.deck[0]

    def scheduler_with(self, stability, age):
        progress = {card_key(self.card): seen(stability, self.clock() - age)}
        return make_scheduler(self.deck, self.clock, progress=progress)

    def test_missing_a_new_card_makes_it_a_learning_card(self):
        s = make_scheduler(self.deck, self.clock)
        s.record(self.card, False)
        self.assertEqual(s.counts(), {"new": 19, "learning": 1, "known": 0})
        self.assertLess(s.stability(self.card), 10 * MINUTE)

    def test_knowing_a_new_card_first_try_counts_it_as_known(self):
        s = make_scheduler(self.deck, self.clock)
        s.record(self.card, True)
        self.assertEqual(s.counts(), {"new": 19, "learning": 0, "known": 1})

    def test_on_time_correct_review_multiplies_stability(self):
        s = self.scheduler_with(stability=HOUR, age=HOUR)
        s.record(self.card, True)
        self.assertGreater(s.stability(self.card), 1.5 * HOUR)
        self.assertLess(s.stability(self.card), 4 * HOUR)

    def test_early_correct_review_barely_grows_stability(self):
        s = self.scheduler_with(stability=HOUR, age=MINUTE)
        s.record(self.card, True)
        self.assertGreaterEqual(s.stability(self.card), HOUR)
        self.assertLess(s.stability(self.card), 1.1 * HOUR)

    def test_overdue_correct_review_grows_more_than_on_time_one(self):
        on_time = self.scheduler_with(stability=HOUR, age=HOUR)
        on_time.record(self.card, True)
        overdue = self.scheduler_with(stability=HOUR, age=9 * HOUR)
        overdue.record(self.card, True)
        self.assertGreater(overdue.stability(self.card), on_time.stability(self.card))

    def test_one_correct_answer_after_a_long_break_is_not_trusted_blindly(self):
        # Missed right before a week away, then answered correctly once
        # (possibly a lucky guess between two look-alikes).
        progress = {card_key(c): seen(30 * DAY, self.clock() + 7 * DAY) for c in self.deck[1:]}
        s = make_scheduler(self.deck, self.clock, progress=progress)
        s.record(self.card, False)
        self.clock.advance(7 * DAY)
        s.record(self.card, True)
        self.assertGreater(s.stability(self.card), MINUTE)
        self.assertLess(s.stability(self.card), DAY)
        self.assertEqual(s.counts()["learning"], 1)
        # ...so a day later it is checked again ahead of the well-known cards.
        self.clock.advance(DAY)
        self.assertIn(self.card["front"], study(s, self.clock, always_right, 5))

    def test_missing_a_well_known_card_sends_it_back_to_learning(self):
        s = self.scheduler_with(stability=30 * DAY, age=DAY)
        self.assertEqual(s.counts()["known"], 1)
        s.record(self.card, False)
        self.assertLess(s.stability(self.card), 10 * MINUTE)
        self.assertEqual(s.counts(), {"new": 19, "learning": 1, "known": 0})

    def test_stability_never_exceeds_a_few_years(self):
        s = self.scheduler_with(stability=300 * DAY, age=300 * DAY)
        for _ in range(10):
            self.clock.advance(5000 * DAY)
            s.record(self.card, True)
        self.assertLessEqual(s.stability(self.card), 3 * 365 * DAY)

    def test_clock_going_backwards_does_not_corrupt_state(self):
        s = self.scheduler_with(stability=HOUR, age=HOUR)
        self.clock.advance(-10 * DAY)
        s.record(self.card, True)
        self.assertGreaterEqual(s.stability(self.card), HOUR)
        self.assertIsNotNone(s.next_card())
        self.assertEqual(sum(s.counts().values()), 20)


def mostly_known(deck, clock, weak):
    """Everything was learned long ago except the `weak` cards, missed yesterday."""
    progress = {card_key(c): seen(30 * DAY, clock() - DAY) for c in deck}
    for c in weak:
        progress[card_key(c)] = seen(60.0, clock() - DAY)
    return progress


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    # -- learning a deck from nothing ---------------------------------------

    def test_fluent_learner_sees_every_card_once_before_any_repeat(self):
        deck = load_deck("kana")
        s = make_scheduler(deck, self.clock)
        shown = study(s, self.clock, always_right, len(deck))
        self.assertEqual(len(set(shown)), len(deck))

    def test_beginner_is_not_drilled_on_a_handful_of_cards(self):
        # Cramming a small stack feels good but teaches less than a big one,
        # so a missed card must not come back soon while new ones remain.
        for pace in (3.0, 8.0):
            with self.subTest(pace=pace):
                clock = FakeClock()
                s = make_scheduler(load_deck("hiragana"), clock)
                shown = study(s, clock, wrong_on_first_sight, 60, pace=pace)
                last_seen_at = {}
                for i, front in enumerate(shown):
                    if front in last_seen_at:
                        self.assertGreaterEqual(i - last_seen_at[front], 20, front)
                    last_seen_at[front] = i
                self.assertGreaterEqual(len(set(shown)), 45)

    def test_on_a_huge_deck_missed_cards_return_before_everything_is_introduced(self):
        clock = FakeClock()
        s = make_scheduler(make_deck(500), clock)
        shown = study(s, clock, lambda card, first_time: False, 400, pace=6.0)
        distinct = len(set(shown))
        self.assertGreater(distinct, 50)
        self.assertLess(distinct, 250)

    def test_learner_who_keeps_missing_everything_still_cycles_fairly(self):
        clock = FakeClock()
        deck = make_deck(12)
        s = make_scheduler(deck, clock)
        shown = study(s, clock, lambda card, first_time: False, 240, pace=6.0)
        for card in deck:
            self.assertGreaterEqual(shown.count(card["front"]), 10)
            self.assertLessEqual(shown.count(card["front"]), 40)

    def test_no_card_repeats_with_fewer_than_three_others_in_between(self):
        for learner in (always_right, wrong_on_first_sight, lambda c, f: False):
            clock = FakeClock()
            s = make_scheduler(load_deck("hiragana"), clock)
            shown = study(s, clock, learner, 400)
            for i in range(len(shown) - 3):
                window = shown[i:i + 4]
                self.assertEqual(len(set(window)), 4, "repeat in %r at %d" % (window, i))

    def test_minimum_gap_holds_even_when_every_card_looks_forgotten(self):
        # Answering one card an hour: by then every card, including the one
        # shown just before, is estimated to be completely forgotten.
        deck = make_deck(8)
        s = make_scheduler(deck, self.clock)
        shown = study(s, self.clock, lambda card, first_time: False, 150, pace=HOUR)
        for i in range(len(shown) - 3):
            window = shown[i:i + 4]
            self.assertEqual(len(set(window)), 4, "repeat in %r at %d" % (window, i))

    def test_new_cards_follow_deck_order_in_large_chunks(self):
        deck = make_deck(500)
        s = make_scheduler(deck, self.clock)
        shown = study(s, self.clock, always_right, 200)
        positions = [int(front[1:]) for front in shown]
        self.assertEqual(len(set(positions)), 200)
        # The start of the deck is taught before the rest of it...
        self.assertLess(max(positions[:50]), 100)
        self.assertLess(max(positions), 300)
        # ...but not card by card in file order.
        self.assertNotEqual(positions[:50], sorted(positions[:50]))

    def test_new_cards_do_not_arrive_one_kana_row_at_a_time(self):
        # The decks list kana row by row (ka ki ku ke ko). Introducing them
        # in that order would give away the consonant of the next card.
        deck = load_deck("hiragana")
        row = {c["front"]: i // 5 for i, c in enumerate(deck)}
        same_row = 0
        for seed in range(20):
            clock = FakeClock()
            s = make_scheduler(deck, clock, seed=seed)
            shown = study(s, clock, always_right, len(deck))
            same_row += sum(row[a] == row[b] for a, b in zip(shown, shown[1:]))
        self.assertLess(same_row / (20 * (len(deck) - 1)), 0.2)

    def test_second_pass_through_a_deck_is_in_a_different_order(self):
        deck = load_deck("hiragana")
        for learner in (always_right, lambda card, first_time: False):
            shifts = []
            for seed in range(10):
                clock = FakeClock()
                s = make_scheduler(deck, clock, seed=seed)
                shown = study(s, clock, learner, 2 * len(deck))
                first = {front: i for i, front in enumerate(shown[:len(deck)])}
                shifts += [abs(first[front] - i)
                           for i, front in enumerate(shown[len(deck):]) if front in first]
            # A card moves about 24 places on average in a pure shuffle of 71.
            self.assertGreater(sum(shifts) / len(shifts), 10)

    # -- a deck that is mostly known ----------------------------------------

    def weak_card_session(self, weak_count, learner_for, steps):
        """Hiragana, all long known except `weak_count` cards missed yesterday."""
        deck = load_deck("hiragana")
        weak_fronts = {c["front"] for c in deck[10:10 + weak_count]}
        progress = mostly_known(deck, self.clock, deck[10:10 + weak_count])
        s = make_scheduler(deck, self.clock, progress=progress)
        shown = study(s, self.clock, learner_for(weak_fronts), steps, pace=4.0)
        return shown, weak_fronts

    @staticmethod
    def keeps_missing(weak_fronts):
        return lambda card, first_time: card["front"] not in weak_fronts

    @staticmethod
    def knows_them_now(weak_fronts):
        return always_right

    def test_a_few_weak_cards_get_far_more_than_their_share_of_practice(self):
        shown, weak = self.weak_card_session(3, self.keeps_missing, 200)
        weak_share = sum(f in weak for f in shown) / len(shown)
        fair_share = 3 / 71
        self.assertGreater(weak_share, 3 * fair_share)
        for front in weak:
            self.assertGreaterEqual(shown.count(front), 8)

    def test_weak_cards_never_crowd_out_the_rest_of_the_deck(self):
        shown, weak = self.weak_card_session(3, self.keeps_missing, 200)
        weak_share = sum(f in weak for f in shown) / len(shown)
        self.assertLess(weak_share, 0.5)
        self.assertGreaterEqual(len(set(shown) - weak), 50)

    def test_a_single_weak_card_gets_extra_practice_without_dominating(self):
        shown, weak = self.weak_card_session(1, self.keeps_missing, 200)
        share = sum(f in weak for f in shown) / len(shown)
        self.assertGreater(share, 3 / 71)
        self.assertLessEqual(share, 0.25)

    def test_weak_cards_are_shown_less_once_they_are_answered_correctly(self):
        missing, weak = self.weak_card_session(3, self.keeps_missing, 300)
        self.clock = FakeClock()
        knowing, _ = self.weak_card_session(3, self.knows_them_now, 300)
        still_missing = sum(f in weak for f in missing[100:])
        now_known = sum(f in weak for f in knowing[100:])
        self.assertLess(now_known, still_missing)

    def test_with_nothing_due_cards_rotate_instead_of_looping(self):
        # Everything is answered correctly, so after the weak cards' first
        # showing nothing is due: no card may come round again quickly,
        # however much weaker it is than the rest.
        shown, weak = self.weak_card_session(3, self.knows_them_now, 300)
        last_seen_at = {}
        for i, front in enumerate(shown):
            if front in last_seen_at:
                self.assertGreaterEqual(i - last_seen_at[front], 15, front)
            last_seen_at[front] = i

    def test_with_everything_known_weaker_cards_are_favoured(self):
        deck = make_deck(10)
        weak_picks = 0
        for seed in range(200):
            clock = FakeClock()
            progress = {card_key(c): seen(30 * DAY, clock() - 5 * MINUTE) for c in deck}
            progress[card_key(deck[4])] = seen(10 * MINUTE, clock() - 5 * MINUTE)
            s = make_scheduler(deck, clock, seed=seed, progress=progress)
            weak_picks += s.next_card()["front"] == "f4"
        self.assertGreater(weak_picks, 160)

    def test_with_everything_known_every_card_still_gets_practice(self):
        deck = make_deck(10)
        progress = {card_key(c): seen(30 * DAY, self.clock() - HOUR) for c in deck}
        s = make_scheduler(deck, self.clock, progress=progress)
        shown = study(s, self.clock, always_right, 100)
        self.assertEqual(len(set(shown)), 10)

    # -- priorities ---------------------------------------------------------

    def test_most_forgotten_cards_are_reviewed_first(self):
        deck = make_deck(30)
        picks = set()
        for seed in range(40):
            clock = FakeClock()
            # Five cards are long overdue; the rest are only just due.
            progress = {card_key(c): seen(DAY, clock() - 1.1 * DAY) for c in deck}
            for c in deck[10:15]:
                progress[card_key(c)] = seen(DAY, clock() - 12 * DAY)
            s = make_scheduler(deck, clock, seed=seed, progress=progress)
            picks.add(s.next_card()["front"])
        self.assertTrue(picks <= {"f10", "f11", "f12", "f13", "f14"}, picks)
        # Equally forgotten cards are shuffled, not taken in a fixed order.
        self.assertGreater(len(picks), 2)

    def test_forgotten_card_is_reviewed_even_though_new_cards_are_waiting(self):
        deck = make_deck(40)
        for seed in range(20):
            with self.subTest(seed=seed):
                clock = FakeClock()
                progress = {card_key(deck[30]): seen(DAY, clock() - 60 * DAY)}
                s = make_scheduler(deck, clock, seed=seed, progress=progress)
                self.assertEqual(s.next_card()["front"], "f30")

    def test_well_remembered_card_waits_while_new_cards_are_introduced(self):
        deck = make_deck(40)
        progress = {card_key(deck[30]): seen(30 * DAY, self.clock() - DAY)}
        s = make_scheduler(deck, self.clock, progress=progress)
        self.assertNotIn("f30", study(s, self.clock, always_right, 39))

    def test_returning_after_a_month_starts_with_the_weakest_cards(self):
        deck = load_deck("hiragana")
        weak = deck[20:40]
        weak_fronts = {c["front"] for c in weak}
        firsts = set()
        for seed in range(20):
            clock = FakeClock()
            progress = {card_key(c): seen(10 * DAY, clock() - 30 * DAY) for c in deck}
            for c in weak:
                progress[card_key(c)] = seen(60.0, clock() - 30 * DAY)
            s = make_scheduler(deck, clock, seed=seed, progress=progress)
            shown = study(s, clock, always_right, 15)
            self.assertTrue(set(shown) <= weak_fronts, shown)
            firsts.add(shown[0])
        # Equally stale cards must not come out in deck order every time.
        self.assertGreater(len(firsts), 5)

    # -- edge cases ---------------------------------------------------------

    def test_frozen_clock_with_everything_just_seen_still_picks_a_card(self):
        deck = make_deck(5)
        progress = {card_key(c): seen(DAY, self.clock()) for c in deck}
        s = make_scheduler(deck, self.clock, progress=progress)
        for _ in range(20):
            card = s.next_card()
            self.assertIn(card, deck)
            s.record(card, True)

    def test_tiny_decks_work(self):
        for size in (1, 2, 3):
            with self.subTest(size=size):
                clock = FakeClock()
                deck = make_deck(size)
                s = make_scheduler(deck, clock)
                shown = study(s, clock, wrong_on_first_sight, 40)
                self.assertEqual(set(shown), {c["front"] for c in deck})
                if size > 1:
                    for a, b in zip(shown, shown[1:]):
                        self.assertNotEqual(a, b)

    def test_duplicate_cards_in_a_deck_are_treated_as_one(self):
        deck = make_deck(3) + make_deck(3)
        s = make_scheduler(deck, self.clock)
        self.assertEqual(s.counts()["new"], 3)
        shown = study(s, self.clock, always_right, 30)
        for a, b in zip(shown, shown[1:]):
            self.assertNotEqual(a, b)

    def test_empty_deck_is_rejected(self):
        with self.assertRaises(ValueError):
            make_scheduler([], self.clock)


class SharedProgressTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_progress_survives_a_json_round_trip(self):
        deck = load_deck("hiragana")
        s = make_scheduler(deck, self.clock)
        study(s, self.clock, wrong_on_first_sight, 50)
        restored = json.loads(json.dumps(s.progress))
        again = make_scheduler(deck, self.clock, progress=restored)
        self.assertEqual(again.counts(), s.counts())

    def test_cards_learned_in_one_deck_are_known_in_another(self):
        hiragana = make_scheduler(load_deck("hiragana"), self.clock)
        study(hiragana, self.clock, always_right, 71)
        kana = make_scheduler(load_deck("kana"), self.clock, progress=hiragana.progress)
        self.assertEqual(kana.counts()["new"], 71)

    def test_progress_for_cards_outside_the_deck_is_left_alone(self):
        foreign = seen(DAY, self.clock() - 9 * DAY)
        progress = {"other\tcard": dict(foreign)}
        s = make_scheduler(make_deck(5), self.clock, progress=progress)
        self.assertEqual(s.counts(), {"new": 5, "learning": 0, "known": 0})
        study(s, self.clock, always_right, 20)
        self.assertEqual(s.progress["other\tcard"], foreign)


if __name__ == "__main__":
    unittest.main()
