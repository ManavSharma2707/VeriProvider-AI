import requests
import json

def search_npi_by_name(first_name: str, last_name: str, state: str) -> str:
    """
    Searches for an NPI number using provider name and state.
    Returns the NPI as a string if exactly one or more matches are found.
    """
    url = "https://npiregistry.cms.hhs.gov/api/"
    params = {
        'first_name': first_name,
        'last_name': last_name,
        'state': state,
        'version': '2.1'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; StudentProject/1.0)'
    }

    try:
        print(f"Searching NPI Registry for: {first_name} {last_name} ({state})...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        
        if not results:
            print("No matching NPI found.")
            return None
        
        if len(results) > 1:
            print(f"Warning: Found {len(results)} matches. Defaulting to the first result.")
            
        found_npi = str(results[0].get("number"))
        print(f"Found NPI: {found_npi}")
        return found_npi

    except Exception as e:
        print(f"NPI Search failed: {e}")
        return None

def fetch_npi_data(npi_id: str = None, first_name: str = None, last_name: str = None, state: str = None) -> dict:
    """
    Fetches provider data from the CMS NPI Registry API.
    Can lookup by NPI ID directly, or search by name if NPI is missing.
    """
    # 1. Handle Missing NPI -> Search by Name
    if not npi_id:
        if first_name and last_name and state:
            npi_id = search_npi_by_name(first_name, last_name, state)
            if not npi_id:
                return None
        else:
            print("Error: Must provide either 'npi_id' OR 'first_name', 'last_name', and 'state'.")
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

        # Check if we got valid results
        if not data.get("results"):
            return None

        result = data["results"][0]
        basic_info = result.get("basic", {})

        # Extract Name (Individual or Organization) and Credential
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
            
            # --- NEW: Extract Phone Number ---
            phone_number = location_address.get("telephone_number", "")

            full_address = f"{line1}, {city}, {st} {postal_code}"

        # Extract Taxonomy (Specialty)
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
            "phone": phone_number,  # Added Field
            "specialty": specialty
        }

    except requests.RequestException as e:
        print(f"API Request Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return None

if __name__ == '__main__':
    # Test Block
    print("--- Test 1: Direct NPI Lookup (Providence Hospital) ---")
    data1 = fetch_npi_data(npi_id='1952390643')
    if data1:
        print(f"Success: Found {data1.get('organization_name')}")
        print(f"Phone: {data1.get('phone')}")
    
    print("\n--- Test 2: Name Search (Ashish Jha, RI) ---")
    data2 = fetch_npi_data(first_name="Ashish", last_name="Jha", state="RI")
    if data2:
        print(f"Success: Found NPI {data2.get('npi')}")
        print(f"Phone: {data2.get('phone')}")