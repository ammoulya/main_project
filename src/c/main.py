#!/usr/bin/env python
import sys
import warnings
import os
from datetime import datetime
from c.crew import Automation



# warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Configuration - Move these to environment variables in production
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ACCOUNT = os.getenv("GITHUB_ACCOUNT")
DESTINATION_FOLDER = os.getenv("DESTINATION_FOLDER")
TARGET_REPO_PATH = os.getenv("TARGET_REPO_PATH")
# REPO_URL=os.getenv("REPO_URL")
def run():
    """Run the Automation crew."""
    try:
        # Initialize inputs for the crew
        inputs = {
            "github_account": os.getenv("GITHUB_ACCOUNT"),
            "destination_folder": os.getenv("DESTINATION_FOLDER"),
            "github_token": GITHUB_TOKEN,
            "target_repo_path": os.getenv("TARGET_REPO_PATH"),
            "repo_url": os.getenv("REPO_URL")  # ✅ add this
        }
        
        # Create and run the crew
        crew = Automation().crew()
        result = crew.kickoff(inputs=inputs)
        
        print("\n🎉 Crew execution completed!")
        print("\n📊 Results:")
        print(result)
        
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'github_token': GITHUB_TOKEN,
        'destination_folder': DESTINATION_FOLDER
    }
    try:
        Automation().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        Automation().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'github_token': GITHUB_TOKEN,
        'destination_folder': DESTINATION_FOLDER
    }
    
    try:
        Automation().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

if __name__ == "__main__":
    # Example of how to run specific functions based on command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "train":
            train()
        elif sys.argv[1] == "replay":
            replay()
        elif sys.argv[1] == "test":
            test()
        else:
            run()
    else:
        run()