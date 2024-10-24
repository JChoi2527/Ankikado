# Ankikado
Simple CLI flashcard program written in Python 3

Selected cards are added to a 5 card queue and will not be selected until it leaves queue to prevent immediate repetition

Made it for myself for some discrete studying, decided to share if anyone else wanted it :)

## Linux Installation
Run the installation script in the Ankikado folder:

```
chmod +x install.sh
./install.sh
```

Run the ankikado command:

```
ankikado
```

If it says "ankikado: command not found", you may have to add local bin to PATH:

```
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## No Installation/Windows
Alternatively, you can just run the main.py file directly with Python 3:

```
python3 src/main.py
```

## Usage

To exit, input "exit" or press ctrl+c

For custom cards, edit the cards.json file in Ankikado/json