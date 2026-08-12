import os
import threading
import time
from agent import NovaAgent


def email_monitor_loop(agent):
    print("[Nova] Email monitor started.")
    while True:
        try:
            time.sleep(300)  # check every 5 minutes
            agent.registry.load_tools()
            if "check_inbox" in agent.registry.tools:
                emails = agent.registry.tools["check_inbox"]()
                if emails and "No" not in emails and "Error" not in emails:
                    print("\n[Nova] New emails detected, processing...")
                    response = agent.chat(
                        f"SYSTEM: New emails:\n\n{emails}\n\nReview and auto-respond if appropriate."
                    )
                    print(f"\nNova (email): {response}\nYou: ", end="", flush=True)
        except Exception as e:
            print(f"[Nova] Email monitor error: {e}")


def main():
    print("Starting Nova...")
    agent = NovaAgent()

    # Only start email monitor if credentials are configured
    if os.getenv("EMAIL_ADDRESS"):
        t = threading.Thread(target=email_monitor_loop, args=(agent,), daemon=True)
        t.start()

    print("\nNova ready. Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            response = agent.chat(user_input)
            print(f"\nNova: {response}\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
