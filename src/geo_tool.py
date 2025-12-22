from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

def validate_address_osm(address_str: str) -> dict:
    """
    Validates an address using OpenStreetMap (Nominatim).
    Attempts an exact match first, then falls back to City/State level.
    Returns structured address components in the result.
    
    Args:
        address_str (str): The full address string (e.g. "123 Main St, Springfield, IL 62704")
        
    Returns:
        dict: Geolocation data including lat, lon, display_name, match_type, and components.
              Returns None if no location is found.
    """
    # MUST set a unique user_agent to comply with Nominatim usage policy
    geolocator = Nominatim(user_agent="VeriProvider_Student_Project")

    try:
        # 1. Attempt Exact Match
        # addressdetails=True ensures we get keys like 'road', 'city', 'state' in .raw['address']
        location = geolocator.geocode(address_str, timeout=10, addressdetails=True)
        
        if location:
            # Parse raw address components
            raw_addr = location.raw.get('address', {})
            
            # Try to construct a street string (Number + Road)
            street_part = raw_addr.get('road', '')
            house_num = raw_addr.get('house_number', '')
            full_street = f"{house_num} {street_part}".strip() if street_part else None
            
            components = {
                'street': full_street if full_street else None,
                'city': raw_addr.get('city') or raw_addr.get('town') or raw_addr.get('village'),
                'state': raw_addr.get('state'),
                'zip': raw_addr.get('postcode')
            }

            return {
                'lat': location.latitude,
                'lon': location.longitude,
                'osm_display_name': location.address,
                'match_type': 'EXACT',
                'components': components
            }

        # 2. Fallback: Try City/State only
        # We assume standard format "Street, City, State Zip" or similar comma-separated
        parts = address_str.split(',')
        if len(parts) >= 2:
            # Construct a broader query using the last two parts (usually City, State/Zip)
            city_state_query = f"{parts[-2].strip()}, {parts[-1].strip()}"
            print(f"Exact match failed. Retrying with fallback query: '{city_state_query}'")
            
            location = geolocator.geocode(city_state_query, timeout=10, addressdetails=True)
            
            if location:
                raw_addr = location.raw.get('address', {})
                
                # Fallback components (street is None)
                components = {
                    'street': None,
                    'city': raw_addr.get('city') or raw_addr.get('town') or raw_addr.get('village'),
                    'state': raw_addr.get('state'),
                    'zip': raw_addr.get('postcode')
                }

                return {
                    'lat': location.latitude,
                    'lon': location.longitude,
                    'osm_display_name': location.address,
                    'match_type': 'PARTIAL',
                    'components': components
                }

        return None

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding service error: {e}")
        return None

if __name__ == "__main__":
    # Test Block
    
    # 1. Likely Fake Address (should trigger fallback)
    fake_addr = "99999 Wizard Blvd, Springfield, IL 62704" 
    print(f"Testing Fake Address: {fake_addr}")
    result_fake = validate_address_osm(fake_addr)
    if result_fake:
        print(f"Result Components: {result_fake['components']}\n")
    else:
        print("No result found.\n")

    # 2. Real Address
    real_addr = "6801 Airport Blvd, Mobile, AL 36608"
    print(f"Testing Real Address: {real_addr}")
    result_real = validate_address_osm(real_addr)
    if result_real:
        print(f"Result Components: {result_real['components']}")
    else:
        print("No result found.")