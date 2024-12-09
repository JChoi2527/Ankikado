import sys
import json
import random
from os import system, name
from pathlib import Path
from enum import Enum

def main():
    path = Path(__file__).parent / "../json/cards.json"
    with path.open() as file:
        data = json.load(file)

    all_cards = data["cards"]
    incorrect_cards = []

    correct_count = 0
    total_count = 0

    all_queue = []
    incorrect_queue = []

    clear_cli()

    print("Ankikado")
    print("")
    print("")
    print("")

    try:
        while True:
            # every 10 cards, select random from incorrect_queue if it exists
            random_card = False
            if total_count%10 == 0:
                random_card = biased_shuffle(incorrect_cards, incorrect_queue)
            
            if random_card is False:
                random_card = biased_shuffle(all_cards, all_queue)

            # print word
            print(random_card["front"])

            # prompt user for input and save it in a variable
            user_input = input("Answer: ")

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

class Result(Enum):
    EXIT = 0
    CORRECT = 1
    INCORRECT = -1

def biased_shuffle (cards, queue):
    # create list of cards not in queue
    not_in_queue = [card for card in cards]
    for card in queue:
        if card in not_in_queue:
            not_in_queue.remove(card)

    # if all cards are in queue, return false
    if not not_in_queue:
        return False
    
    random_card = random.choice(not_in_queue)

    # add selected card to queue and pop if needed
    queue.append(random_card)
    if len(queue) >= len(cards):
        queue.pop(0)
    return random_card

def print_incorrect(incorrect_list):
    if incorrect_list:
        print("Incorrect list:")
        for card in incorrect_list:
            print(card["front"] + ": " + card["back"])
        print("")

def clear_cli():
    # windows
    if name == 'nt':
        _ = system('cls')

    # mac and linux
    else:
        _ = system('clear')