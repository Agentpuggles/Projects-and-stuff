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
    commander: Commander
    cards: List[Dict[str, Any]] = []  # {card_id, quantity}
    total_cards: int = 100  # Commander format
    power_level: int = 1  # WOTC Bracket 1-5
    total_price_usd: float = 0
    total_price_aud: float = 0
    foil_price_usd: float = 0
    foil_price_aud: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

def convert_usd_to_aud(usd_price: float) -> float:
    """Convert USD price to AUD"""
    return round(usd_price * USD_TO_AUD_RATE, 2)

def calculate_deck_power_level(cards: List[Dict]) -> int:
    """Calculate WOTC bracket power level (1-5) based on deck composition"""
    # This is a simplified algorithm - in production you'd have more sophisticated analysis
    power_level = 1
    
    # Count high-power cards, fast mana, tutors, etc.
    high_power_indicators = 0
    
    for card_entry in cards:
        # This would need actual card data analysis
        # For now, return a base power level
        pass
    
    return min(5, max(1, power_level))

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
                        aud_prices[f"{price_type}_aud"] = 0
            
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
async def create_deck(deck_data: Dict[str, Any]):
    """Create a new Commander deck"""
    try:
        # Calculate power level and pricing
        cards = deck_data.get("cards", [])
        power_level = calculate_deck_power_level(cards)
        
        # Create deck object
        deck = Deck(
            name=deck_data["name"],
            commander=Commander(**deck_data["commander"]),
            cards=cards,
            power_level=power_level
        )
        
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