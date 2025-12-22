from abc import ABC, abstractmethod
import json
import time
import difflib  # For fuzzy string matching
import string   # For removing punctuation during normalization

# Import existing functional tools
try:
    from src.npi_tool import fetch_npi_data
    from src.geo_tool import validate_address_osm
    from src.web_tool import find_provider_url
    from src.phone_tool import validate_phone
except ImportError:
    print("Warning: Some tools could not be imported. Ensure src/ folder contains npi_tool.py etc.")

# --- 1. Abstraction for Verification Steps ---

class IVerificationStep(ABC):
    """Interface for a single investigation step."""
    @abstractmethod
    def execute(self, context: dict, logs: list) -> None:
        """
        Executes the step.
        :param context: A shared dictionary containing data accumulated so far.
        :param logs: A list to append audit logs to.
        """
        pass

# --- 2. Concrete Verification Steps (Wrappers) ---

class NpiRegistryStep(IVerificationStep):
    def execute(self, context: dict, logs: list) -> None:
        npi_id = context.get('target_npi')
        print("Step 1: Querying NPI Registry...")
        logs.append("Investigator: Querying CMS NPI Registry API...")
        
        try:
            npi_data = fetch_npi_data(npi_id)
        except NameError:
            npi_data = None # Handle case where import failed

        if not npi_data:
            logs.append("Investigator: NPI not found or invalid.")
            context['status'] = 'INVALID_NPI'
            context['npi_data'] = None
        else:
            context['npi_data'] = npi_data
            # We'll determine the display name in the next step or here for logging
            entity = npi_data.get('organization_name') or f"{npi_data.get('first_name','')} {npi_data.get('last_name','')}".strip()
            logs.append(f"Investigator: NPI record found for {entity}")

class NameVerificationStep(IVerificationStep):
    """
    Checks if the name extracted from the document matches the name in the NPI Registry.
    """
    def execute(self, context: dict, logs: list) -> None:
        npi_data = context.get('npi_data')
        vision_name = context.get('vision_name')
        
        # Call the helper to determine mismatch
        is_mismatch, ratio, registry_name = self._is_name_mismatch(vision_name, npi_data)
        
        # Store registry name for later steps (like web search)
        if registry_name:
            context['registry_name'] = registry_name
            
        print(f"Step 1.5: Verifying Name Match (Similarity: {ratio*100:.1f}%)")

        if is_mismatch:
            percent = f"{ratio*100:.1f}"
            warning = (f"WARNING: Identity mismatch! Document Name ({vision_name}) "
                       f"vs Registry ({registry_name}) is {percent}% match.")
            logs.append(f"Investigator: ⚠️ {warning}")
            context['name_mismatch_flag'] = True
        else:
            if vision_name and registry_name:
                logs.append(f"Investigator: Name match confirmed ({ratio*100:.1f}%).")
            context['name_mismatch_flag'] = False

    def _is_name_mismatch(self, vision_name, registry_data):
        """
        Helper method to check for name mismatches with normalization.
        Returns: (is_mismatch: bool, ratio: float, registry_name: str)
        """
        # Step A: Determine Registry Name
        if not registry_data:
            return False, 0.0, ""
            
        registry_name = registry_data.get('organization_name')
        if not registry_name:
            registry_name = f"{registry_data.get('first_name', '')} {registry_data.get('last_name', '')}".strip()
            
        # Step B: Check for missing data (Skip check)
        if not vision_name or not registry_name:
            return False, 0.0, registry_name
            
        # Step C: Normalize strings
        def normalize(s):
            if not s: return ""
            # Lowercase and remove punctuation
            return s.lower().translate(str.maketrans('', '', string.punctuation))
            
        v_norm = normalize(vision_name)
        r_norm = normalize(registry_name)
        
        # Step D: Calculate similarity
        ratio = difflib.SequenceMatcher(None, v_norm, r_norm).ratio()
        
        # Step E: Define Threshold (0.60)
        # If ratio < 0.60 (60%), set mismatch = True
        is_mismatch = ratio < 0.60
        
        return is_mismatch, ratio, registry_name

class GeoVerificationStep(IVerificationStep):
    def execute(self, context: dict, logs: list) -> None:
        npi_data = context.get('npi_data')
        if not npi_data: return

        address = npi_data.get('address')
        print(f"Step 2: Verifying address: {address}")
        logs.append(f"Investigator: Verifying address '{address}'...")

        if address:
            try:
                geo_data = validate_address_osm(address)
                context['geo_data'] = geo_data
                match = geo_data.get('match_type', 'UNKNOWN') if geo_data else 'NONE'
                logs.append(f"Investigator: Address verified. Match: {match}")
            except Exception as e:
                logs.append(f"Investigator: Geo-tool error: {e}")
                context['geo_data'] = None
        else:
            logs.append("Investigator: No address to verify.")

class PhoneValidationStep(IVerificationStep):
    def execute(self, context: dict, logs: list) -> None:
        npi_data = context.get('npi_data')
        if not npi_data: return

        raw_phone = npi_data.get('phone')
        if raw_phone:
            logs.append(f"Investigator: Validating phone '{raw_phone}'...")
            try:
                phone_data = validate_phone(raw_phone)
                context['phone_data'] = phone_data
                if phone_data and phone_data.get('valid'):
                    logs.append(f"Investigator: Phone valid. Location: {phone_data.get('area_location')}")
                else:
                    logs.append("Investigator: Phone validation failed.")
            except Exception as e:
                logs.append(f"Investigator: Phone tool error: {e}")
        else:
            logs.append("Investigator: No phone number found.")

class WebPresenceStep(IVerificationStep):
    def execute(self, context: dict, logs: list) -> None:
        npi_data = context.get('npi_data')
        if not npi_data: return

        print("Step 3: Searching for web presence...")
        logs.append("Investigator: Initiating web presence search...")

        # Construct search query
        search_name = context.get('registry_name', '')
        city = npi_data.get('city', '')
        state = npi_data.get('state', '')

        if search_name and city and state:
            try:
                web_data = find_provider_url(search_name, city, state)
                context['web_data'] = web_data
                
                if web_data:
                    official = web_data.get('official_site')
                    social_count = len(web_data.get('social_media', []))
                    dir_count = len(web_data.get('directories', []))
                    
                    if official:
                        logs.append(f"Investigator: Found Official Website: {official}")
                    
                    if not official and social_count == 0 and dir_count == 0:
                        logs.append("Investigator: Web search returned no results (0 profiles).")
                    else:
                        logs.append(f"Investigator: Web search complete. Found {social_count} social profiles and {dir_count} directories.")
                else:
                    logs.append("Investigator: Web search returned no results.")
            except Exception as e:
                logs.append(f"Investigator: Web tool error: {e}")
        else:
            logs.append("Investigator: Insufficient data for web search.")

# --- 3. The Investigator Agent (Context Manager) ---

class InvestigatorAgent:
    def __init__(self):
        # Configure the pipeline of steps
        self.steps = [
            NpiRegistryStep(),
            NameVerificationStep(),
            GeoVerificationStep(),
            PhoneValidationStep(),
            WebPresenceStep()
        ]

    def investigate_provider(self, npi_number: str, vision_name: str = None) -> dict:
        """
        Main entry point called by main_hybrid.py.
        """
        return self.process_provider(npi_number, vision_name)

    def process_provider(self, npi_id: str, vision_name: str = None) -> dict:
        logs = []
        logs.append(f"Investigator: Starting investigation for NPI: {npi_id}")
        print(f"--- Starting Investigation for NPI: {npi_id} ---")

        # Shared Context with Vision Name
        context = {
            'target_npi': npi_id, 
            'vision_name': vision_name,
            'status': 'PENDING'
        }

        # Execute all steps
        for step in self.steps:
            # Stop if NPI was invalid in the first step
            if context.get('status') == 'INVALID_NPI':
                break
            step.execute(context, logs)

        # Assemble Report
        return {
            "npi_registry": context.get('npi_data'),
            "geo_verification": context.get('geo_data'),
            "phone_verification": context.get('phone_data'),
            "web_presence": context.get('web_data'),
            "name_mismatch_flag": context.get('name_mismatch_flag', False),
            "audit_log": logs,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

if __name__ == "__main__":
    agent = InvestigatorAgent()
    # Test Mismatch Logic
    print("Testing Mismatch...")
    # This should now trigger a mismatch warning
    report = agent.process_provider('1457890234', vision_name="Terminator Health")
    print(json.dumps(report, indent=2))