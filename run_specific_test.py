"""
Quick test runner for the specific McDonald's receipt test
Run this to test the AI with the Russian McDonald's text
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Run the specific McDonald's test"""
    print("🚀 Running Specific AI Test")
    print("Testing: Russian McDonald's Receipt with Currency Conversion")
    print("-" * 60)
    
    # Ensure OpenAI provider is set
    os.environ['AI_PROVIDER'] = 'openai'
    
    # Check environment
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment")
        print("Please add your OpenAI API key to the .env file:")
        print("OPENAI_API_KEY=sk-your-actual-api-key-here")
        return
    
    try:
        # Import and run the test
        from test_mcdonald_specific import test_mcdonald_cancellation

        
        print("🤖 Starting AI test...")
        result = test_mcdonald_cancellation()
        
        if result:
            print("\n✅ SUCCESS: AI test passed!")
            print("The AI successfully:")
            print("  - Parsed Russian text")
            print("  - Recognized McDonald's and all 3 items")
            print("  - Converted EUR to CZK (25.3 rate)")
            print("  - Added Japan location comment")
            print("  - Created proper JSON structure")
            print("  - Processing time displayed in detailed results above")
        else:
            print("\n❌ FAILED: AI test had issues")
            
    except Exception as e:
        print(f"❌ Error running test: {str(e)}")

if __name__ == "__main__":
    main()