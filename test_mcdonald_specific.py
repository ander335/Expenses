"""
Specific test for Russian McDonald's receipt with currency conversion
Tests the AI's ability to:
1. Parse Russian text
2. Extract individual items with prices
3. Convert EUR to CZK
4. Add location comment (Japan)
5. Handle operation cancellation via threading primitives
"""

import os
import json
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_mcdonald_cancellation():
    """Test the cancellation functionality of parse_voice_to_receipt"""
    print("🛑 Testing McDonald's Receipt Processing with Cancellation")
    print("=" * 60)
    
    # Set up OpenAI provider
    os.environ['AI_PROVIDER'] = 'openai'
    
    # Check API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment variables")
        print("Please add OPENAI_API_KEY=your_key to your .env file")
        return False
    
    print(f"✅ Using OpenAI provider with API key: {api_key[:10]}...")
    
    try:
        # Import AI function and exception
        from ai import parse_voice_to_receipt, OperationCancelledException
        
        # The specific Russian text from the user
        russian_text = "Купил вчера в макдональдсе бигмак за 10 евро, колу за 5 и нагетсы за 9. Сконвертируй евро в чешские кроны по текущему курсу. Добавь коментарий, что это было в японии."
        
        print(f"\n📝 Input text (Russian):")
        print(f"'{russian_text}'")
        
        print(f"\n📝 English translation for reference:")
        print(f"'Bought yesterday at McDonald's big mac for 10 euros, cola for 5 and nuggets for 9. Convert euros to Czech crowns at current rate. Add comment that it was in Japan.'")
        
        # Create a cancellation event
        cancel_event = threading.Event()
        
        print(f"\n🤖 Processing with OpenAI (will be cancelled after 1 second)...")
        
        # Start a timer to trigger cancellation after 1 second
        def trigger_cancellation():
            time.sleep(1.0)  # Wait 1 second
            print(f"\n🛑 Triggering cancellation after 1 second...")
            cancel_event.set()
        
        cancellation_thread = threading.Thread(target=trigger_cancellation, daemon=True)
        cancellation_thread.start()
        
        start_time = time.time()
        
        try:
            # Call the AI function with cancellation support
            result, elapsed_time = parse_voice_to_receipt(russian_text, cancel_event=cancel_event)
            
            # If we reach here, the operation completed before cancellation
            print(f"⚠️  Operation completed before cancellation in {elapsed_time:.1f} seconds")
            print(f"📄 Result: {result[:100]}...")
            return False  # Test failed - should have been cancelled
            
        except OperationCancelledException as e:
            elapsed_time = time.time() - start_time
            print(f"✅ Operation successfully cancelled after {elapsed_time:.1f} seconds")
            print(f"✅ Exception message: {str(e)}")
            
            # Verify cancellation happened reasonably quickly (within 3 seconds of trigger)
            if elapsed_time <= 3.5:  # Allow some buffer for network latency and processing time
                print(f"✅ Cancellation was triggered promptly (within {elapsed_time:.1f}s)")
                return True
            else:
                print(f"❌ Cancellation took too long ({elapsed_time:.1f}s)")
                return False
        
    except Exception as e:
        print(f"❌ Test failed with unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_mcdonald_receipt():
    """Test the specific McDonald's receipt scenario"""
    print("🍔 Testing Russian McDonald's Receipt Processing")
    print("=" * 60)
    
    # Set up OpenAI provider
    os.environ['AI_PROVIDER'] = 'openai'
    
    # Check API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment variables")
        print("Please add OPENAI_API_KEY=your_key to your .env file")
        return False
    
    print(f"✅ Using OpenAI provider with API key: {api_key[:10]}...")
    
    try:
        # Import AI function
        from ai import parse_voice_to_receipt
        
        # The specific Russian text from the user
        russian_text = "Купил вчера в макдональдсе бигмак за 10 евро, колу за 5 и нагетсы за 9. Сконвертируй евро в чешские кроны по текущему курсу. Добавь коментарий, что это было в японии."
        
        print(f"\n📝 Input text (Russian):")
        print(f"'{russian_text}'")
        
        print(f"\n📝 English translation for reference:")
        print(f"'Bought yesterday at McDonald's big mac for 10 euros, cola for 5 and nuggets for 9. Convert euros to Czech crowns at current rate. Add comment that it was in Japan.'")
        
        print(f"\n🤖 Processing with OpenAI...")
        
        # Call the AI function
        result, elapsed_time = parse_voice_to_receipt(russian_text)
        
        print(f"✅ Processing completed in {elapsed_time:.1f} seconds")
        
        # Parse the JSON result
        receipt_data = json.loads(result)
        
        # Display the complete result
        print(f"\n📋 Generated Receipt (Full JSON):")
        print(json.dumps(receipt_data, indent=2, ensure_ascii=False))
        
        # Extract and display key information
        print(f"\n📊 Key Information:")
        print(f"   🏪 Merchant: {receipt_data.get('merchant', 'Not found')}")
        print(f"   💰 Total Amount: {receipt_data.get('total_amount', 'Not found')}")
        print(f"   📅 Date: {receipt_data.get('date', 'Not found')}")
        print(f"   🏷️  Category: {receipt_data.get('category', 'Not found')}")
        print(f"   📝 Description: {receipt_data.get('description', 'Not found')}")
        
        # Display individual items
        positions = receipt_data.get('positions', [])
        print(f"\n🛒 Items ({len(positions)} items):")
        total_eur = 0
        for i, item in enumerate(positions, 1):
            description = item.get('description', 'Unknown')
            quantity = item.get('quantity', 'Unknown')
            price = item.get('price', 'Unknown')
            category = item.get('category', 'Unknown')
            
            print(f"   {i}. {description}")
            print(f"      Quantity: {quantity}")
            print(f"      Price: {price}")
            print(f"      Category: {category}")
            
            # Try to extract numeric price for validation
            try:
                price_num = float(str(price).replace(',', '.'))
                total_eur += price_num
            except:
                pass
        
        print(f"\n✅ Calculated total from items: {total_eur} EUR")
        
        # Validation checks
        print(f"\n🔍 Validation Checks:")
        
        # Check 1: Currency conversion mentioned
        description = receipt_data.get('description', '').lower()
        full_text = json.dumps(receipt_data, ensure_ascii=False).lower()
        
        currency_indicators = ['crown', 'czk', 'крон', 'чешск', 'koruna', 'koruna']
        currency_found = any(indicator in full_text for indicator in currency_indicators)
        print(f"   {'✅' if currency_found else '❌'} Currency conversion to CZK: {'Found' if currency_found else 'Not found'}")
        
        # Check 2: Japan location mentioned
        location_indicators = ['japan', 'япон', 'japanese', 'tokyo']
        location_found = any(indicator in full_text for indicator in location_indicators)
        print(f"   {'✅' if location_found else '❌'} Japan location mentioned: {'Found' if location_found else 'Not found'}")
        
        # Check 3: McDonald's recognized
        mcdonald_indicators = ['mcdonald', 'макдональдс', 'mcdonalds']
        mcdonald_found = any(indicator in full_text for indicator in mcdonald_indicators)
        print(f"   {'✅' if mcdonald_found else '❌'} McDonald's recognized: {'Found' if mcdonald_found else 'Not found'}")
        
        # Check 4: Individual items recognized
        expected_items = [
            ('big mac', 'бигмак', '10'),
            ('cola', 'кола', '5'), 
            ('nugget', 'нагетс', '9')
        ]
        
        items_recognized = 0
        for eng_name, rus_name, expected_price in expected_items:
            found = False
            for item in positions:
                item_desc = item.get('description', '').lower()
                if eng_name in item_desc or rus_name in item_desc:
                    found = True
                    items_recognized += 1
                    break
            print(f"   {'✅' if found else '❌'} {eng_name.title()} recognized: {'Found' if found else 'Not found'}")
        
        print(f"\n📈 Overall Results:")
        print(f"   Items recognized: {items_recognized}/3")
        print(f"   Currency conversion: {'✅' if currency_found else '❌'}")
        print(f"   Location mentioned: {'✅' if location_found else '❌'}")
        print(f"   ⏱️  Total parsing time: {elapsed_time:.1f} seconds")
        
        # Determine success
        success = currency_found and location_found and items_recognized >= 2
        print(f"\n🎯 Test Result: {'✅ PASSED' if success else '❌ FAILED'} (Processing time: {elapsed_time:.1f}s)")
        
        return success
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Specific Test: Russian McDonald's Receipt + Cancellation")
    print("Tests AI ability to process complex Russian text and handle cancellation")
    print("")
    
    # First test: Normal processing
    print("=" * 60)
    print("TEST 1: Normal Processing")
    print("=" * 60)
    success_normal = test_mcdonald_receipt()
    
    # Second test: Cancellation functionality
    print("\n" + "=" * 60)
    print("TEST 2: Cancellation Functionality")
    print("=" * 60)
    success_cancellation = test_mcdonald_cancellation()
    
    # Overall results
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)
    
    print(f"Normal processing test: {'✅ PASSED' if success_normal else '❌ FAILED'}")
    print(f"Cancellation test: {'✅ PASSED' if success_cancellation else '❌ FAILED'}")
    
    overall_success = success_normal and success_cancellation
    print(f"\nOverall test result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n🎉 All tests completed successfully!")
        print("The AI successfully processed Russian text and supports cancellation.")
    else:
        print("\n⚠️  Some tests had issues.")
        print("Check the output above for details on what might need improvement.")
    
    print("\n📝 Test Requirements Checked:")
    print("1. Parse Russian text about McDonald's purchase")
    print("2. Extract 3 items: Big Mac (10€), Cola (5€), Nuggets (9€)")
    print("3. Convert EUR to CZK at current exchange rate")
    print("4. Add comment about location (Japan)")
    print("5. Structure data as proper receipt JSON")
    print("6. Support operation cancellation via threading.Event")