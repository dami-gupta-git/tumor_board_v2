"""Development server for TumorBoard Flask API."""

import os
import sys

# Add parent directory to path so we can import tumorboard
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from backend.app import app

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Verify OpenAI API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable is not set!")
        print("Set it in .env file or export it in your shell")

    # Run development server
    print("Starting TumorBoard API server...")
    print("API available at: http://localhost:5000")
    print("Health check: http://localhost:5000/api/health")
    print("Press Ctrl+C to stop")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
