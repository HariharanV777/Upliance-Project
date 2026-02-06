# AI Judge for Rock-Paper-Scissors Plus

A **prompt-driven AI Judge** for the Rock-Paper-Scissors Plus game using Google Gemini. This project demonstrates how to architect AI systems where **game logic lives primarily in the prompt**, not in code.

## Project Philosophy

### Why Prompt-Driven?

Traditional game logic is implemented as rules in code (if-else statements, state machines, etc.). This approach is:
- **Rigid**: Changes to rules require code changes and redeployment
- **Hard to explain**: Logic is scattered across functions
- **Difficult to test edge cases**: Requires adding more code

This project takes a **different approach**: the prompt acts as the "brain" that encodes all rules, constraints, and decision logic. The Python code is purely a **communication layer** that:
1. Loads the prompt
2. Formats game state as JSON
3. Sends it to Gemini
4. Parses and displays the result

### Gemini Optional & Mock Mode

- The project is deliberately *prompt-centric*: the AI Judge's logic, constraints, explanations, and decision-making live entirely in the system prompt (`prompts/judge_prompt.txt`).
- The Gemini integration is intentionally optional and replaceable. A lightweight *mock judge* is included in `src/main.py` so evaluators can run the project without API keys and focus on the quality of reasoning and the prompt design.
- For local testing the app will automatically fall back to mock mode when `GEMINI_API_KEY` is not set (or you can set `MOCK_GEMINI=1`). In production you can swap the mock for Gemini or any other LLM while using the same prompt as the single source of truth.

This is **more maintainable, explainable, and easier to test** for complex decision-making tasks.

---

## Architecture

The system separates concerns into three layers:

### Layer 1: Intent Understanding (in Prompt)
**What did the player actually mean?**

The AI Judge interprets free-text input to determine the player's move:
- Recognizes typos and common variations ("rok" → "rock", "ppr" → "paper")
- Detects ambiguous input (e.g., "something random" → UNCLEAR)
- Handles refusals to play ("pass" → INVALID)

**Why in prompt?**: NLP interpretation is complex and context-dependent. The prompt can guide Gemini with patterns and examples without hardcoding regex or parsing logic.

### Layer 2: Game Logic (in Prompt)
**Is the move valid? Who won?**

The AI Judge:
- Validates moves against game rules (rock beats scissors, paper beats rock, scissors beats paper)
- Enforces bomb constraints (can only be used once per player)
- Determines round winners based on game state
- Updates bomb usage tracking

**Why in prompt?**: All rules are explicitly documented in natural language, making them auditable and changeable without code changes.

### Layer 3: Response Generation (Hybrid)
**What does the player see?**

The prompt generates structured JSON output with:
- Validation status (VALID/INVALID/UNCLEAR)
- Explanation of every decision
- Updated game state
- Clear, actionable feedback for the player

The Python code then formats this JSON for human readability.

---

## Design Decisions

### 1. **Single AI Agent (Judge)**

The prompt describes a single agent acting as both referee and evaluator:
- The agent understands the player's move intent
- The agent validates it against game state
- The agent determines the winner
- The agent explains all decisions

This is simpler than multi-agent architectures and aligns with the project requirement for "minimal glue code only."

### 2. **Game State Lives in Code, Rules Live in Prompt**

**Minimal state tracked in Python:**
- Round number
- Bomb usage flags (which players have used their bomb)
- Round history

**Why?**: State management requires persistence, which is easier to handle in code. Rules don't need to be stateful—the prompt evaluates them fresh each round.

### 3. **JSON Structure for Explainability**

The prompt outputs strict JSON with this hierarchy:
```
{
  "intent_understanding": {...},  // What did they mean?
  "validation": {...},            // Is it valid?
  "game_logic": {...},            // Who won?
  "state_update": {...},          // New game state
  "final_result": {...}           // What to tell the player
}
```

This enforces that **every decision has a reason** and makes output machine-readable for potential extensions.

### 4. **No Hardcoded Game Logic in Python**

The main.py file **does not contain**:
- Move validation rules
- Win condition checks
- Bomb constraint enforcement
- Any if-else statements about game rules

This ensures the prompt is the single source of truth.

---

## Edge Cases Handled

### 1. Bomb Usage Violation
**Input:** User plays "bomb" when they've already used it
**Handling:** Prompt checks `player2_bomb_used` flag, marks as INVALID
**Output:** Clear message explaining bomb was already used and turn is wasted

### 2. Ambiguous Input
**Input:** "I'm not sure" or random text
**Handling:** Intent understanding fails, validation = UNCLEAR
**Output:** Request clarification without penalizing the player

### 3. Typos/Close Matches
**Input:** "rok" instead of "rock"
**Handling:** Charitable interpretation using the pattern-matching capability of LLMs
**Output:** Confirmed move interpretation, proceed with game

### 4. Refusal to Play
**Input:** "pass", "skip", "I don't want to play"
**Handling:** Not a valid move, validation = INVALID
**Output:** Penalty (turn is wasted) and request to play a valid move

### 5. Empty/Nonsense Input
**Input:** Empty string or "xyzabc"
**Handling:** Intent = null, validation = UNCLEAR
**Output:** Request for valid move without penalty if UNCLEAR

### 6. Bomb vs Bomb
**Input:** Both players play bomb
**Handling:** Special case in game logic (draw condition)
**Output:** Round is draw, both bomb flags set to used

---

## How to Run

### Setup

1. **Clone/navigate to the project:**
   ```bash
   cd ai-judge-rps-plus
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your Gemini API key:**
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```
   OR
   directly paste a temporary key in line 253 for easier testing
   (On Windows: `set GEMINI_API_KEY=your_api_key_here`)

### Play a Game

```bash
python src/main.py
```

Example session:
```
--- Round 1 ---
Your move: rock

[INTENT UNDERSTANDING]
  Raw Input: rock
  Move Understood: rock
  Reasoning: Clear move input

[VALIDATION]
  Status: VALID
  Reason: Rock is a recognized move and no constraints violated

[GAME LOGIC]
  Player 1 Move: rock
  Player 2 Move: rock
  Round Winner: draw
  Explanation: Both players played rock. Result: draw.

[STATE UPDATE]
  Player 1 Bomb Used: False
  Player 2 Bomb Used: False
  Bombs Remaining: P1=1, P2=1

[RESULT]
  Move Accepted: True
  Action: PLAYED
  Message: You played rock. Your opponent also played rock. It's a draw!
```

---

## Prompt Structure

The [judge_prompt.txt](prompts/judge_prompt.txt) is organized into sections:

1. **System Prompt Header**: Role and responsibilities
2. **Game Rules**: Valid moves, bomb constraints, win conditions
3. **Move Interpretation**: Patterns to recognize, ambiguity handling
4. **Input Format**: Expected JSON structure
5. **Decision Process**: 4-step framework (Intent → Validation → Logic → Response)
6. **Output Format**: Strict JSON schema
7. **Edge Cases**: Specific handling for tricky situations
8. **Explainability**: Requirement that every decision is reasoned
9. **Important Guardrails**: Prevent assumptions, enforce constraints

This structure ensures Gemini interprets the prompt consistently and doesn't skip steps.

---

## Constraints Met

✅ **Python-only**: No external services except Gemini  
✅ **Google Gemini**: Uses free tier (flash model for speed)  
✅ **No UI**: Command-line interface only  
✅ **No database**: Game state held in memory  
# AI Judge — Rock-Paper-Scissors Plus

Prompt-driven AI Judge where all rules, constraints, and explanations live in the system prompt (`prompts/judge_prompt.txt`). The Python code is a minimal communication layer that sends game state to an LLM and prints structured JSON results.

Key points
- Prompt-centric: All decision logic (intent parsing, validation, winner rules, explainability) is in the prompt, so behavior is auditable and easy to iterate.
- Gemini optional: The project supports Google Gemini but does not require it. A mock judge is included in `src/main.py` so reviewers can run the project without API keys.
- Separation of concerns: Intent understanding, game logic, and response generation are kept conceptually separate and expressed in the prompt.

Quick run
1. Install deps:
```powershell
py -3 -m pip install -r requirements.txt
```
2. Run (mock mode auto-enabled):
```powershell
py -3 src\\main.py
```

Files
- `prompts/judge_prompt.txt`: The full system prompt (single source of truth).
- `src/main.py`: Minimal runner + mock judge fallback for offline testing.
- `requirements.txt`: Python dependency list.

Why mock mode
- Let evaluators run and inspect judge outputs without setting API keys.
- Keeps focus on prompt quality, instruction clarity, and explainability.
- In production, swap the mock for Gemini (or any LLM) and use the same prompt.

If you want the README even shorter or want me to switch the client to `google.genai`, tell me which direction to trim or change.
- Rock-paper-scissors-bomb tournaments
