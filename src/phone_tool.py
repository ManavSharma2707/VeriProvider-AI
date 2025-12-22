import phonenumbers
from phonenumbers import geocoder, timezone

def validate_phone(phone_str: str, region: str = "US") -> dict:
    """
    Parses and validates a phone number using Google's libphonenumber.
    Returns structured data including formatting and location metadata.
    
    Args:
        phone_str (str): The raw phone string (e.g., "555-123-4567").
        region (str): Default region code (default "US").
        
    Returns:
        dict: Validation results or error details.
    """
    if not phone_str:
        return None
    
    try:
        # Parse the input string
        parsed_num = phonenumbers.parse(phone_str, region)
        
        # Check if it's a possible number and a valid number
        is_valid = phonenumbers.is_valid_number(parsed_num)
        
        if not is_valid:
            return {
                'valid': False, 
                'original': phone_str,
                'error': 'Invalid structure or non-existent number'
            }

        # Format: Standard US format (555) 555-5555
        formatted_national = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL)
        # Format: E.164 +15555555555 (Best for databases/APIs)
        formatted_e164 = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
        
        # Extract Metadata
        # Get location based on area code (e.g., "New York, NY")
        location_desc = geocoder.description_for_number(parsed_num, "en")
        
        # Get Timezone
        time_zones = timezone.time_zones_for_number(parsed_num)

        return {
            'valid': True,
            'original': phone_str,
            'formatted_display': formatted_national,
            'e164': formatted_e164,
            'area_location': location_desc,
            'time_zones': list(time_zones)
        }
        
    except phonenumbers.NumberParseException as e:
        return {
            'valid': False, 
            'original': phone_str,
            'error': f"Parse Error: {str(e)}"
        }
    except Exception as e:
        return {
            'valid': False, 
            'original': phone_str,
            'error': f"Unexpected Error: {str(e)}"
        }

if __name__ == "__main__":
    # Test Block
    print("--- Testing Phone Tool ---")
    
    # 1. Valid US Number
    print(validate_phone("2024561111"))
    
    # 2. Messy Format
    print(validate_phone("(212) 555.1234"))
    
    # 3. Invalid
    print(validate_phone("12345"))