import sys
from os import system, name
import json
from pathlib import Path
import random
from collections import deque
from enum import Enum

class Result(Enum):
    EXIT = 0
    CORRECT = 1
    INCORRECT = -1

def clear_cli():
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

def print_incorrect(incorrect_list):
    if incorrect_list:
        print("Incorrect list:")
        for card in incorrect_list:
            print(card["front"] + ": " + card["back"])
        print("")

def main():
    path = Path(__file__).parent / "../json/cards.json"
    with path.open() as file:
        data = json.load(file)

    cards = data["cards"]

    correct_count = 0
    total_count = 0

    incorrect_cards = []

    clear_cli()

    print("Ankikado")
    print("")
    print("")
    print("")

    try:
        while True:
            # Select a random word entry
            random_card = biased_shuffle(cards)

            # Print the word
            print(random_card["front"])

            # Prompt the user for input and save it in a variable
            user_input = input("Input: ")

            clear_cli()

            if user_input == random_card["back"]:
                result = Result.CORRECT
                correct_count += 1
                total_count += 1

            elif user_input == "exit":
                result = Result.EXIT

            else:
                result = Result.INCORRECT
                if not random_card in incorrect_cards:
                    incorrect_cards.append(random_card)
                total_count += 1

            print("Score: " + str(correct_count) + "/" + str(total_count))
            print("")

            match result:
                case Result.CORRECT:
                    print("Correct!")
                    print("")
                case Result.INCORRECT:
                    print("INCORRECT, answer is: " + random_card["back"])
                    print("")
                case Result.EXIT:
                    print_incorrect(incorrect_cards)
                    sys.exit()

    except KeyboardInterrupt:
        clear_cli()
        print("Score: " + str(correct_count) + "/" + str(total_count))
        print("")
        print_incorrect(incorrect_cards)
        exit(0)