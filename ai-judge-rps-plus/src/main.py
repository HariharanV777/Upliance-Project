import json
import os
from pathlib import Path
import random
from google import genai



def load_system_prompt():
    """Load the system prompt from file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "judge_prompt.txt"
    with open(prompt_path, "r") as f:
        return f.read()


def initialize_game():
    """Initialize game state."""
    return {
        "round_number": 1,
        "player1_bomb_used": False,
        "player2_bomb_used": False,
        "rounds": [],  # History of round results
    }


def play_round(client, system_prompt, game_state, player2_input, player1_move=None):
    """
    Execute a single round of the game.
    
    Args:
        client: Gemini API client
        system_prompt: The system prompt (judge instructions)
        game_state: Current game state (round number, bomb usage)
        player2_input: The player's free-text move input
        player1_move: The AI's move (can be None if only evaluating player input)
    
    Returns:
        dict: Judge's decision with structured output
    """
    
    # Prepare game context for the judge
    game_context = {
        "round_number": game_state["round_number"],
        "player1_move": player1_move,
        "player2_move": player2_input,
        "player1_bomb_used": game_state["player1_bomb_used"],
        "player2_bomb_used": game_state["player2_bomb_used"],
    }
    
    # Build the message to send to Gemini
    user_message = f"""
Please evaluate this round:

{json.dumps(game_context, indent=2)}

Remember to output VALID JSON with the structure defined in your instructions.
"""
    # If client is None, we're in MOCK mode (local testing without Gemini API)
    if client is None:
        judge_decision = mock_judge_response(system_prompt, game_context)
    else:
        # Call Gemini API using the client (updated pattern)
        try:
            response = client.generate_text(
                model="gemini-1.5",
                prompt=system_prompt + "\n" + user_message
            )
            response_text = response.text
        except Exception as e:
            print("Gemini API failed, using mock mode:", e)
            judge_decision = mock_judge_response(system_prompt, game_context)
        else:
            # Extract JSON from response (handle markdown code blocks if present)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            judge_decision = json.loads(response_text.strip())
    
    # Update game state based on judge's decision
    if judge_decision["final_result"]["move_accepted"]:
        game_state["player1_bomb_used"] = judge_decision["state_update"]["player1_bomb_used"]
        game_state["player2_bomb_used"] = judge_decision["state_update"]["player2_bomb_used"]
    
    # Store round result
    game_state["rounds"].append(judge_decision)
    
    return judge_decision


def print_round_result(judge_decision):
    """Pretty-print the judge's decision for this round."""
    print("\n" + "="*70)
    print(f"ROUND {judge_decision['round_number']}")
    print("="*70)
    
    # Intent Understanding
    print("\n[INTENT UNDERSTANDING]")
    print(f"  Raw Input: {judge_decision['player2_raw_input']}")
    print(f"  Move Understood: {judge_decision['intent_understanding']['move_understood']}")
    print(f"  Reasoning: {judge_decision['intent_understanding']['reasoning']}")
    
    # Validation
    print(f"\n[VALIDATION]")
    print(f"  Status: {judge_decision['validation']['status']}")
    print(f"  Reason: {judge_decision['validation']['reason']}")
    
    # Game Logic
    if judge_decision['validation']['status'] == 'VALID':
        print(f"\n[GAME LOGIC]")
        print(f"  Player 1 Move: {judge_decision['game_logic']['player1_move']}")
        print(f"  Player 2 Move: {judge_decision['game_logic']['player2_move']}")
        print(f"  Round Winner: {judge_decision['game_logic']['round_winner']}")
        print(f"  Explanation: {judge_decision['game_logic']['round_explanation']}")
    
    # State Update
    print(f"\n[STATE UPDATE]")
    print(f"  Player 1 Bomb Used: {judge_decision['state_update']['player1_bomb_used']}")
    print(f"  Player 2 Bomb Used: {judge_decision['state_update']['player2_bomb_used']}")
    print(f"  Bombs Remaining: P1={judge_decision['state_update']['bombs_remaining']['player1']}, "
          f"P2={judge_decision['state_update']['bombs_remaining']['player2']}")
    
    # Final Result
    print(f"\n[RESULT]")
    print(f"  Move Accepted: {judge_decision['final_result']['move_accepted']}")
    print(f"  Action: {judge_decision['final_result']['action']}")
    print(f"  Message: {judge_decision['final_result']['player_message']}")


def mock_judge_response(system_prompt, game_context):
    """
    MOCK JUDGE: Minimal local judge implementation for testing without Gemini.
    This is a testing fallback only and intentionally contains simple logic.
    It returns the same strict JSON schema that the real prompt expects.
    """
    raw = game_context.get("player2_move") or ""
    raw_l = raw.lower()

    # Intent heuristics (simple keyword matching)
    move_map = {
        "rock": ["rock", "rok", "stone", "boulder", "fist"],
        "paper": ["paper", "ppr", "pap", "sheet", "document"],
        "scissors": ["scissors", "scissor", "sciz", "snip", "shears"],
        "bomb": ["bomb", "boom", "nuke", "dynamite", "c4", "explosion"]
    }

    move_understood = None
    for mv, keys in move_map.items():
        for k in keys:
            if k in raw_l:
                move_understood = mv
                break
        if move_understood:
            break

    # Refusals
    refuses = ["pass", "skip", "i don't want", "dont want", "not play", "nope"]
    if any(r in raw_l for r in refuses):
        move_understood = None

    # Validation
    if move_understood is None:
        validation_status = "UNCLEAR"
        validation_reason = "Could not determine move from input."
    elif move_understood == "bomb" and game_context.get("player2_bomb_used"):
        validation_status = "INVALID"
        validation_reason = "Bomb already used by player 2."
    else:
        validation_status = "VALID"
        validation_reason = "Move recognized and constraints satisfied."

    # Simple game logic
    p1 = game_context.get("player1_move")
    p2 = move_understood
    round_winner = None
    round_explanation = "No winner determined."

    if validation_status == "VALID":
        # Handle bombs
        if p1 == p2:
            round_winner = "draw"
            round_explanation = f"Both players played {p1}. It's a draw."
        elif p1 == "bomb" and p2 == "bomb":
            round_winner = "draw"
            round_explanation = "Both players used bomb. Draw."
        elif p1 == "bomb":
            round_winner = "player1"
            round_explanation = "Player1's bomb beats player2's move."
        elif p2 == "bomb":
            round_winner = "player2"
            round_explanation = "Player2's bomb beats player1's move."
        else:
            # Standard RPS
            beats = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
            if beats.get(p1) == p2:
                round_winner = "player1"
                round_explanation = f"{p1} beats {p2}."
            elif beats.get(p2) == p1:
                round_winner = "player2"
                round_explanation = f"{p2} beats {p1}."
            else:
                round_winner = "draw"
                round_explanation = "No clear winner (unexpected input)."

    # State updates
    p1_bomb = bool(game_context.get("player1_bomb_used"))
    p2_bomb = bool(game_context.get("player2_bomb_used"))
    if validation_status == "VALID" and p2 == "bomb":
        p2_bomb = True

    response = {
        "round_number": game_context.get("round_number"),
        "player2_raw_input": raw,
        "intent_understanding": {
            "move_understood": p2 if p2 is not None else None,
            "reasoning": "Matched keywords heuristically in mock mode."
        },
        "validation": {
            "status": validation_status,
            "reason": validation_reason
        },
        "game_logic": {
            "player1_move": p1,
            "player2_move": p2 if p2 is not None else None,
            "round_winner": round_winner,
            "round_explanation": round_explanation
        },
        "state_update": {
            "player1_bomb_used": p1_bomb,
            "player2_bomb_used": p2_bomb,
            "bombs_remaining": {
                "player1": "0" if p1_bomb else "1",
                "player2": "0" if p2_bomb else "1"
            }
        },
        "final_result": {
            "move_accepted": validation_status == "VALID",
            "action": "PLAYED" if validation_status == "VALID" else ("REJECTED" if validation_status == "INVALID" else "UNCLEAR_MOVE"),
            "player_message": "(MOCK) " + ("Move accepted." if validation_status == "VALID" else validation_reason)
        }
    }

    return response


def main():
    """Main game loop."""
    
    # Initialize Gemini API (or fall back to MOCK mode for local testing)
    api_key = "AIzaSyBsw0xocQJt55aupu-cn9W5Wi7V0BqIMZo"#paste your API key here for testing, or set GEMINI_API_KEY env variable
    mock_mode = os.getenv("MOCK_GEMINI", "0") == "1"

    if not api_key and not mock_mode:
        print("WARNING: GEMINI_API_KEY not set. Starting in MOCK mode for local testing.")
        mock_mode = True

    if mock_mode:
        client = None
    else:
        # Initialize Gemini client with API key
        client = genai.Client(api_key=api_key)

    
    # Load system prompt
    system_prompt = load_system_prompt()
    
    # Initialize game state
    game_state = initialize_game()
    
    print("\n" + "="*70)
    print("ROCK-PAPER-SCISSORS PLUS: AI JUDGE")
    print("="*70)
    print("\nWelcome! The AI Judge will evaluate your moves.")
    print("Valid moves: rock, paper, scissors, bomb")
    print("(Bomb can be used only once per player)\n")
    
    # Game loop
    while True:
        print(f"\n--- Round {game_state['round_number']} ---")
        
        # Get player input
        player_input = input("Your move: ").strip()
        
        if player_input.lower() in ["quit", "exit", "q"]:
            print("\nThanks for playing!")
            break
        
        if not player_input:
            print("Please provide a move.")
            continue
        
       
        # The judge will evaluate both moves
        ai_move =random.choice(["rock","paper","scissors","bomb"])

        
        # Play the round
        judge_decision = play_round(
            client,
            system_prompt,
            game_state,
            player_input,
            ai_move
        )
        
        # Display result
        print_round_result(judge_decision)
        
        # Move to next round
        game_state["round_number"] += 1

        # After every 3 rounds evaluate overall winner and reset game for another match
        if len(game_state["rounds"]) % 3 == 0:
            last_three = game_state["rounds"][-3:]
            user_wins = 0
            bot_wins = 0
            draws = 0
            for rd in last_three:
                rw = rd.get("game_logic", {}).get("round_winner")
                if rw == "player2":
                    user_wins += 1
                elif rw == "player1":
                    bot_wins += 1
                else:
                    draws += 1

            if user_wins > bot_wins:
                final = "User wins"
            elif bot_wins > user_wins:
                final = "Bot wins"
            else:
                final = "Draw"

            print("\n" + "="*70)
            print("FINAL RESULT FOR THE LAST 3 ROUNDS:")
            print(f"  User wins: {user_wins}, Bot wins: {bot_wins}, Draws: {draws}")
            print(f"\nFinal result: {final}")
            print("="*70 + "\n")

            # Reset game state to start another 3-round match
            game_state = initialize_game()
          

if __name__ == "__main__":
    main()

