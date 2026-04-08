Show the tasks from the Trello "AI To Do" list, let the developer pick one, implement it, confirm, then mark it done.

## Step-by-step

### 1. Fetch and display tasks

Run:
```
python trello/trello_client.py get-cards "AI To Do"
```

If the list is empty, tell the user and stop.

Present the cards as a numbered list with their names, for example:
```
Tasks in "AI To Do":
1. Fix gift category (should be gifts)
2. Showing list of items, show recent by date not by ID
3. ...
```

Ask the user: "Which task would you like to work on? (enter a number)"

Wait for the user's selection. Then get the full details of the chosen card:
```
python trello/trello_client.py get-card <card_id>
```

Print the card name and description so the user sees what you're working on.

### 2. Analyse and implement

Read the codebase as needed and implement the fix described by the card.
- Follow all rules in `.github/copilot-instructions.md`.
- Do not add unnecessary files, comments, or abstractions.
- When done, briefly summarise the changes made.

### 3. Confirm with the developer

Ask the user:
> "I've implemented the fix for **<card name>**. Here's a summary: <summary>. Does this look good? Reply **yes** to move the card to Done, or describe what to change."

Wait for the user's response. If they request changes, apply them and ask again. Repeat until they approve.

### 4. Mark as done

Once the user approves, run these three commands in sequence:
```
python trello/trello_client.py move-card <card_id> "Done"
python trello/trello_client.py mark-complete <card_id>
python trello/trello_client.py add-comment <card_id> "Implemented and confirmed by developer."
```

Confirm to the user that the card has been moved to Done and marked as complete.
