import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Sword, Users, TrendingUp, Sparkles, Crown, DollarSign, Zap } from 'lucide-react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './components/ui/dialog';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [decks, setDecks] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [gameInProgress, setGameInProgress] = useState(false);
  const [activeTab, setActiveTab] = useState('search');
  const [commanderRecommendations, setCommanderRecommendations] = useState('');

  useEffect(() => {
    fetchDecks();
  }, []);

  const fetchDecks = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/decks`);
      setDecks(response.data);
    } catch (error) {
      console.error('Error fetching decks:', error);
    }
  };

  const searchCards = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/cards/search`, {
        params: { q: searchQuery, limit: 20 }
      });
      setSearchResults(response.data.cards || []);
    } catch (error) {
      console.error('Error searching cards:', error);
      setSearchResults([]);
    }
    setLoading(false);
  };

  const getCommanderRecommendations = async (colors = '', playstyle = 'aggressive') => {
    setLoading(true);
    try {
      const response = await axios.get(`${BACKEND_URL}/api/commanders/recommend`, {
        params: { colors, playstyle }
      });
      setCommanderRecommendations(response.data.recommendations);
    } catch (error) {
      console.error('Error getting recommendations:', error);
      setCommanderRecommendations('Error getting recommendations. Please try again.');
    }
    setLoading(false);
  };

  const createTestGame = async () => {
    try {
      setGameInProgress(true);
      const response = await axios.post(`${BACKEND_URL}/api/games`, [
        'player1', 'ai_player1', 'ai_player2', 'ai_player3'
      ]);
      console.log('Game created:', response.data);
      
      // Simulate getting AI decision
      const aiDecision = await axios.get(`${BACKEND_URL}/api/games/${response.data.id}/ai-decision`, {
        params: { player_id: 'ai_player1' }
      });
      console.log('AI Decision:', aiDecision.data);
      
      setTimeout(() => setGameInProgress(false), 3000);
    } catch (error) {
      console.error('Error creating game:', error);
      setGameInProgress(false);
    }
  };

  const formatManaSymbols = (manaCost) => {
    if (!manaCost) return '';
    return manaCost.replace(/[{}]/g, '');
  };

  const getPriceDisplay = (prices) => {
    if (!prices) return 'N/A';
    
    const usd = prices.usd ? parseFloat(prices.usd) : 0;
    const aud = prices.usd_aud ? parseFloat(prices.usd_aud) : 0;
    const foilUsd = prices.usd_foil ? parseFloat(prices.usd_foil) : 0;
    const foilAud = prices.usd_foil_aud ? parseFloat(prices.usd_foil_aud) : 0;
    
    return (
      <div className="space-y-1">
        {usd > 0 && (
          <div className="flex justify-between text-sm">
            <span>Regular:</span>
            <span>${usd.toFixed(2)} USD / ${aud.toFixed(2)} AUD</span>
          </div>
        )}
        {foilUsd > 0 && (
          <div className="flex justify-between text-sm">
            <span>Foil:</span>
            <span>${foilUsd.toFixed(2)} USD / ${foilAud.toFixed(2)} AUD</span>
          </div>
        )}
      </div>
    );
  };

  const getPowerLevelBadge = (level) => {
    const colors = {
      1: 'bg-green-100 text-green-800',
      2: 'bg-blue-100 text-blue-800', 
      3: 'bg-yellow-100 text-yellow-800',
      4: 'bg-orange-100 text-orange-800',
      5: 'bg-red-100 text-red-800'
    };
    
    return (
      <Badge className={`${colors[level] || colors[1]} font-semibold`}>
        Bracket {level}
      </Badge>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-white/10 backdrop-blur-sm bg-black/20">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-400 to-pink-400 rounded-lg flex items-center justify-center">
                <Crown className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">MTG Commander Hub</h1>
                <p className="text-purple-200 text-sm">Master the Art of Multiplayer Magic</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant="outline" className="text-purple-200 border-purple-300">
                4-Player Engine
              </Badge>
              <Badge variant="outline" className="text-green-200 border-green-300">
                AI Powered
              </Badge>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-8">
          <TabsList className="grid w-full grid-cols-4 bg-black/30 border border-white/10">
            <TabsTrigger value="search" className="data-[state=active]:bg-purple-600">
              <Search className="w-4 h-4 mr-2" />
              Card Search
            </TabsTrigger>
            <TabsTrigger value="commanders" className="data-[state=active]:bg-purple-600">
              <Crown className="w-4 h-4 mr-2" />
              Commanders
            </TabsTrigger>
            <TabsTrigger value="decks" className="data-[state=active]:bg-purple-600">
              <Sword className="w-4 h-4 mr-2" />
              Deck Builder
            </TabsTrigger>
            <TabsTrigger value="play" className="data-[state=active]:bg-purple-600">
              <Users className="w-4 h-4 mr-2" />
              Play Test
            </TabsTrigger>
          </TabsList>

          {/* Card Search Tab */}
          <TabsContent value="search" className="space-y-6">
            <Card className="bg-black/20 backdrop-blur border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Search className="w-5 h-5 mr-2 text-purple-400" />
                  Card Search & Analysis
                </CardTitle>
                <CardDescription className="text-purple-200">
                  Search the entire Magic: The Gathering database with pricing in AUD
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex space-x-2">
                  <Input
                    placeholder="Search cards (e.g., 'Lightning Bolt', 'legendary creature', 'cmc=3')"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && searchCards()}
                    className="bg-white/5 border-white/20 text-white placeholder-white/50"
                  />
                  <Button 
                    onClick={searchCards} 
                    disabled={loading}
                    className="bg-purple-600 hover:bg-purple-700"
                    type="button"
                  >
                    {loading ? <Sparkles className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    Search
                  </Button>
                </div>

                {searchResults.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
                    {searchResults.map((card) => (
                      <Dialog key={card.id}>
                        <DialogTrigger asChild>
                          <Card className="cursor-pointer hover:bg-white/5 bg-black/10 border-white/10 transition-all transform hover:scale-105">
                            <CardContent className="p-4">
                              <div className="flex items-start space-x-3">
                                {card.image_uris?.small && (
                                  <img 
                                    src={card.image_uris.small} 
                                    alt={card.name}
                                    className="w-16 h-22 rounded-lg object-cover border border-white/20"
                                  />
                                )}
                                <div className="flex-1 min-w-0">
                                  <h3 className="font-semibold text-white truncate">{card.name}</h3>
                                  <p className="text-sm text-purple-300 mb-1">{formatManaSymbols(card.mana_cost)}</p>
                                  <p className="text-xs text-gray-300 mb-2 line-clamp-2">{card.type_line}</p>
                                  <div className="flex items-center justify-between">
                                    <Badge variant="outline" className="text-xs">
                                      {card.rarity}
                                    </Badge>
                                    {card.prices?.usd && (
                                      <div className="text-xs text-green-400">
                                        ${parseFloat(card.prices.usd).toFixed(2)} USD
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl bg-black/90 border-white/20">
                          <DialogHeader>
                            <DialogTitle className="text-white">{card.name}</DialogTitle>
                          </DialogHeader>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {card.image_uris?.normal && (
                              <img 
                                src={card.image_uris.normal} 
                                alt={card.name}
                                className="w-full rounded-lg border border-white/20"
                              />
                            )}
                            <div className="space-y-4">
                              <div>
                                <h4 className="font-semibold text-white mb-2">Card Details</h4>
                                <div className="space-y-2 text-sm text-gray-300">
                                  <div><strong>Mana Cost:</strong> {formatManaSymbols(card.mana_cost) || 'N/A'}</div>
                                  <div><strong>Type:</strong> {card.type_line}</div>
                                  <div><strong>Set:</strong> {card.set_name}</div>
                                  <div><strong>Rarity:</strong> {card.rarity}</div>
                                  {card.power && <div><strong>P/T:</strong> {card.power}/{card.toughness}</div>}
                                </div>
                              </div>
                              
                              {card.oracle_text && (
                                <div>
                                  <h4 className="font-semibold text-white mb-2">Oracle Text</h4>
                                  <p className="text-sm text-gray-300 leading-relaxed">{card.oracle_text}</p>
                                </div>
                              )}
                              
                              <div>
                                <h4 className="font-semibold text-white mb-2 flex items-center">
                                  <DollarSign className="w-4 h-4 mr-1" />
                                  Pricing
                                </h4>
                                <div className="bg-white/5 rounded-lg p-3">
                                  {getPriceDisplay(card.prices)}
                                </div>
                              </div>
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Commanders Tab */}
          <TabsContent value="commanders" className="space-y-6">
            <Card className="bg-black/20 backdrop-blur border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Crown className="w-5 h-5 mr-2 text-yellow-400" />
                  AI Commander Recommendations
                </CardTitle>
                <CardDescription className="text-purple-200">
                  Get personalized commander suggestions based on your playstyle
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <Button 
                    variant="outline" 
                    onClick={() => getCommanderRecommendations('', 'aggressive')}
                    className="border-red-500/50 text-red-300 hover:bg-red-500/10"
                  >
                    Aggressive
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => getCommanderRecommendations('', 'control')}
                    className="border-blue-500/50 text-blue-300 hover:bg-blue-500/10"
                  >
                    Control
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => getCommanderRecommendations('', 'combo')}
                    className="border-purple-500/50 text-purple-300 hover:bg-purple-500/10"
                  >
                    Combo
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => getCommanderRecommendations('', 'tribal')}
                    className="border-green-500/50 text-green-300 hover:bg-green-500/10"
                  >
                    Tribal
                  </Button>
                </div>

                {commanderRecommendations && (
                  <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-white mb-3 flex items-center">
                        <Sparkles className="w-4 h-4 mr-2 text-yellow-400" />
                        AI Recommendations
                      </h4>
                      <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                        {loading ? (
                          <div className="flex items-center">
                            <Sparkles className="w-4 h-4 animate-spin mr-2" />
                            Analyzing commanders...
                          </div>
                        ) : (
                          commanderRecommendations
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Decks Tab */}
          <TabsContent value="decks" className="space-y-6">
            <Card className="bg-black/20 backdrop-blur border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Sword className="w-5 h-5 mr-2 text-orange-400" />
                  Deck Manager
                </CardTitle>
                <CardDescription className="text-purple-200">
                  Build and manage your Commander decks with power level analysis
                </CardDescription>
              </CardHeader>
              <CardContent>
                {decks.length === 0 ? (
                  <div className="text-center py-8">
                    <Sword className="w-12 h-12 text-gray-500 mx-auto mb-4" />
                    <p className="text-gray-400 mb-4">No decks created yet</p>
                    <Button className="bg-purple-600 hover:bg-purple-700">
                      Create Your First Deck
                    </Button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {decks.map((deck) => (
                      <Card key={deck.id} className="bg-white/5 border-white/10 hover:bg-white/10 transition-colors">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-3">
                            <h3 className="font-semibold text-white">{deck.name}</h3>
                            {getPowerLevelBadge(deck.power_level)}
                          </div>
                          <p className="text-sm text-purple-300 mb-2">
                            Commander: {deck.commander?.name || 'Unknown'}
                          </p>
                          <div className="flex items-center justify-between text-xs text-gray-400">
                            <span>{deck.total_cards} cards</span>
                            <span>
                              ${deck.total_price_aud?.toFixed(2) || '0.00'} AUD
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Play Test Tab */}
          <TabsContent value="play" className="space-y-6">
            <Card className="bg-black/20 backdrop-blur border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center">
                  <Users className="w-5 h-5 mr-2 text-green-400" />
                  4-Player Commander Simulator
                </CardTitle>
                <CardDescription className="text-purple-200">
                  Test your decks against intelligent AI opponents
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="bg-green-500/10 border-green-500/30">
                    <CardContent className="p-4 text-center">
                      <div className="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-2">
                        <Users className="w-6 h-6 text-green-400" />
                      </div>
                      <h4 className="font-semibold text-white">You</h4>
                      <p className="text-xs text-green-300">40 Life</p>
                    </CardContent>
                  </Card>

                  {[1, 2, 3].map((ai) => (
                    <Card key={ai} className="bg-purple-500/10 border-purple-500/30">
                      <CardContent className="p-4 text-center">
                        <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-2">
                          <Zap className="w-6 h-6 text-purple-400" />
                        </div>  
                        <h4 className="font-semibold text-white">AI Player {ai}</h4>
                        <p className="text-xs text-purple-300">40 Life</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <div className="text-center">
                  <Button 
                    onClick={createTestGame}
                    disabled={gameInProgress}
                    size="lg"
                    className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                  >
                    {gameInProgress ? (
                      <>
                        <Sparkles className="w-4 h-4 mr-2 animate-spin" />
                        Game in Progress...
                      </>
                    ) : (
                      <>
                        <Users className="w-4 h-4 mr-2" />
                        Start 4-Player Game
                      </>
                    )}
                  </Button>
                </div>

                {gameInProgress && (
                  <Card className="bg-blue-500/10 border-blue-500/30">
                    <CardContent className="p-4">
                      <h4 className="font-semibold text-white mb-2 flex items-center">
                        <TrendingUp className="w-4 h-4 mr-2 text-blue-400" />
                        Game Status
                      </h4>
                      <div className="space-y-2 text-sm text-blue-200">
                        <div>• Initializing 4-player Commander game...</div>
                        <div>• AI opponents analyzing opening hands...</div>
                        <div>• Turn 1 begins - AI Player 1 is thinking...</div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-black/20 backdrop-blur-sm mt-16">
        <div className="container mx-auto px-6 py-8">
          <div className="text-center text-gray-400">
            <p className="mb-2">MTG Commander Hub - Built with Scryfall API</p>
            <p className="text-xs">Not affiliated with Wizards of the Coast. Magic: The Gathering is a trademark of Wizards of the Coast LLC.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;