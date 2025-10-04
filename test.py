from gemini import parse_receipt_image
import json
from datetime import datetime
from parse import parse_receipt_from_file
from db import add_receipt
from db import get_or_create_user, UserData

# Test code for image processing and saving to JSON
# if __name__ == "__main__":
#     image_path = "receipt_AgACAgIAAxkBAAM8aOEvI9CMa1Q7lZxD3Ozu_2SsM64AAoT5MRsFOQhLdE3VvC1monABAAMCAAN5AAM2BA.jpg"
#     result = parse_receipt_image(image_path)
    
#     # Print to console
#     print("Gemini output:")
#     print(result)  # Already a formatted string from Gemini
    
#     # Save to file with timestamp
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     output_file = f"receipt_analysis_{timestamp}.json"
    
#     with open(output_file, "w", encoding="utf-8") as f:
#         f.write(result)  # Write the string directly
    
#     print(f"\nOutput saved to: {output_file}")

# Test code for reading JSON and saving to database
if __name__ == "__main__":
    # Read and parse the receipt data from JSON file
    json_file = "receipt_analysis_20251004_171452.json"  # Use your actual JSON file name
    user_id = 2  # Example user ID
    
    try:
        # First ensure we have a user
        test_user = get_or_create_user(UserData(user_id=user_id, name="Test User"))
        print(f"Using user: {test_user.name} (ID: {test_user.user_id})")
        
        # Parse the receipt data from the JSON file
        receipt_data = parse_receipt_from_file(json_file, user_id)
        
        # Save the receipt data to the database
        receipt_id = add_receipt(receipt_data)
        
        print(f"Successfully saved receipt to database with ID: {receipt_id}")
        
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
