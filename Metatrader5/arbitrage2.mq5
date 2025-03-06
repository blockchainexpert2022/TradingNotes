//+------------------------------------------------------------------+
//|                                                    Arbitrage.mq5 |
//|                        Copyright 2025, BCXP Fashion Paris        |
//|                                       https://www.mql5.com       |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
  {
   while(true)
     {

      // Noms des actifs
      string symbol1 = "EURUSD";
      string symbol2 = "USDJPY";
      string symbol3 = "EURJPY";

      // Vérifier si les actifs sont sélectionnables
      if(!SymbolSelect(symbol1, true))
        {
         Print("Actif ", symbol1, " non sélectionnable.");
         return;
        }
      if(!SymbolSelect(symbol2, true))
        {
         Print("Actif ", symbol2, " non sélectionnable.");
         return;
        }
      if(!SymbolSelect(symbol3, true))
        {
         Print("Actif ", symbol3, " non sélectionnable.");
         return;
        }

      // Obtenir les prix des actifs
      double bid1 = SymbolInfoDouble(symbol1, SYMBOL_BID);
      double ask1 = SymbolInfoDouble(symbol1, SYMBOL_ASK);
      double bid2 = SymbolInfoDouble(symbol2, SYMBOL_BID);
      double ask2 = SymbolInfoDouble(symbol2, SYMBOL_ASK);
      double bid3 = SymbolInfoDouble(symbol3, SYMBOL_BID);
      double ask3 = SymbolInfoDouble(symbol3, SYMBOL_ASK);

      // Vérifier si les prix sont valides
      if(bid1 == 0 || ask1 == 0 || bid2 == 0 || ask2 == 0 || bid3 == 0 || ask3 == 0)
        {
         Print("Prix non valides pour un ou plusieurs actifs.");
         return;
        }

      // Calculer les prix implicites de EUR/JPY
      double implicit_bid3 = bid1 * bid2;
      double implicit_ask3 = ask1 * ask2;

      // Définir un seuil pour détecter l'arbitrage
      double threshold = 0.0001; // 1%

      // Vérifier si l'écart de prix dépasse le seuil
      if(MathAbs(bid3 - implicit_ask3) > threshold * bid3 || MathAbs(ask3 - implicit_bid3) > threshold * ask3)
        {
         Print("Opportunité d'arbitrage détectée : ", symbol1, " et ", symbol2);
         Print("Prix ", symbol1, " (Bid) : ", bid1);
         Print("Prix ", symbol1, " (Ask) : ", ask1);
         Print("Prix ", symbol2, " (Bid) : ", bid2);
         Print("Prix ", symbol2, " (Ask) : ", ask2);
         Print("Prix ", symbol3, " (Bid) : ", bid3);
         Print("Prix ", symbol3, " (Ask) : ", ask3);
         Print("Prix implicite ", symbol3, " (Bid) : ", implicit_bid3);
         Print("Prix implicite ", symbol3, " (Ask) : ", implicit_ask3);
         Print("Écart de prix entre ", symbol3, " (Bid) et ", symbol1, "/", symbol2, " (Ask) : ", bid3 - implicit_ask3);
         Print("Écart de prix entre ", symbol3, " (Ask) et ", symbol1, "/", symbol2, " (Bid) : ", ask3 - implicit_bid3);
         return;
        }
      else
        {
         //Print("Aucune opportunité d'arbitrage détectée.");
        }
     }
//+------------------------------------------------------------------+

  }
//+------------------------------------------------------------------+
