import requests
import sys
import json
from datetime import datetime

class MTGCommanderAPITester:
    def __init__(self, base_url="https://mtgcommander.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}...")
                self.failed_tests.append(f"{name}: Expected {expected_status}, got {response.status_code}")

            return success, response.json() if response.status_code < 400 else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (30s)")
            self.failed_tests.append(f"{name}: Request timeout")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append(f"{name}: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "api/",
            200
        )

    def test_card_search_lightning_bolt(self):
        """Test card search for Lightning Bolt"""
        return self.run_test(
            "Card Search - Lightning Bolt",
            "GET",
            "api/cards/search",
            200,
            params={"q": "lightning bolt", "limit": 5}
        )

    def test_card_search_sol_ring(self):
        """Test card search for Sol Ring"""
        return self.run_test(
            "Card Search - Sol Ring",
            "GET",
            "api/cards/search",
            200,
            params={"q": "sol ring", "limit": 5}
        )

    def test_card_search_rhystic_study(self):
        """Test card search for Rhystic Study"""
        return self.run_test(
            "Card Search - Rhystic Study",
            "GET",
            "api/cards/search",
            200,
            params={"q": "rhystic study", "limit": 5}
        )

    def test_commander_recommendations_aggressive(self):
        """Test AI commander recommendations for aggressive playstyle"""
        return self.run_test(
            "Commander Recommendations - Aggressive",
            "GET",
            "api/commanders/recommend",
            200,
            params={"playstyle": "aggressive"}
        )

    def test_commander_recommendations_control(self):
        """Test AI commander recommendations for control playstyle"""
        return self.run_test(
            "Commander Recommendations - Control",
            "GET",
            "api/commanders/recommend",
            200,
            params={"playstyle": "control"}
        )

    def test_commander_recommendations_combo(self):
        """Test AI commander recommendations for combo playstyle"""
        return self.run_test(
            "Commander Recommendations - Combo",
            "GET",
            "api/commanders/recommend",
            200,
            params={"playstyle": "combo"}
        )

    def test_commander_recommendations_tribal(self):
        """Test AI commander recommendations for tribal playstyle"""
        return self.run_test(
            "Commander Recommendations - Tribal",
            "GET",
            "api/commanders/recommend",
            200,
            params={"playstyle": "tribal"}
        )

    def test_get_decks(self):
        """Test getting all decks"""
        return self.run_test(
            "Get All Decks",
            "GET",
            "api/decks",
            200
        )

    def test_create_game(self):
        """Test creating a 4-player Commander game"""
        player_data = ['player1', 'ai_player1', 'ai_player2', 'ai_player3']
        success, response = self.run_test(
            "Create 4-Player Game",
            "POST",
            "api/games",
            200,
            data=player_data
        )
        return success, response

    def test_ai_decision(self, game_id):
        """Test getting AI decision for a game"""
        return self.run_test(
            "Get AI Decision",
            "GET",
            f"api/games/{game_id}/ai-decision",
            200,
            params={"player_id": "ai_player1"}
        )

def main():
    print("🎯 Starting MTG Commander API Testing...")
    print("=" * 60)
    
    # Setup
    tester = MTGCommanderAPITester()
    
    # Test basic connectivity
    print("\n📡 Testing Basic Connectivity...")
    tester.test_root_endpoint()
    
    # Test card search functionality
    print("\n🔍 Testing Card Search Functionality...")
    tester.test_card_search_lightning_bolt()
    tester.test_card_search_sol_ring()
    tester.test_card_search_rhystic_study()
    
    # Test AI commander recommendations
    print("\n👑 Testing AI Commander Recommendations...")
    tester.test_commander_recommendations_aggressive()
    tester.test_commander_recommendations_control()
    tester.test_commander_recommendations_combo()
    tester.test_commander_recommendations_tribal()
    
    # Test deck management
    print("\n⚔️ Testing Deck Management...")
    tester.test_get_decks()
    
    # Test game creation and AI decisions
    print("\n🎮 Testing Game Creation...")
    game_success, game_response = tester.test_create_game()
    
    if game_success and game_response.get('id'):
        print("\n🤖 Testing AI Decision Making...")
        tester.test_ai_decision(game_response['id'])
    else:
        print("⚠️ Skipping AI decision test - game creation failed")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.failed_tests:
        print(f"\n❌ Failed Tests:")
        for failure in tester.failed_tests:
            print(f"   • {failure}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())