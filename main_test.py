from src.investigator import InvestigatorAgent
import json

def run_tests():
    # Instantiate the agent
    agent = InvestigatorAgent()

    # Define test cases
    test_npis = [
        "1952390643",  # Valid Doctor (should return full data)
        "0000000000"   # Invalid NPI (should return INVALID_NPI status)
    ]

    print("=== Starting Investigator Agent Tests ===\n")

    for npi in test_npis:
        print(f"Testing NPI: {npi}")
        try:
            result = agent.process_provider(npi)
            print(f"Result for {npi}:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"An error occurred while processing {npi}: {e}")
        
        print("-" * 50 + "\n")

if __name__ == "__main__":
    run_tests()