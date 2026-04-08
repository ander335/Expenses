import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TRELLO_API_KEY")
TOKEN = os.getenv("TRELLO_TOKEN")
BOARD_ID = "8BRA1S05"

BASE_URL = "https://api.trello.com/1"


def get_board():
    url = f"{BASE_URL}/boards/{BOARD_ID}"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_lists():
    url = f"{BASE_URL}/boards/{BOARD_ID}/lists"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_cards():
    url = f"{BASE_URL}/boards/{BOARD_ID}/cards"
    params = {"key": API_KEY, "token": TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    board = get_board()
    print(f"Board: {board['name']}\n")

    lists = get_lists()
    print("Lists:")
    for lst in lists:
        print(f"  - {lst['name']} (id: {lst['id']})")

    cards = get_cards()
    print(f"\nCards ({len(cards)} total):")
    for card in cards:
        print(f"  - {card['name']}")
