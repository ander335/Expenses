from gemini import parse_receipt_image
import json
from datetime import datetime

if __name__ == "__main__":
    image_path = "receipt_AgACAgIAAxkBAAM8aOEvI9CMa1Q7lZxD3Ozu_2SsM64AAoT5MRsFOQhLdE3VvC1monABAAMCAAN5AAM2BA.jpg"
    result = parse_receipt_image(image_path)
    
    # Print to console
    print("Gemini output:")
    print(result)  # Already a formatted string from Gemini
    
    # Save to file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"receipt_analysis_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)  # Write the string directly
    
    print(f"\nOutput saved to: {output_file}")
