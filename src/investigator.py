from src.npi_tool import fetch_npi_data
from src.geo_tool import validate_address_osm
from src.web_tool import find_provider_url, verify_address_claim
from src.phone_tool import validate_phone
import json

class InvestigatorAgent:
    """
    Orchestrates the data gathering process for a healthcare provider.
    Combines NPI Registry data, Geo-verification, Web Presence search, and Phone Validation.
    Now supports verification of claimed data (Self-Attested Data).
    """
    
    def process_provider(self, npi_id: str, claimed_name: str = None, claimed_address: str = None, claimed_phone: str = None) -> dict:
        """
        Runs the full investigation flow for a given NPI ID.
        Supports optional verification of claimed details provided by the user/application.
        
        Args:
            npi_id (str): The 10-digit National Provider Identifier.
            claimed_name (str, optional): Name claimed by the provider.
            claimed_address (str, optional): Address claimed by the provider.
            claimed_phone (str, optional): Phone number claimed by the provider.
            
        Returns:
            dict: Comprehensive investigation report.
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
        
        # Step 3: Geo-Verification (Official Address)
        print(f"Step 2: Verifying official address: {address_str}")
        logs.append(f"Investigator: Verifying official address '{address_str}' via OpenStreetMap...")
        
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
            
        # Step 4: Phone Validation (Official & Claimed)
        
        # 4a. Official Phone (from NPI)
        raw_phone = npi_data.get('phone')
        phone_data = None
        if raw_phone:
            logs.append(f"Investigator: Validating official phone '{raw_phone}'...")
            phone_data = validate_phone(raw_phone)
        else:
            logs.append("Investigator: No official phone number found in NPI record.")

        # 4b. Claimed Phone (Input)
        claimed_phone_data = None
        if claimed_phone:
            logs.append(f"Investigator: Validating claimed phone '{claimed_phone}'...")
            claimed_phone_data = validate_phone(claimed_phone)
            if claimed_phone_data and claimed_phone_data.get('valid'):
                logs.append("Investigator: Claimed phone is a valid number.")
            else:
                logs.append("Investigator: Claimed phone is invalid.")

        # Step 5: Web Presence & Claim Verification
        print("Step 3: Searching for web presence...")
        logs.append("Investigator: Initiating web presence search...")
        web_data = None
        address_confirmation_links = []
        
        # Use claimed name if provided, else official name
        first_name = npi_data.get('first_name', '')
        last_name = npi_data.get('last_name', '')
        organization_name = npi_data.get('organization_name', '')
        
        # Determine the primary search name
        search_name = ""
        if claimed_name:
            search_name = claimed_name
        elif first_name and last_name:
            search_name = f"{first_name} {last_name}"
        elif organization_name:
            search_name = organization_name
            
        city = npi_data.get('city', '')
        state = npi_data.get('state', '')
        
        # 5a. General Web Footprint
        if search_name and city and state:
            logs.append(f"Investigator: Searching for digital footprint using: '{search_name} {city} {state}'")
            web_data = find_provider_url(search_name, city, state)
            
            if web_data:
                official = web_data.get('official_site')
                if official:
                    logs.append(f"Investigator: Found Official URL: {official}")
                else:
                    logs.append("Investigator: No official website confirmed.")
            else:
                logs.append("Investigator: Web search returned no results.")
        else:
            logs.append("Investigator: Insufficient data for web search.")

        # 5b. Specific Address Claim Search
        if claimed_address:
            logs.append(f"Investigator: Verifying claimed address '{claimed_address}' on the web...")
            # We search for the name + claimed address to find third-party confirmation
            target_name = claimed_name if claimed_name else search_name
            if target_name:
                address_confirmation_links = verify_address_claim(target_name, claimed_address)
                logs.append(f"Investigator: Found {len(address_confirmation_links)} links mentioning the claimed address.")
            else:
                logs.append("Investigator: Cannot verify address claim without a valid name.")

        # Step 6: Assemble Report
        investigation_report = {
            "npi_registry": npi_data,
            "geo_verification": geo_data,
            "phone_verification": phone_data,       # Official
            "claimed_phone_verification": claimed_phone_data, # NEW: Claimed
            "web_presence": web_data,
            "address_confirmation_links": address_confirmation_links, # NEW: Address Links
            "audit_log": logs
        }
        
        return investigation_report

if __name__ == "__main__":
    # Test Block
    agent = InvestigatorAgent()
    
    test_npi = '1952390643' 
    # Simulate a claim (e.g., user provides a slightly different address or phone)
    fake_claimed_addr = "6801 Airport Blvd"
    fake_claimed_phone = "251-633-1000" 
    
    print(f"Testing with claims for NPI {test_npi}...")
    report = agent.process_provider(
        test_npi, 
        claimed_address=fake_claimed_addr, 
        claimed_phone=fake_claimed_phone
    )
    
    print("\n--- FINAL INVESTIGATION REPORT ---")
    print(json.dumps(report, indent=2))