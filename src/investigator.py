from src.npi_tool import fetch_npi_data
from src.geo_tool import validate_address_osm
from src.web_tool import find_provider_url
from src.phone_tool import validate_phone  # NEW IMPORT
import json

class InvestigatorAgent:
    """
    Orchestrates the data gathering process for a healthcare provider.
    Combines NPI Registry data, Geo-verification, Web Presence search, and Phone Validation.
    """
    
    def process_provider(self, npi_id: str) -> dict:
        """
        Runs the full investigation flow for a given NPI ID.
        """
        # Initialize Audit Log
        logs = []
        logs.append(f"Investigator: Starting investigation for NPI: {npi_id}")
        
        print(f"--- Starting Investigation for NPI: {npi_id} ---")
        
        # Step 1: Fetch Official NPI Data
        print("Step 1: Querying NPI Registry...")
        logs.append("Investigator: Querying CMS NPI Registry API...")
        
        npi_data = fetch_npi_data(npi_id)
        
        if not npi_data:
            msg = "Investigator: NPI not found or invalid in CMS Registry."
            print(msg)
            logs.append(msg)
            return {'status': 'INVALID_NPI', 'audit_log': logs}
            
        # Log success details
        entity_name = f"{npi_data.get('first_name', '')} {npi_data.get('last_name', '')} {npi_data.get('organization_name', '')}".strip()
        logs.append(f"Investigator: Successfully fetched NPI record for {entity_name}")

        # Step 2: Extract Address for Verification
        address_str = npi_data.get('address')
        
        # Step 3: Geo-Verification
        print(f"Step 2: Verifying physical address: {address_str}")
        logs.append(f"Investigator: Verifying physical address '{address_str}' via OpenStreetMap...")
        
        geo_data = None
        if address_str:
            geo_data = validate_address_osm(address_str)
            if geo_data:
                 match_type = geo_data.get('match_type', 'UNKNOWN')
                 logs.append(f"Investigator: Address verified. Match Type: {match_type}")
            else:
                 logs.append("Investigator: Address validation failed or returned no results.")
        else:
            msg = "Investigator: No physical address found in NPI record to verify."
            print(msg)
            logs.append(msg)
            
        # --- Step 3.5: Phone Validation (NEW) ---
        raw_phone = npi_data.get('phone')
        phone_data = None
        
        if raw_phone:
            logs.append(f"Investigator: Validating phone number '{raw_phone}'...")
            phone_data = validate_phone(raw_phone)
            
            if phone_data and phone_data.get('valid'):
                logs.append(f"Investigator: Phone number valid. Location: {phone_data.get('area_location')}")
            else:
                logs.append(f"Investigator: Phone validation failed. Error: {phone_data.get('error')}")
        else:
            logs.append("Investigator: No phone number found in NPI record.")

        # Step 4: Web Presence Search
        print("Step 3: Searching for web presence...")
        logs.append("Investigator: Initiating web presence search...")
        web_data = None
        
        first_name = npi_data.get('first_name', '')
        last_name = npi_data.get('last_name', '')
        organization_name = npi_data.get('organization_name', '')
        city = npi_data.get('city', '')
        state = npi_data.get('state', '')
        
        # Determine the search name: Use First+Last if available, otherwise Organization Name
        search_name = ""
        if first_name and last_name:
            search_name = f"{first_name} {last_name}"
        elif organization_name:
            search_name = organization_name
        
        if search_name and city and state:
            logs.append(f"Investigator: Searching for digital footprint using: '{search_name} {city} {state}'")
            web_data = find_provider_url(search_name, city, state)
            
            if web_data:
                official = web_data.get('official_site')
                social_count = len(web_data.get('social_media', []))
                dir_count = len(web_data.get('directories', []))
                
                if official:
                    logs.append(f"Investigator: Found Official URL: {official}")
                else:
                    logs.append("Investigator: No official website confirmed.")
                    
                logs.append(f"Investigator: Web search complete. Found {social_count} social profiles and {dir_count} directory listings.")
            else:
                logs.append("Investigator: Web search returned no results.")
        else:
            msg = f"Investigator: Insufficient data for web search. Name: '{search_name}', City: '{city}'"
            print(msg)
            logs.append(msg)

        # Step 5: Assemble Report
        investigation_report = {
            "npi_registry": npi_data,
            "geo_verification": geo_data,
            "phone_verification": phone_data, # Added to report
            "web_presence": web_data,
            "audit_log": logs
        }
        
        return investigation_report

if __name__ == "__main__":
    # Test Block
    agent = InvestigatorAgent()
    
    # Test with the Hospital NPI
    test_npi = '1952390643' 
    
    report = agent.process_provider(test_npi)
    
    print("\n--- FINAL INVESTIGATION REPORT ---")
    print(json.dumps(report, indent=2))