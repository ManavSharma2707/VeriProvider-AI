import os
import json
import re
from src.vision_tool import extract_provider_from_file
from src.investigator import InvestigatorAgent

# Try to import the search tool, or define a fallback if it doesn't exist yet
try:
    from src.npi_tool import search_npi_by_name
except ImportError:
    def search_npi_by_name(name, state):
        print(f"   [System] Placeholder: 'search_npi_by_name' not found in npi_tool.py.")
        print(f"   [System] Would search for: '{name}' in '{state}'")
        return None

class VerificationPipeline:
    """
    Orchestrator class responsible for running the full Multi-Agent pipeline.
    """
    def __init__(self):
        # We use the helper function wrapper for Vision to keep it simple
        self.investigator_agent = InvestigatorAgent()
        self.output_dir = "output_logs"
        os.makedirs(self.output_dir, exist_ok=True)

    def _extract_state_from_address(self, address_raw):
        """
        Helper to extract a 2-letter US state code from an address string.
        """
        if not address_raw:
            return None
        
        # Regex looks for 2 uppercase letters surrounded by spaces or comma/digits
        # e.g., "Los Angeles, CA 90001" -> matches CA
        match = re.search(r'\b([A-Z]{2})\b', address_raw)
        if match:
            return match.group(1)
        return None

    def run(self, image_path: str):
        print("="*50)
        print("STARTING HYBRID VERIFICATION PIPELINE")
        print("="*50)

        # --- PHASE 2: VISION ---
        print("\n--- Phase 2: Running Visionary Agent ---")
        vision_data = extract_provider_from_file(image_path)

        if not vision_data:
            print("❌ Critical Error: Vision Agent failed.")
            return

        # Extract Claims
        npi = vision_data.get("npi_number")
        claimed_name = vision_data.get("provider_name")
        claimed_address = vision_data.get("address_raw")
        claimed_phone = vision_data.get("phone")
        
        print(f"Extracted Name: {claimed_name}")
        print(f"Extracted NPI:  {npi}")

        # --- FALLBACK LOGIC: FIND NPI IF MISSING ---
        if not npi:
            print("\n⚠️ No NPI in document. Attempting to find NPI by Name/Address...")
            
            if claimed_name:
                # Try to guess state from the address
                state_code = self._extract_state_from_address(claimed_address)
                print(f"   Searching Registry for: '{claimed_name}' (State: {state_code})")
                
                # Call NPI Search Tool
                found_npi = search_npi_by_name(claimed_name, state_code)
                
                if found_npi:
                    npi = found_npi
                    print(f"   ✓ Success: Found NPI {npi} for '{claimed_name}'")
                    # Update vision data to reflect the found NPI
                    vision_data['npi_number'] = npi
                    vision_data['npi_source'] = "inferred_by_search"
                else:
                    print("   ❌ Search failed. Could not locate NPI.")
            else:
                print("   ❌ Cannot search: Provider Name is also missing.")

        # --- PHASE 1: INVESTIGATION ---
        print("\n--- Phase 1: Running Investigator Agent ---")
        
        final_report = {
            "source_document": image_path,
            "vision_extraction": vision_data,
            "investigation_result": None,
            "status": "pending"
        }

        if npi:
            # Delegate to Investigator Agent
            # We pass the claimed name so the investigator can check for Identity Mismatch
            investigation_result = self.investigator_agent.process_provider(
                npi_id=npi, 
                claimed_name=claimed_name
            )
            
            final_report["investigation_result"] = investigation_result
            
            # Determine final status based on investigation flags
            if investigation_result.get('status') == 'INVALID_NPI':
                final_report["status"] = "failed_invalid_npi"
            elif investigation_result.get('name_mismatch_flag'):
                final_report["status"] = "warning_identity_mismatch"
            else:
                final_report["status"] = "complete"
                
            print("✓ Investigation complete.")
        else:
            print("⚠️ Status: UNVERIFIABLE_NO_NPI")
            print("Action: Manual review required.")
            final_report["status"] = "UNVERIFIABLE_NO_NPI"
            final_report["error"] = "NPI missing and search failed"

        self._save_report(final_report)

    def _save_report(self, report: dict):
        output_file = os.path.join(self.output_dir, "final_report.json")
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"\n✓ Report saved to: {output_file}")

if __name__ == "__main__":
    pipeline = VerificationPipeline()
    
    # You can change this to test different files
    target_image = "input_images/sample_doctor.jpg"
    
    pipeline.run(target_image)