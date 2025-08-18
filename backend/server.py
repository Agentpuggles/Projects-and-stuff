from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import aiohttp
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# LLM Configuration
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Scryfall API base URL
SCRYFALL_API_BASE = "https://api.scryfall.com"

# USD to AUD conversion rate (in production, you'd fetch this from a currency API)
USD_TO_AUD_RATE = 1.55  # Approximate rate

# Define Models
class Card(BaseModel):
    id: str
    name: str
    mana_cost: Optional[str] = None
    cmc: float = 0
    type_line: str
    oracle_text: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    colors: List[str] = []
    color_identity: List[str] = []
    image_uris: Optional[Dict[str, str]] = None
    prices: Optional[Dict[str, Optional[str]]] = None
    set_name: Optional[str] = None
    rarity: Optional[str] = None
    legalities: Optional[Dict[str, str]] = None

class DeckCard(BaseModel):
    card_id: str
    name: str
    quantity: int = 1
    mana_cost: Optional[str] = None
    cmc: float = 0
    type_line: str = ""
    colors: List[str] = []
    color_identity: List[str] = []
    price_usd: float = 0
    price_aud: float = 0
    rarity: Optional[str] = None
    image_uri: Optional[str] = None

class Commander(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    card_id: str
    name: str
    color_identity: List[str]
    image_uri: Optional[str] = None
    power_level: int = 1  # WOTC Bracket 1-5
    synergies: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Deck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    commander: Optional[DeckCard] = None
    cards: List[DeckCard] = []
    total_cards: int = 0
    power_level: int = 1  # WOTC Bracket 1-5
    total_price_usd: float = 0
    total_price_aud: float = 0
    color_identity: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DeckCreate(BaseModel):
    name: str
    commander_id: Optional[str] = None

class GameState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    players: List[str] = []  # Player IDs
    current_turn: int = 0
    phase: str = "upkeep"  # upkeep, main1, combat, main2, end
    life_totals: Dict[str, int] = {}
    commander_damage: Dict[str, Dict[str, int]] = {}  # {from_player: {to_player: damage}}
    board_state: Dict[str, List[Dict]] = {}  # {player_id: [cards_on_battlefield]}
    hands: Dict[str, List[Dict]] = {}  # {player_id: [cards_in_hand]}
    graveyards: Dict[str, List[Dict]] = {}  # {player_id: [cards_in_graveyard]}
    stack: List[Dict] = []  # Current spells/abilities on stack
    turn_count: int = 1
    game_over: bool = False
    winner: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AIDecision(BaseModel):
    player_id: str
    action_type: str  # "play_spell", "attack", "block", "pass", etc.
    target: Optional[str] = None
    reasoning: str

# Utility Functions
async def fetch_scryfall_data(endpoint: str, params: Dict = None) -> Dict:
    """Fetch data from Scryfall API with proper headers and rate limiting"""
    headers = {
        'User-Agent': 'MTGCommander/1.0',
        'Accept': 'application/json'
    }
    
    url = f"{SCRYFALL_API_BASE}/{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise HTTPException(status_code=response.status, detail="Scryfall API error")

def convert_usd_to_aud(usd_price: float) -> str:
    """Convert USD price to AUD"""
    return str(round(usd_price * USD_TO_AUD_RATE, 2))

def calculate_deck_power_level(cards: List[DeckCard], commander: Optional[DeckCard] = None) -> int:
    """Calculate WOTC bracket power level (1-5) based on deck composition"""
    power_level = 1
    
    # Base power assessment
    expensive_cards = sum(1 for card in cards if card.price_usd > 20)
    very_expensive_cards = sum(1 for card in cards if card.price_usd > 50)
    
    # Fast mana and powerful cards increase power level
    fast_mana_cards = [
        "Sol Ring", "Mana Crypt", "Mana Vault", "Chrome Mox", "Mox Diamond",
        "Grim Monolith", "Basalt Monolith", "Thran Dynamo"
    ]
    
    tutors = [
        "Vampiric Tutor", "Demonic Tutor", "Mystical Tutor", "Enlightened Tutor",
        "Worldly Tutor", "Gamble", "Imperial Seal"
    ]
    
    power_cards_count = sum(1 for card in cards if card.name in fast_mana_cards + tutors)
    
    # Calculate power level
    if expensive_cards >= 20 or very_expensive_cards >= 5:
        power_level += 2
    elif expensive_cards >= 10:
        power_level += 1
    
    if power_cards_count >= 8:
        power_level += 2
    elif power_cards_count >= 4:
        power_level += 1
    
    # Adjust based on average CMC
    if len(cards) > 0:
        avg_cmc = sum(card.cmc for card in cards) / len(cards)
        if avg_cmc < 2.5:
            power_level += 1
        elif avg_cmc > 4.0:
            power_level -= 1
    
    return min(5, max(1, power_level))

def validate_commander_deck(cards: List[DeckCard], commander: Optional[DeckCard] = None) -> Dict[str, Any]:
    """Validate Commander deck rules"""
    errors = []
    warnings = []
    
    # Check total card count (99 + 1 commander = 100)
    total_cards = sum(card.quantity for card in cards)
    if commander:
        total_cards += 1
    
    if total_cards != 100:
        errors.append(f"Commander decks must have exactly 100 cards. Current: {total_cards}")
    
    # Check for duplicates (except basic lands)
    basic_lands = ["Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"]
    card_counts = {}
    
    for card in cards:
        if card.name not in basic_lands:
            card_counts[card.name] = card_counts.get(card.name, 0) + card.quantity
            if card_counts[card.name] > 1:
                errors.append(f"Only one copy of {card.name} allowed (except basic lands)")
    
    # Check color identity
    if commander:
        commander_colors = set(commander.color_identity)
        for card in cards:
            card_colors = set(card.color_identity)
            if not card_colors.issubset(commander_colors):
                errors.append(f"{card.name} contains colors not in commander's identity")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "total_cards": total_cards
    }

async def get_ai_decision(game_state: GameState, player_id: str) -> AIDecision:
    """Get AI decision for a given game state using LLM"""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"mtg_game_{game_state.id}_{player_id}",
            system_message="""You are an expert Magic: The Gathering Commander player. 
            Analyze the current game state and make strategic decisions. 
            Consider: board state, life totals, commander damage, card advantage, mana efficiency, 
            threat assessment, politics in multiplayer, and win conditions.
            Always provide clear reasoning for your decisions."""
        ).with_model("openai", "gpt-4o")
        
        game_analysis = f"""
        Current Game State:
        - Turn: {game_state.turn_count}
        - Phase: {game_state.phase}
        - Life Totals: {game_state.life_totals}
        - Current Player: {player_id}
        - Players: {game_state.players}
        - Board State: {game_state.board_state.get(player_id, [])}
        - Hand Size: {len(game_state.hands.get(player_id, []))}
        
        What is your next action? Choose from: play_spell, attack, block, pass, activate_ability
        Provide your reasoning.
        """
        
        user_message = UserMessage(text=game_analysis)
        response = await chat.send_message(user_message)
        
        # Parse the AI response (simplified - would need more sophisticated parsing)
        action_type = "pass"  # Default action
        reasoning = response if response else "AI decision processing..."
        
        return AIDecision(
            player_id=player_id,
            action_type=action_type,
            reasoning=reasoning
        )
    
    except Exception as e:
        logging.error(f"AI decision error: {e}")
        return AIDecision(
            player_id=player_id,
            action_type="pass",
            reasoning="AI error - passing turn"
        )

# API Endpoints

@api_router.get("/")
async def root():
    return {"message": "MTG Commander API Ready", "version": "1.0"}

@api_router.get("/cards/search")
async def search_cards(q: str, limit: int = 20):
    """Search for cards using Scryfall API"""
    try:
        params = {"q": q, "limit": limit}
        data = await fetch_scryfall_data("cards/search", params)
        
        cards = []
        for card_data in data.get("data", []):
            # Convert prices to AUD
            prices = card_data.get("prices", {})
            aud_prices = {}
            for price_type, usd_price in prices.items():
                if usd_price and usd_price != "null":
                    try:
                        aud_prices[f"{price_type}_aud"] = convert_usd_to_aud(float(usd_price))
                    except (ValueError, TypeError):
                        aud_prices[f"{price_type}_aud"] = None
                else:
                    aud_prices[f"{price_type}_aud"] = None
            
            card = Card(
                id=card_data["id"],
                name=card_data["name"],
                mana_cost=card_data.get("mana_cost"),
                cmc=card_data.get("cmc", 0),
                type_line=card_data["type_line"],
                oracle_text=card_data.get("oracle_text"),
                power=card_data.get("power"),
                toughness=card_data.get("toughness"),
                colors=card_data.get("colors", []),
                color_identity=card_data.get("color_identity", []),
                image_uris=card_data.get("image_uris"),
                prices={**prices, **aud_prices},
                set_name=card_data.get("set_name"),
                rarity=card_data.get("rarity"),
                legalities=card_data.get("legalities")
            )
            cards.append(card)
        
        return {"cards": cards, "total": len(cards)}
    
    except Exception as e:
        logging.error(f"Card search error: {e}")
        raise HTTPException(status_code=500, detail="Card search failed")

@api_router.get("/cards/{card_id}")
async def get_card_details(card_id: str):
    """Get detailed card information by ID"""
    try:
        data = await fetch_scryfall_data(f"cards/{card_id}")
        
        # Convert prices to AUD
        prices = data.get("prices", {})
        aud_prices = {}
        for price_type, usd_price in prices.items():
            if usd_price and usd_price != "null":
                try:
                    aud_prices[f"{price_type}_aud"] = convert_usd_to_aud(float(usd_price))
                except (ValueError, TypeError):
                    aud_prices[f"{price_type}_aud"] = None
            else:
                aud_prices[f"{price_type}_aud"] = None
        
        card = Card(
            id=data["id"],
            name=data["name"],
            mana_cost=data.get("mana_cost"),
            cmc=data.get("cmc", 0),
            type_line=data["type_line"],
            oracle_text=data.get("oracle_text"),
            power=data.get("power"),
            toughness=data.get("toughness"),
            colors=data.get("colors", []),
            color_identity=data.get("color_identity", []),
            image_uris=data.get("image_uris"),
            prices={**prices, **aud_prices},
            set_name=data.get("set_name"),
            rarity=data.get("rarity"),
            legalities=data.get("legalities")
        )
        
        return card
    
    except Exception as e:
        logging.error(f"Card details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get card details")

@api_router.get("/commanders/recommend")
async def recommend_commanders(colors: str = "", playstyle: str = ""):
    """Get AI-powered commander recommendations"""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id="commander_recommendations",
            system_message="""You are an expert Magic: The Gathering deck builder specializing in Commander format.
            Provide strategic commander recommendations based on color preferences and playstyle.
            Consider synergies, power level, and meta considerations."""
        ).with_model("openai", "gpt-4o")
        
        query = f"Recommend 3 commanders for colors: {colors}, playstyle: {playstyle}. Include reasoning."
        user_message = UserMessage(text=query)
        response = await chat.send_message(user_message)
        
        return {"recommendations": response, "colors": colors, "playstyle": playstyle}
    
    except Exception as e:
        logging.error(f"Commander recommendation error: {e}")
        raise HTTPException(status_code=500, detail="Commander recommendation failed")

@api_router.post("/decks", response_model=Deck)
async def create_deck(deck_data: DeckCreate):
    """Create a new Commander deck"""
    try:
        # Initialize empty deck
        deck = Deck(
            name=deck_data.name,
            commander=None,
            cards=[],
            total_cards=0,
            power_level=1,
            total_price_usd=0.0,
            total_price_aud=0.0,
            color_identity=[]
        )
        
        # If commander is specified, fetch and add it
        if deck_data.commander_id:
            try:
                card_data = await fetch_scryfall_data(f"cards/{deck_data.commander_id}")
                
                # Check if it's a valid commander
                if "Legendary" not in card_data.get("type_line", "") or "Creature" not in card_data.get("type_line", ""):
                    raise HTTPException(status_code=400, detail="Commander must be a Legendary Creature")
                
                prices = card_data.get("prices", {})
                usd_price = float(prices.get("usd", 0) or 0)
                
                commander_card = DeckCard(
                    card_id=card_data["id"],
                    name=card_data["name"],
                    quantity=1,
                    mana_cost=card_data.get("mana_cost"),
                    cmc=card_data.get("cmc", 0),
                    type_line=card_data["type_line"],
                    colors=card_data.get("colors", []),
                    color_identity=card_data.get("color_identity", []),
                    price_usd=usd_price,
                    price_aud=float(convert_usd_to_aud(usd_price)),
                    rarity=card_data.get("rarity"),
                    image_uri=card_data.get("image_uris", {}).get("small")
                )
                
                deck.commander = commander_card
                deck.color_identity = commander_card.color_identity
                deck.total_cards = 1
                deck.total_price_usd = commander_card.price_usd
                deck.total_price_aud = commander_card.price_aud
                
            except Exception as e:
                logging.error(f"Commander fetch error: {e}")
                raise HTTPException(status_code=400, detail="Invalid commander ID")
        
        # Save to database
        deck_dict = deck.dict()
        await db.decks.insert_one(deck_dict)
        
        return deck
    
    except Exception as e:
        logging.error(f"Deck creation error: {e}")
        raise HTTPException(status_code=500, detail="Deck creation failed")

@api_router.get("/decks", response_model=List[Deck])
async def get_decks():
    """Get all decks"""
    try:
        decks = await db.decks.find().sort("created_at", -1).to_list(100)
        return [Deck(**deck) for deck in decks]
    except Exception as e:
        logging.error(f"Get decks error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve decks")

@api_router.get("/decks/{deck_id}", response_model=Deck)
async def get_deck(deck_id: str):
    """Get specific deck by ID"""
    try:
        deck_data = await db.decks.find_one({"id": deck_id})
        if not deck_data:
            raise HTTPException(status_code=404, detail="Deck not found")
        return Deck(**deck_data)
    except Exception as e:
        logging.error(f"Get deck error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deck")

@api_router.put("/decks/{deck_id}/add-card")
async def add_card_to_deck(deck_id: str, card_id: str, quantity: int = 1):
    """Add a card to a deck"""
    try:
        # Get deck
        deck_data = await db.decks.find_one({"id": deck_id})
        if not deck_data:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        deck = Deck(**deck_data)
        
        # Get card details from Scryfall
        card_data = await fetch_scryfall_data(f"cards/{card_id}")
        
        prices = card_data.get("prices", {})
        usd_price = float(prices.get("usd", 0) or 0)
        
        new_card = DeckCard(
            card_id=card_data["id"],
            name=card_data["name"],
            quantity=quantity,
            mana_cost=card_data.get("mana_cost"),
            cmc=card_data.get("cmc", 0),
            type_line=card_data["type_line"],
            colors=card_data.get("colors", []),
            color_identity=card_data.get("color_identity", []),
            price_usd=usd_price,
            price_aud=float(convert_usd_to_aud(usd_price)),
            rarity=card_data.get("rarity"),
            image_uri=card_data.get("image_uris", {}).get("small")
        )
        
        # Check if card already exists in deck
        existing_card_idx = None
        for idx, card in enumerate(deck.cards):
            if card.card_id == card_id:
                existing_card_idx = idx
                break
        
        if existing_card_idx is not None:
            # Update quantity
            deck.cards[existing_card_idx].quantity += quantity
        else:
            # Add new card
            deck.cards.append(new_card)
        
        # Recalculate deck stats
        deck.total_cards = sum(card.quantity for card in deck.cards) + (1 if deck.commander else 0)
        deck.total_price_usd = sum(card.price_usd * card.quantity for card in deck.cards) + (deck.commander.price_usd if deck.commander else 0)
        deck.total_price_aud = sum(card.price_aud * card.quantity for card in deck.cards) + (deck.commander.price_aud if deck.commander else 0)
        deck.power_level = calculate_deck_power_level(deck.cards, deck.commander)
        deck.updated_at = datetime.utcnow()
        
        # Validate deck
        validation = validate_commander_deck(deck.cards, deck.commander)
        
        # Update in database
        await db.decks.update_one(
            {"id": deck_id},
            {"$set": deck.dict()}
        )
        
        return {
            "deck": deck,
            "validation": validation
        }
    
    except Exception as e:
        logging.error(f"Add card error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add card to deck")

@api_router.delete("/decks/{deck_id}/remove-card/{card_id}")
async def remove_card_from_deck(deck_id: str, card_id: str, quantity: int = 1):
    """Remove a card from a deck"""
    try:
        # Get deck
        deck_data = await db.decks.find_one({"id": deck_id})
        if not deck_data:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        deck = Deck(**deck_data)
        
        # Find and remove card
        for idx, card in enumerate(deck.cards):
            if card.card_id == card_id:
                if card.quantity <= quantity:
                    # Remove card entirely
                    deck.cards.pop(idx)
                else:
                    # Reduce quantity
                    deck.cards[idx].quantity -= quantity
                break
        else:
            raise HTTPException(status_code=404, detail="Card not found in deck")
        
        # Recalculate deck stats
        deck.total_cards = sum(card.quantity for card in deck.cards) + (1 if deck.commander else 0)
        deck.total_price_usd = sum(card.price_usd * card.quantity for card in deck.cards) + (deck.commander.price_usd if deck.commander else 0)
        deck.total_price_aud = sum(card.price_aud * card.quantity for card in deck.cards) + (deck.commander.price_aud if deck.commander else 0)
        deck.power_level = calculate_deck_power_level(deck.cards, deck.commander)
        deck.updated_at = datetime.utcnow()
        
        # Validate deck
        validation = validate_commander_deck(deck.cards, deck.commander)
        
        # Update in database
        await db.decks.update_one(
            {"id": deck_id},
            {"$set": deck.dict()}
        )
        
        return {
            "deck": deck,
            "validation": validation
        }
    
    except Exception as e:
        logging.error(f"Remove card error: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove card from deck")

@api_router.delete("/decks/{deck_id}")
async def delete_deck(deck_id: str):
    """Delete a deck"""
    try:
        result = await db.decks.delete_one({"id": deck_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Deck not found")
        return {"message": "Deck deleted successfully"}
    except Exception as e:
        logging.error(f"Delete deck error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete deck")

@api_router.post("/games", response_model=GameState)
async def create_game(player_decks: List[str]):
    """Create a new 4-player Commander game"""
    try:
        if len(player_decks) != 4:
            raise HTTPException(status_code=400, detail="Commander requires exactly 4 players")
        
        # Initialize game state
        game_state = GameState(
            players=player_decks,
            life_totals={pid: 40 for pid in player_decks},  # Commander starts at 40 life
            commander_damage={pid: {other: 0 for other in player_decks if other != pid} for pid in player_decks},
            board_state={pid: [] for pid in player_decks},
            hands={pid: [] for pid in player_decks},
            graveyards={pid: [] for pid in player_decks}
        )
        
        # Save to database
        game_dict = game_state.dict()
        await db.games.insert_one(game_dict)
        
        return game_state
    
    except Exception as e:
        logging.error(f"Game creation error: {e}")
        raise HTTPException(status_code=500, detail="Game creation failed")

@api_router.get("/games/{game_id}/ai-decision")
async def get_game_ai_decision(game_id: str, player_id: str):
    """Get AI decision for current game state"""
    try:
        # Fetch game state
        game_data = await db.games.find_one({"id": game_id})
        if not game_data:
            raise HTTPException(status_code=404, detail="Game not found")
        
        game_state = GameState(**game_data)
        ai_decision = await get_ai_decision(game_state, player_id)
        
        return ai_decision
    
    except Exception as e:
        logging.error(f"AI decision error: {e}")
        raise HTTPException(status_code=500, detail="AI decision failed")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()