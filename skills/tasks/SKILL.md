---
name: tasks
description: Pick and implement a task from the Trello "AI To Do" list. Use this skill when the user says /tasks, "show tasks", "what's on the board", "pick a task", or wants to work on a Trello card.
---

1. **Fetch cards** — call `mcp__trello_expenses__list_cards` for the "AI To Do" list. If empty, stop and tell the user.

2. **Present and pick** — show a numbered list of card names. Ask: "Which task? (enter a number)"

3. **Load card** — call `mcp__trello_expenses__get_card` with the chosen card's ID. Show the name and description.

4. **Implement** — read the codebase as needed and implement the fix. Follow `.github/copilot-instructions.md`. No unnecessary files, comments, or abstractions.

5. **Confirm** — ask: "Done with **\<card name\>**: \<one-line summary\>. Look good? Reply yes to close it, or describe what to change." Repeat until approved.

6. **Close** — call `mcp__trello_expenses__move_card` to move the card to "Done", then `mcp__trello_expenses__comment_card` with `"Implemented and confirmed by developer."` Tell the user it's done.
