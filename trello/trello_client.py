"""Generic Trello CLI client. Usage: python trello_client.py <command> [args]

Commands:
  get-lists                          List all lists on the board
  get-cards <list_name_or_id>        Get cards from a list (by name substring or ID)
  get-card <card_id>                 Get details of a specific card
  move-card <card_id> <list_name>    Move a card to a list (by name substring or ID)
  archive-card <card_id>             Archive (close) a card
  mark-complete <card_id>            Mark a card as complete (dueComplete=true)
  add-comment <card_id> <text>       Add a comment to a card
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

API_KEY = os.getenv("TRELLO_API_KEY")
TOKEN = os.getenv("TRELLO_TOKEN")
BOARD_ID = os.getenv("TRELLO_BOARD_ID", "8BRA1S05")

BASE_URL = "https://api.trello.com/1"


def _auth():
    return {"key": API_KEY, "token": TOKEN}


def _get(path, **params):
    r = requests.get(f"{BASE_URL}{path}", params={**_auth(), **params})
    r.raise_for_status()
    return r.json()


def _put(path, **data):
    r = requests.put(f"{BASE_URL}{path}", params=_auth(), json=data)
    r.raise_for_status()
    return r.json()


def _post(path, **data):
    r = requests.post(f"{BASE_URL}{path}", params=_auth(), json=data)
    r.raise_for_status()
    return r.json()


def get_lists():
    """Return all lists on the board."""
    return _get(f"/boards/{BOARD_ID}/lists")


def find_list(name_or_id):
    """Find a list by ID or case-insensitive name substring."""
    lists = get_lists()
    # exact ID match first
    for lst in lists:
        if lst["id"] == name_or_id:
            return lst
    # name substring match
    needle = name_or_id.lower()
    matches = [lst for lst in lists if needle in lst["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = [m["name"] for m in matches]
        raise ValueError(f"Ambiguous list name '{name_or_id}': matches {names}")
    raise ValueError(f"No list found matching '{name_or_id}'")


def get_cards(list_name_or_id):
    """Return cards in a list identified by name or ID."""
    lst = find_list(list_name_or_id)
    cards = _get(f"/lists/{lst['id']}/cards")
    return lst, cards


def get_card(card_id):
    """Return full card details."""
    return _get(f"/cards/{card_id}")


def move_card(card_id, list_name_or_id):
    """Move a card to the specified list."""
    lst = find_list(list_name_or_id)
    return _put(f"/cards/{card_id}", idList=lst["id"])


def archive_card(card_id):
    """Archive (close) a card."""
    return _put(f"/cards/{card_id}", closed=True)


def add_comment(card_id, text):
    """Add a comment to a card."""
    return _post(f"/cards/{card_id}/actions/comments", text=text)


def mark_complete(card_id):
    """Mark a card as complete (sets dueComplete=true)."""
    return _put(f"/cards/{card_id}", dueComplete=True)


def _print_json(data):
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "get-lists":
        lists = get_lists()
        for lst in lists:
            print(f"{lst['id']}  {lst['name']}")

    elif cmd == "get-cards":
        if len(sys.argv) < 3:
            print("Usage: get-cards <list_name_or_id>")
            sys.exit(1)
        lst, cards = get_cards(sys.argv[2])
        print(f"List: {lst['name']} ({lst['id']})")
        for c in cards:
            desc_preview = (c.get("desc") or "")[:80].replace("\n", " ")
            print(f"  {c['id']}  {c['name']}" + (f"  —  {desc_preview}" if desc_preview else ""))

    elif cmd == "get-card":
        if len(sys.argv) < 3:
            print("Usage: get-card <card_id>")
            sys.exit(1)
        _print_json(get_card(sys.argv[2]))

    elif cmd == "move-card":
        if len(sys.argv) < 4:
            print("Usage: move-card <card_id> <list_name_or_id>")
            sys.exit(1)
        result = move_card(sys.argv[2], sys.argv[3])
        print(f"Moved card '{result['name']}' to list '{result['idList']}'")

    elif cmd == "archive-card":
        if len(sys.argv) < 3:
            print("Usage: archive-card <card_id>")
            sys.exit(1)
        result = archive_card(sys.argv[2])
        print(f"Archived card '{result['name']}'")

    elif cmd == "add-comment":
        if len(sys.argv) < 4:
            print("Usage: add-comment <card_id> <text>")
            sys.exit(1)
        add_comment(sys.argv[2], sys.argv[3])
        print("Comment added.")

    elif cmd == "mark-complete":
        if len(sys.argv) < 3:
            print("Usage: mark-complete <card_id>")
            sys.exit(1)
        result = mark_complete(sys.argv[2])
        print(f"Marked card '{result['name']}' as complete.")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
