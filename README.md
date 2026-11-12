# Ankikado
Simple CLI flashcard program written in Python 3

It always shows the card you are most likely to have forgotten, and it remembers how well you know each card between sessions (see [How cards are chosen](#how-cards-are-chosen))

Made it for myself for some discrete studying, decided to share if anyone else wanted it :)

## Linux Installation
Run the installation script from the Ankikado folder:

```
./install.sh
```

*Note: Run this **without** sudo. The script prompts for your password only when it needs to install python3-pip (the one step that requires root); running the whole script as root installs the command to the wrong place.

After it finishes, run `source ~/.bashrc` (or open a new terminal) so the `ankikado` command is on your PATH.

## No Installation/Windows
Alternatively, you can just run the main.py file directly with Python 3 from the Ankikado folder:

```
python3 main.py
```

## Usage
Run the ankikado command:

```
ankikado
```

To exit, input "exit" or press ctrl+c

| Option | What it does |
| --- | --- |
| *(none)* | Hiragana and katakana together |
| `-h`, `--hiragana` | Hiragana only |
| `-k`, `--katakana` | Katakana only |
| `-d NAME`, `--deck NAME` | Use the deck in `json/NAME.json` |
| `--reset` | Forget the saved progress for the selected deck's cards, then exit |
| `--help` | Show the options |

Answers ignore capital letters and spaces around them. A card you have never been shown is marked `(new)`; press enter if you don't know it and the answer is shown.

The line under the score counts the deck's cards:

- **Known**: expected to be remembered for at least a day
- **Learning**: seen, but not yet that well remembered
- **New**: never shown

For custom cards, add a file to Ankikado/json in the same format as the existing decks and pick it with `-d`. Cards are introduced roughly in the order they appear in the file.

## How cards are chosen
For every card it has shown you, Ankikado keeps a *stability*: how long it expects you to remember that card.

- A correct answer makes the stability longer. The longer you went without seeing the card, the more it grows.
- A wrong answer drops it to one minute.

Each turn it estimates how likely you are to have forgotten every card, from its stability and the time since you last answered it, and shows the most forgotten one. Roughly equal cards are shuffled, so the order keeps changing. In practice:

- **A new deck** is worked through as one big stack: every card once, then round again, starting with the ones you missed. A missed card waits for the remaining new cards (eleven minutes at most) instead of being drilled in a small group.
- **Cards you keep getting right** come up less and less often, and the time goes to the ones you get wrong.
- **Once there are no new cards left**, a card you miss comes back after about a minute (later if more forgotten cards are waiting), then at growing intervals as you get it right.
- **When nothing needs review**, it keeps rotating through the deck, weakest cards first, so you can practise as long as you like.
- No card is repeated until at least three others have been shown.

The numbers behind this are at the top of `scheduler.py`.

## Saved progress
Progress is saved after every answer to `~/.local/share/ankikado/progress.json` (`$XDG_DATA_HOME/ankikado/` if that is set, `%APPDATA%\ankikado\` on Windows).

It is stored per card, not per deck, so hiragana learned with `-h` is already known when you study the combined deck.

Deleting the file starts everything from scratch; `--reset` does the same for one deck.

## Tests
```
python3 -m unittest discover -s tests
```
