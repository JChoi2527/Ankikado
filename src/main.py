import sys
from os import system, name
import json
from pathlib import Path
import random
from collections import deque

def clear():
    # windows
    if name == 'nt':
        _ = system('cls')

    # mac and linux
    else:
        _ = system('clear')

recent_queue = []

def biased_shuffle (n):
    while True:
        random_element = random.choice(n)
        if not random_element in recent_queue:
            recent_queue.append(random_element)
            if len(recent_queue) > 5:
                recent_queue.pop(0)
            return random_element

path = Path(__file__).parent / "../json/cards.json"
with path.open() as file:
    data = json.load(file)

cards = data["cards"]

correct_count = 0
total_count = 0

incorrect_cards = []

try:
    while True:
        # Select a random word entry
        random_card = biased_shuffle(cards)

        # Print the word
        print(random_card["front"])

        # Prompt the user for input and save it in a variable
        user_input = input("Input: ")

        clear()

        if user_input == random_card["back"]:
            correct_count += 1
            total_count += 1
            print("Correct!")
            print("")

        elif user_input == "exit":
            print("Score: " + str(correct_count) + "/" + str(total_count))
            if incorrect_cards:
                print("Incorrect list:")
                for card in incorrect_cards:
                    print(card["front"] + ": " + card["back"])
            sys.exit()

        else:
            if not random_card in incorrect_cards:
                incorrect_cards.append(random_card)
            total_count += 1
            print("INCORRECT, answer is:")
            print(random_card["back"])
            print("")
except KeyboardInterrupt:
    print("")
    print("")
    print("Score: " + str(correct_count) + "/" + str(total_count))
    if incorrect_cards:
        print("Incorrect list:")
        for card in incorrect_cards:
            print(card["front"] + ": " + card["back"])
    exit(0)