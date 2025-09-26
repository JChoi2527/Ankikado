import sys
import json
import random
import math
from os import system, name
from pathlib import Path
from enum import Enum
import argparse

def main():
    parser = argparse.ArgumentParser(description="Simple CLI flashcard program")
    parser.add_argument(
        "-d", "--deck",
        help="Specify flashcard deck",
        default="kana"
    )

    args = parser.parse_args()
    path_string = "json/" + str(args.deck) + ".json"
    path = Path(__file__).parent / path_string
    with path.open(encoding='utf-8') as file:
        data = json.load(file)

    cards = data["cards"]
    cards_num = len(cards)
    boxes_num = 3
    boxes = [[] for _ in range(boxes_num)]
    boxes[0] = cards
    boxes_queue = [[] for _ in range(boxes_num)]
    
    boxes_order = []
    increment = 1
    for box_index in range(boxes_num - 1, -1, -1):
        for i in range(math.ceil(cards_num * (0.5 ** (boxes_num - increment)))):
            boxes_order.append(box_index)
        increment += 1

    incorrect_cards = []

    correct_count = 0
    total_count = 0

    clear_cli()

    print("Ankikado")
    print("")
    print(str(args.deck))
    print(str(len(cards)) + " cards")
    print("")

    try:
        order_index = 0
        while True:
            selected_card = False
            while not selected_card:
                while len(boxes[boxes_order[order_index]]) <= 0:
                    order_index += 1
                    if order_index >= len(boxes_order):
                        order_index = 0
                selected_card = biased_shuffle(boxes[boxes_order[order_index]], boxes_queue[boxes_order[order_index]])
                if not selected_card:
                    order_index += 1
                    if order_index >= len(boxes_order):
                        order_index = 0

            # print word
            print(selected_card["front"])

            # prompt user for input and save it in a variable
            user_input = input("Answer: ")

            clear_cli()

            if user_input == selected_card["back"]:
                result = Result.CORRECT
                if boxes_order[order_index] + 1 < boxes_num:
                    boxes[boxes_order[order_index]].remove(selected_card)
                    boxes_queue[boxes_order[order_index]].remove(selected_card)
                    boxes[boxes_order[order_index] + 1].append(selected_card)
                    boxes_queue[boxes_order[order_index] + 1].append(selected_card)
                correct_count += 1
                total_count += 1
            elif user_input == "exit":
                result = Result.EXIT
            else:
                result = Result.INCORRECT
                if not selected_card in incorrect_cards:
                    incorrect_cards.append(selected_card)
                if boxes_order[order_index] != 0:
                    boxes[boxes_order[order_index]].remove(selected_card)
                    boxes_queue[boxes_order[order_index]].remove(selected_card)
                    boxes[0].append(selected_card)
                    boxes_queue[0].append(selected_card)
                total_count += 1

            print(f"Score: {(correct_count)}/{str(total_count)}")

            if len(boxes[boxes_num - 1]) == cards_num:
                print("All cards in final box!!!")
            else:
                for index, box in enumerate(boxes):
                    print(f"Box {index+1}: {len(box)}", end='')
                    if index < boxes_num - 1:
                        print(", ", end='')
                    else:
                        print("")

            match result:
                case Result.CORRECT:
                    print("Correct!")
                    print("")
                    print("")
                case Result.INCORRECT:
                    print("INCORRECT")
                    print(selected_card["front"] + ": " + selected_card["back"])
                    print("")
                case Result.EXIT:
                    print_incorrect(incorrect_cards)
                    sys.exit()
            
            for i in range(boxes_num):
                if (len(boxes_queue[i]) >= len(boxes[i])):
                    boxes_queue[i].clear()
            
            order_index += 1
            if order_index >= len(boxes_order):
                order_index = 0

    except KeyboardInterrupt:
        clear_cli()
        print(f"Score: {str(correct_count)}/{str(total_count)}")
        print("")
        print_incorrect(incorrect_cards)
        exit(0)

class Result(Enum):
    EXIT = 0
    CORRECT = 1
    INCORRECT = -1

def biased_shuffle (list, queue):
    # if list is empty, return false
    if not list:
        return False
    
    # create list of elements not in queue
    not_in_queue = list.copy()
    for card in queue:
        if card in not_in_queue:
            not_in_queue.remove(card)

    # if all elements are in queue, return false
    if not not_in_queue:
        return False
    
    random_selection = random.choice(not_in_queue)

    # add selected card to queue
    queue.append(random_selection)
    return random_selection

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

if __name__ == "__main__":
    main()  # Or your main function entry point