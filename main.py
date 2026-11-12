import sys
import json
import math
import os
from os import system, name
from pathlib import Path
from enum import Enum
import argparse

# scheduler.py sits next to this file. An `ankikado` command installed before
# it existed only knows how to find main.py, so point Python at the folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scheduler import Scheduler, card_key

PROGRESS_VERSION = 1


def main(argv=None):
    args = parse_args(argv)

    path_string = "json/" + str(args.deck) + ".json"
    path = Path(__file__).parent / path_string
    with path.open(encoding='utf-8') as file:
        data = json.load(file)

    all_cards = data["cards"]
    if not all_cards:
        print("Deck " + str(args.deck) + " has no cards")
        sys.exit(1)

    save_path = progress_path()
    progress, corrupt_backup = load_progress(save_path)

    if args.reset:
        forgotten = 0
        for card in all_cards:
            if progress.pop(card_key(card), None) is not None:
                forgotten += 1
        if forgotten and not save_progress(save_path, progress):
            print("Progress could not be saved to " + str(save_path))
            sys.exit(1)
        print("Progress reset for " + str(args.deck) + " (" + str(forgotten) + " cards forgotten)")
        sys.exit(0)

    scheduler = Scheduler(all_cards, progress)
    incorrect_cards = []

    correct_count = 0
    total_count = 0
    save_failed = False

    clear_cli()

    print("Ankikado")
    print(str(args.deck))
    print(str(len(all_cards)) + " cards")
    print(status_line(scheduler))
    if corrupt_backup:
        print("Saved progress was unreadable and has been moved to " + str(corrupt_backup))
    print("")

    try:
        while True:
            card = scheduler.next_card()

            # print word
            if scheduler.is_new(card):
                print(card["front"] + "   (new)")
            else:
                print(card["front"])

            # prompt user for input and save it in a variable
            user_input = input("Answer: ")
            answer = normalize(user_input)

            clear_cli()

            if answer == normalize(card["back"]):
                result = Result.CORRECT
                correct_count += 1
                total_count += 1
            elif answer == "exit":
                result = Result.EXIT
            else:
                result = Result.INCORRECT
                if not card in incorrect_cards:
                    incorrect_cards.append(card)
                total_count += 1

            if result != Result.EXIT:
                scheduler.record(card, result == Result.CORRECT)
                if not save_progress(save_path, progress):
                    save_failed = True

            print("Score: " + str(correct_count) + "/" + str(total_count))

            if result == Result.CORRECT:
                print(status_line(scheduler))
                print("Correct")
                print("")
                print("")
            elif result == Result.INCORRECT:
                print(status_line(scheduler))
                print("Incorrect")
                print(card["front"] + ": " + card["back"])
                print("")
            elif result == Result.EXIT:
                print("")
                print_summary(incorrect_cards, save_failed, save_path)
                sys.exit()

    except (KeyboardInterrupt, EOFError):
        clear_cli()
        print("Score: " + str(correct_count) + "/" + str(total_count))
        print("")
        print_summary(incorrect_cards, save_failed, save_path)
        sys.exit(0)

class Result(Enum):
    EXIT = 0
    CORRECT = 1
    INCORRECT = -1

def parse_args(argv=None):
    # add_help=False so that -h can be used for hiragana; --help still works
    parser = argparse.ArgumentParser(
        description="Simple CLI flashcard program",
        add_help=False
    )
    parser.add_argument(
        "--help",
        action="help",
        help="Show this help message and exit"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-h", "--hiragana",
        dest="deck",
        action="store_const",
        const="hiragana",
        help="Use the hiragana deck"
    )
    group.add_argument(
        "-k", "--katakana",
        dest="deck",
        action="store_const",
        const="katakana",
        help="Use the katakana deck"
    )
    group.add_argument(
        "-d", "--deck",
        dest="deck",
        help="Specify flashcard deck by name (default: kana)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Forget the saved progress for the selected deck's cards and exit"
    )
    parser.set_defaults(deck="kana")

    return parser.parse_args(argv)

def normalize(answer):
    # answers are compared ignoring case and surrounding spaces
    return answer.strip().casefold()

def status_line(scheduler):
    counts = scheduler.counts()
    return ("Known: " + str(counts["known"])
            + " | Learning: " + str(counts["learning"]))
            # + " | New: " + str(counts["new"]))

def print_summary(incorrect_list, save_failed, save_path):
    print_incorrect(incorrect_list)
    if save_failed:
        print("Warning: progress could not be saved to " + str(save_path))
        print("")

def print_incorrect(incorrect_list):
    if incorrect_list:
        print("Incorrect list:")
        for card in incorrect_list:
            print(card["front"] + ": " + card["back"])
        print("")

def progress_path():
    """Where progress is kept between sessions (one file for all decks)."""
    if name == 'nt' and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    elif os.environ.get("XDG_DATA_HOME"):
        base = Path(os.environ["XDG_DATA_HOME"])
    else:
        base = Path.home() / ".local" / "share"
    return base / "ankikado" / "progress.json"

def load_progress(path):
    """Read saved progress.

    Returns (progress, backup). `progress` is a dict of card key -> state,
    empty if nothing usable was saved. If the file exists but cannot be
    understood it is moved aside, never deleted, and `backup` is its new
    location; otherwise `backup` is None.
    """
    path = Path(path)
    try:
        with path.open(encoding='utf-8') as file:
            data = json.load(file)
        cards = data["cards"]
        if not isinstance(cards, dict):
            raise ValueError("cards is not an object")
    except OSError:
        return {}, None
    except (ValueError, KeyError, TypeError):
        backup = path.with_name(path.name + ".corrupt")
        try:
            os.replace(str(path), str(backup))
        except OSError:
            backup = None
        return {}, backup

    progress = {}
    for key, state in cards.items():
        if not isinstance(state, dict):
            continue
        if not is_number(state.get("stability")) or state["stability"] <= 0:
            continue
        if not is_number(state.get("last_seen")):
            continue
        progress[key] = {
            "stability": state["stability"],
            "last_seen": state["last_seen"],
            "seen": state["seen"] if is_number(state.get("seen")) else 0,
            "missed": state["missed"] if is_number(state.get("missed")) else 0,
        }
    return progress, None

def save_progress(path, progress):
    """Write progress to disk. Returns False instead of raising on failure."""
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temp.open("w", encoding='utf-8') as file:
            json.dump({"version": PROGRESS_VERSION, "cards": progress}, file,
                      ensure_ascii=False, indent=1)
        # replace in one step so an interrupted save never leaves half a file
        os.replace(str(temp), str(path))
    except OSError:
        return False
    return True

def is_number(value):
    return (isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value))

def clear_cli():
    # windows
    if name == 'nt':
        _ = system('cls')

    # mac and linux
    else:
        _ = system('clear')

if __name__ == "__main__":
    main()  # Or your main function entry point
