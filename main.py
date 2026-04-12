import os
import subprocess
import time

# Get port from environment or default to 5000
port = os.environ.get("PORT", "8080")

def main():
    print(f"--- Starting Flask web server on port {port} ---")
    # Start the Flask app as a background process
    # We use 'python3 app.py' because app.py contains the app.run() entry point
    flask_process = None
    try:
        # Pass the environment variables including PORT
        flask_process = subprocess.Popen(["python3", "app.py"])
        print(f"Flask process started with PID: {flask_process.pid}")
    except Exception as e:
        print(f"Failed to start Flask: {e}")

    # Give the web server a few seconds to initialize
    time.sleep(3)

    print("--- Starting Telegram Bot module (devgagan) ---")
    # Run the bot module in the main thread
    # This will keep the container running
    try:
        os.system("python3 -m devgagan")
    except Exception as e:
        print(f"Bot encountered an error: {e}")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    finally:
        if flask_process:
            print("Terminating Flask process...")
            flask_process.terminate()
            try:
                flask_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                flask_process.kill()
            print("Flask process shut down.")

if __name__ == "__main__":
    main()
