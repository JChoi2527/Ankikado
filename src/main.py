import sys
import json
import random
from os import system, name
from pathlib import Path
from enum import Enum
import argparse
from pynput import keyboard
import termios
import tty

# def get_input(prompt):
#     print(prompt, end='', flush=True)
#     user_input = []

#     def on_press(key):
#         try:
#             if key == keyboard.Key.enter or key == keyboard.Key.space:
#                 return False  # Stop listener
#             elif key == keyboard.Key.backspace:
#                 if user_input:
#                     user_input.pop()
#             else:
#                 user_input.append(key.char)
#         except AttributeError:
#             pass  # Ignore special keys

#     with keyboard.Listener(on_press=on_press) as listener:
#         listener.join()

#     print()  # Move to the next line
#     return ''.join(user_input)

def get_input(prompt):
    print(prompt, end='', flush=True)
    user_input = ""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            char = sys.stdin.read(1)
            if char == "\r" or char == " ":  # Enter or space
                break
            elif char == "\x7f":  # Backspace
                if user_input:
                    user_input = user_input[:-1]
                    print("\b \b", end='', flush=True)
            elif char == "\x03":  # Ctrl+C
                raise KeyboardInterrupt  # Simulate Ctrl+C interrupt
            else:
                user_input += char
                print(char, end='', flush=True)
    except KeyboardInterrupt:
        raise
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print()  # Move to the next line
    return user_input

def main():
    parser = argparse.ArgumentParser(description="Simple CLI flashcard program")
    parser.add_argument(
        "-d", "--deck",
        help="Specify flashcard deck",
        default="japanese"
    )

    args = parser.parse_args()
    path_string = "../json/" + str(args.deck) + ".json"
    path = Path(__file__).parent / path_string
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
            # every n cards, select random from incorrect_queue if it exists
            incorrect_len = len(incorrect_cards)

            if incorrect_len > 0:
                incorrect_period = 24 - (incorrect_len * 2)
                if incorrect_period < 5:
                    incorrect_period = 5

                if total_count % incorrect_period == 0:
                    random_card = biased_shuffle(incorrect_cards, incorrect_queue)
                else:
                    random_card = biased_shuffle(all_cards, all_queue)
            else:
                random_card = biased_shuffle(all_cards, all_queue)

            # print word
            print(random_card["front"])

            # prompt user for input and save it in a variable
            user_input = get_input("Answer: ")

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
                # for card in all_cards:
                #     if user_input == card["back"]:
                #         if not card in incorrect_cards:
                #             incorrect_cards.append(card)
                #         break
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
    if not cards:
        return False
    
    # create list of cards not in queue
    not_in_queue = cards.copy()
    for card in queue:
        # if card in not_in_queue:
        not_in_queue.remove(card)

    # if all cards are in queue, return false
    if not not_in_queue:
        return False
    
    random_card = random.choice(not_in_queue)

    # add selected card to queue, clear queue if all cards in queue
    queue.append(random_card)
    if len(queue) >= len(cards):
        queue.clear()
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

if __name__ == "__main__":
    main()  # Or your main function entry point