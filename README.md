# Ankikado
Simple CLI flashcard program written in Python 3

Picked cards are added to a queue and will not be picked again until it leaves queue to prevent immediate repetition

Cards that were answered incorrectly are prioritized

Made it for myself for some discrete studying, decided to share if anyone else wanted it :)

## Linux Installation
Run the installation script from the Ankikado folder:

```
./install.sh
```

*Note: Sudo is required to install python3-pip if it isn't installed already

## No Installation/Windows
Alternatively, you can just run the main.py file directly with Python 3 from the Ankikado folder:

```
python3 src/main.py
```

## Usage
Run the ankikado command:

```
ankikado
```

To exit, input "exit" or press ctrl+c

For custom cards, edit the cards.json file in Ankikado/json
