import os
import json
from src.vision_tool import extract_provider_from_file
# Assuming your investigator script is structured as a class based on your description.
# If your investigator functions are standalone, you might need to adjust this import.
from src.investigator import InvestigatorAgent

def run_hybrid_pipeline():
    """
    Orchestrates the flow between Vision (Phase 2) and Investigation (Phase 1).
    """
    # 0. Setup
    image_path = "input_images/sample_doctor.jpg"
    output_dir = "output_logs"
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*50)
    print("STARTING HYBRID VERIFICATION PIPELINE")
    print("="*50)

    # --- PHASE 2: THE VISIONARY ---
    print("\n--- Phase 2: Running Visionary Agent ---")
    print(f"Reading file: {image_path}")
    
    vision_data = extract_provider_from_file(image_path)
    
    if not vision_data:
        print("❌ Critical Error: Vision Agent failed to read the document.")
        return

    print("✓ Vision Agent extraction successful.")
    print(f"Extracted Provider: {vision_data.get('provider_name', 'Unknown')}")
    print(f"Extracted NPI: {vision_data.get('npi_number', 'None')}")

    # --- PHASE 1: THE INVESTIGATOR ---
    print("\n--- Phase 1: Running Investigator Agent ---")
    
    npi = vision_data.get("npi_number")
    final_report = {
        "source_document": image_path,
        "vision_extraction": vision_data,
        "investigation_result": None,
        "status": "pending"
    }

    if npi:
        print(f"Valid NPI found ({npi}). Initiating background check...")
        try:
            # Initialize the investigator
            investigator = InvestigatorAgent()
            
            # Run the investigation
            # Passing the whole NPI string. The agent should handle validation.
            investigation_result = investigator.investigate_provider(npi)
            
            final_report["investigation_result"] = investigation_result
            final_report["status"] = "complete"
            print("✓ Investigation complete.")
            
        except Exception as e:
            print(f"❌ Error during investigation: {e}")
            final_report["status"] = "investigation_failed"
            final_report["error"] = str(e)
    else:
        print("⚠️ Alert: No NPI number found in document.")
        print("Skipping automated registry lookup. Manual review required.")
        final_report["status"] = "manual_review_required"

    # --- FINAL REPORTING ---
    print("\n" + "="*50)
    print("FINAL HYBRID REPORT")
    print("="*50)
    
    # Pretty print to console
    print(json.dumps(final_report, indent=2))
    
    # Save to file
    output_file = os.path.join(output_dir, "final_report.json")
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
        
    print(f"\n✓ Report saved to: {output_file}")

if __name__ == "__main__":
    run_hybrid_pipeline()