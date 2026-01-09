import requests
import json

def search_npi_by_name(name_search: str, state: str, last_name: str = None) -> str:
    """
    Searches for an NPI number using a name and state.
    
    Flexible Logic:
    1. If `last_name` is provided, searches for Individual (First Name + Last Name).
    2. If `last_name` is NOT provided:
       - First, searches as an Organization Name.
       - If no results, attempts to split `name_search` into First/Last and searches as Individual.
    
    Args:
        name_search (str): First name, Organization name, or Full Name.
        state (str): 2-letter State code.
        last_name (str, optional): Last name (if searching specifically for a person).
    """
    url = "https://npiregistry.cms.hhs.gov/api/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; StudentProject/1.0)'
    }
    
    # Helper to execute the request
    def _execute_search(params):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            print(f"NPI Search API Error: {e}")
            return []

    print(f"Searching Registry for: '{name_search}' (State: {state})")

    # Scenario A: Explicit First & Last Name provided
    if last_name:
        params = {
            'first_name': name_search,
            'last_name': last_name,
            'state': state,
            'version': '2.1'
        }
        results = _execute_search(params)
        if results:
            print(f"Found NPI (Individual): {results[0]['number']}")
            return str(results[0]['number'])
        return None

    # Scenario B: Single Name String Provided (Could be Org or Full Name)
    
    # 1. Try Organization Search First (Best for "Hospice", "Hospital", "Inc")
    org_params = {
        'organization_name': name_search,
        'state': state,
        'version': '2.1'
    }
    org_results = _execute_search(org_params)
    if org_results:
        print(f"Found NPI (Organization): {org_results[0]['number']}")
        return str(org_results[0]['number'])

    # 2. Fallback: Try Splitting Name into First/Last (Best for "John Doe")
    parts = name_search.split()
    if len(parts) >= 2:
        # Simple heuristic: First word is First Name, Last word is Last Name
        # (ignores middle names for simplicity, which is usually fine for search)
        f_name = parts[0]
        l_name = parts[-1]
        
        print(f"Organization search empty. Retrying as Individual: {f_name} {l_name}...")
        
        ind_params = {
            'first_name': f_name,
            'last_name': l_name,
            'state': state,
            'version': '2.1'
        }
        ind_results = _execute_search(ind_params)
        if ind_results:
            print(f"Found NPI (Individual Split): {ind_results[0]['number']}")
            return str(ind_results[0]['number'])

    print("No matching NPI found.")
    return None

def fetch_npi_data(npi_id: str = None, first_name: str = None, last_name: str = None, state: str = None, organization_name: str = None) -> dict:
    """
    Fetches provider data from the CMS NPI Registry API.
    Can lookup by NPI ID directly, or search by name if NPI is missing.
    """
    # 1. Handle Missing NPI -> Search by Name
    if not npi_id:
        if organization_name and state:
             npi_id = search_npi_by_name(organization_name, state)
        elif first_name and last_name and state:
            npi_id = search_npi_by_name(first_name, state, last_name=last_name)
        else:
            print("Error: Must provide either 'npi_id' OR 'first_name'+'last_name'+'state' OR 'organization_name'+'state'.")
            return None
            
        if not npi_id:
            return None

    # 2. Fetch Details using NPI ID
    url = "https://npiregistry.cms.hhs.gov/api/"
    params = {
        'number': npi_id,
        'version': '2.1'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; StudentProject/1.0)'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status() 
        
        data = response.json()

        if not data.get("results"):
            return None

        result = data["results"][0]
        basic_info = result.get("basic", {})

        # Extract fields
        f_name = basic_info.get("first_name", "")
        l_name = basic_info.get("last_name", "")
        org_name = basic_info.get("organization_name", "")
        credential = basic_info.get("credential", "")

        # Extract Physical Address (LOCATION)
        addresses = result.get("addresses", [])
        location_address = next(
            (addr for addr in addresses if addr.get("address_purpose") == "LOCATION"),
            None
        )

        full_address = "Address not found"
        city = ""
        st = ""
        phone_number = ""
        
        if location_address:
            line1 = location_address.get("address_1", "")
            city = location_address.get("city", "")
            st = location_address.get("state", "")
            postal_code = location_address.get("postal_code", "")[:5] 
            phone_number = location_address.get("telephone_number", "")
            
            full_address = f"{line1}, {city}, {st} {postal_code}"

        # Extract Taxonomy
        taxonomies = result.get("taxonomies", [])
        primary_taxonomy = next(
            (tax for tax in taxonomies if tax.get("primary") is True),
            None
        )
        
        if primary_taxonomy:
            specialty = primary_taxonomy.get("desc", "Unknown Specialty")
        elif taxonomies:
             specialty = taxonomies[0].get("desc", "Unknown Specialty")
        else:
            specialty = "Unknown Specialty"

        return {
            "npi": npi_id,
            "first_name": f_name,
            "last_name": l_name,
            "organization_name": org_name,
            "credential": credential,
            "address": full_address,
            "city": city,
            "state": st,
            "phone": phone_number,
            "specialty": specialty
        }

    except Exception as e:
        print(f"Unexpected Error in fetch_npi_data: {e}")
        return None

if __name__ == '__main__':
    # Test Block
    print("--- Test 1: Org Search (Napa Valley) ---")
    # This matches the call style that caused your error: search_npi_by_name(name, state)
    npi = search_npi_by_name("NAPA VALLEY HOSPICE & ADULT DAY SERVICES", "CA")
    
    if npi:
        print(f"Retrieving details for {npi}...")
        details = fetch_npi_data(npi_id=npi)
        print(details)
    else:
        print("Test 1 Failed.")