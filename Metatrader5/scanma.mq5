//+------------------------------------------------------------------+
//|                                                      MACross.mq5 |
//|                        Copyright 2025, Blockchainexpert2025      |
//|                                             https://www.mql5.com |
//| https://build.nvidia.com/deepseek-ai/deepseek-r1                 |
//+------------------------------------------------------------------+
#property script_show_inputs

//--- Paramètres d'entrée
input ENUM_TIMEFRAMES TimeFrame = PERIOD_CURRENT;  // Période temporelle
input int             MAPeriodFast = 9;           // Période MA rapide
input int             MAPeriodSlow = 26;          // Période MA lente
input ENUM_MA_METHOD  MAMethod = MODE_SMA;        // Méthode de lissage
input ENUM_APPLIED_PRICE PriceType = PRICE_CLOSE; // Type de prix

//+------------------------------------------------------------------+
//| Script execution function                                        |
//+------------------------------------------------------------------+
void OnStart()
{
   int total_symbols = SymbolsTotal(true);
   string cross_symbols = "";
   
   for(int i = 0; i < total_symbols; i++)
   {
      string symbol = SymbolName(i, true);
      
      // Création des handles des indicateurs
      int handle_fast = iMA(symbol, TimeFrame, MAPeriodFast, 0, MAMethod, PriceType);
      int handle_slow = iMA(symbol, TimeFrame, MAPeriodSlow, 0, MAMethod, PriceType);
      
      if(handle_fast == INVALID_HANDLE || handle_slow == INVALID_HANDLE)
      {
         Print("Erreur de création des handles MA pour ", symbol);
         continue;
      }

      // Récupération des valeurs des MA
      double ma_fast[2], ma_slow[2];
      
      if(CopyBuffer(handle_fast, 0, 0, 2, ma_fast) != 2 || 
         CopyBuffer(handle_slow, 0, 0, 2, ma_slow) != 2)
      {
         Print("Données insuffisantes pour ", symbol);
         IndicatorRelease(handle_fast);
         IndicatorRelease(handle_slow);
         continue;
      }

      // Vérification du croisement
      bool bullish_cross = (ma_fast[1] < ma_slow[1]) && (ma_fast[0] > ma_slow[0]);
      bool bearish_cross = (ma_fast[1] > ma_slow[1]) && (ma_fast[0] < ma_slow[0]);

      if(bullish_cross || bearish_cross)
      {
         cross_symbols += StringFormat("%s (%s croisement)\n", 
                        symbol, 
                        bullish_cross ? "Haussier" : "Baissier");
      }

      // Libération des handles
      IndicatorRelease(handle_fast);
      IndicatorRelease(handle_slow);
   }

   // Affichage des résultats
   if(cross_symbols != "")
      MessageBox("Actifs avec croisement MA:\n" + cross_symbols, "Résultats", MB_ICONINFORMATION);
   else
      MessageBox("Aucun croisement détecté", "Information", MB_ICONINFORMATION);
}
//+------------------------------------------------------------------+
