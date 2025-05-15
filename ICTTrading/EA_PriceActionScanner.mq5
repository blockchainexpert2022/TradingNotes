//+------------------------------------------------------------------+
//|                                         EA_PriceActionScanner.mq5 |
//|                        Copyright 2025, InvestDataSystems/Reuniware |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "InvestDataSystems/Reuniware"
#property link      "https://ntic974.blogspot.com"
#property version   "1.03" // Incrémenté la version pour le débogage
#property description "Scanne le Market Watch pour des patterns de Price Action et Chandeliers."

//--- Inputs
input group "Scan Settings"
input int                ScanIntervalSeconds = 60;      // Intervalle de scan en secondes
input ENUM_TIMEFRAMES    TimeframeToScan   = PERIOD_H1; // Timeframe à analyser
input int                BarsToAnalyze     = 50;      // Nombre de barres à charger pour l'analyse
input int                AnalysisBarIndex  = 1;       // Barre à analyser (0=actuelle, 1=dernière clôturée, etc.)

input group "Pattern Sensitivity"
input double             DojiBodyMaxPercent    = 0.1;   // % max du corps par rapport au range total pour un Doji
input double             HammerWickMinRatio  = 2.0;   // Ratio min: Mèche / Corps pour Marteau/Étoile filante
input double             HammerBodyMaxPercent  = 0.33;  // % max du corps par rapport au range total pour Marteau/Étoile filante
input bool               EngulfingStrictRange = false; // Pour Engulfing: le range total doit-il aussi englober?
input bool               HaramiStrictRange    = true;  // Pour Harami: le range total du bébé doit-il être dans le range de la mère?

//--- Global variables
MqlRates rates[];         // Array pour stocker les données de prix
datetime g_last_scan_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("EA_PriceActionScanner initialisé. Scan sur ", EnumToString(TimeframeToScan),
         ", intervalle: ", ScanIntervalSeconds, "s, barre d'analyse: ", AnalysisBarIndex);
   g_last_scan_time = TimeCurrent() - ScanIntervalSeconds; // Permet un scan immédiat au démarrage
   EventSetTimer(ScanIntervalSeconds); // Utiliser le timer pour les scans périodiques
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("EA_PriceActionScanner désinitialisé. Raison: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function (pas utilisé directement pour le scan)      |
//+------------------------------------------------------------------+
void OnTick()
{
   // Le scan principal est géré par OnTimer
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   Print("Début du scan des patterns...");
   ScanMarketWatch();
   Print("Scan des patterns terminé.");
}

//+------------------------------------------------------------------+
//| Scanne tous les symboles du Market Watch                         |
//+------------------------------------------------------------------+
void ScanMarketWatch()
{
   int total_symbols = SymbolsTotal(true); // true = seulement ceux visibles dans Market Watch

   for(int i = 0; i < total_symbols; i++)
   {
      string symbol_name = SymbolName(i, true);

      if(MQLInfoInteger(MQL_VISUAL_MODE))
      {
         if(symbol_name == _Symbol)
         {
            // Continue;
         }
      }

      if(CopyRates(symbol_name, TimeframeToScan, 0, BarsToAnalyze, rates) < BarsToAnalyze)
      {
         Print("Erreur: Impossible de copier assez de données pour ", symbol_name, " sur ", EnumToString(TimeframeToScan));
         continue;
      }
      ArraySetAsSeries(rates, true);

      if(AnalysisBarIndex >= BarsToAnalyze || AnalysisBarIndex < 0)
      {
         Print("Erreur: AnalysisBarIndex (", AnalysisBarIndex, ") est hors des limites pour ", symbol_name);
         continue;
      }

      string pattern_found = "";

      // MODIFICATION ICI pour inclure l'implication du pattern
      if(IsDoji(rates, AnalysisBarIndex)) pattern_found += "Doji (Neutre/Indécision); ";
      if(IsHammer(rates, AnalysisBarIndex)) pattern_found += "Marteau (Potentiel Haussier); ";
      if(IsHangingMan(rates, AnalysisBarIndex)) pattern_found += "Pendu (Potentiel Baissier); ";
      if(IsInvertedHammer(rates, AnalysisBarIndex)) pattern_found += "Marteau Inversé (Potentiel Haussier); ";
      if(IsShootingStar(rates, AnalysisBarIndex)) pattern_found += "Étoile Filante (Potentiel Baissier); ";
      if(IsBullishEngulfing(rates, AnalysisBarIndex)) pattern_found += "Avalement Haussier (Haussier); ";
      if(IsBearishEngulfing(rates, AnalysisBarIndex)) pattern_found += "Avalement Baissier (Baissier); ";
      if(IsBullishHarami(rates, AnalysisBarIndex)) pattern_found += "Harami Haussier (Haussier); ";
      if(IsBearishHarami(rates, AnalysisBarIndex)) pattern_found += "Harami Baissier (Baissier); ";
      if(IsInsideBar(rates, AnalysisBarIndex)) pattern_found += "Inside Bar (Stabilisation/Indécision); ";

      if(pattern_found != "")
      {
         string final_pattern_text = StringTrimRight(pattern_found);

         // Débogage pour voir les valeurs
         Print("Debug pour ", symbol_name, ": pattern_found brut = '", pattern_found, "'");
         Print("Debug pour ", symbol_name, ": final_pattern_text (après trim) = '", final_pattern_text, "'");

         if (final_pattern_text == NULL) {
             Print("Alerte critique: final_pattern_text est NULL pour ", symbol_name);
             final_pattern_text = "ERREUR_PATTERN_NULL";
         } else if (StringLen(final_pattern_text) == 0 && StringLen(pattern_found) > 0) {
             // Cela pourrait indiquer que pattern_found ne contenait que des espaces ou des caractères non imprimables qui ont été supprimés par StringTrimRight
             Print("Info: final_pattern_text est une chaîne vide après trim pour ", symbol_name, " (pattern_found était '", pattern_found, "').");
             // On pourrait décider de ne pas alerter dans ce cas, ou d'utiliser une chaîne par défaut.
             // Pour l'instant, on laisse passer pour voir si StringFormat gère une chaîne vide.
         }


         string message = StringFormat("%s (%s) sur barre [%s]: %s",
                                       symbol_name,
                                       EnumToString(TimeframeToScan),
                                       IntegerToString(AnalysisBarIndex),
                                       final_pattern_text);

         // Débogage supplémentaire pour le message
         Print("Debug pour ", symbol_name, ": message formaté = '", message, "'");

         Alert(message);
         Print(message, " (Clôture: ", TimeToString(rates[AnalysisBarIndex].time, TIME_DATE | TIME_MINUTES), ")");
      }
   }
}

//+------------------------------------------------------------------+
//| Fonctions de détection de Patterns                               |
//+------------------------------------------------------------------+

//--- Vérifie si une bougie est un Doji
bool IsDoji(const MqlRates &r[], int index)
{
   if(index < 0 || index >= ArraySize(r)) return false;
   MqlRates candle = r[index];
   double body = MathAbs(candle.open - candle.close);
   double range = candle.high - candle.low;
   if(range == 0) return false; // Évite la division par zéro si la bougie n'a pas de range
   return ((body / range) <= DojiBodyMaxPercent);
}

//--- Structure pour aider à définir les mèches et le corps
struct CandleParts
{
   double body;
   double upper_wick;
   double lower_wick;
   double range;
   bool   is_bullish;
   bool   is_bearish;

   void Calculate(const MqlRates &candle)
   {
      body       = MathAbs(candle.open - candle.close);
      upper_wick = candle.high - MathMax(candle.open, candle.close);
      lower_wick = MathMin(candle.open, candle.close) - candle.low;
      range      = candle.high - candle.low;
      is_bullish = candle.close > candle.open;
      is_bearish = candle.close < candle.open;
   }
};

//--- Vérifie Marteau (contexte baissier implicite par la forme)
bool IsHammer(const MqlRates &r[], int index)
{
   if(index < 0 || index >= ArraySize(r)) return false;
   MqlRates candle = r[index];
   CandleParts cp;
   cp.Calculate(candle);

   if(cp.range == 0 || cp.body == 0) return false; // Évite la division par zéro ou les ratios non pertinents

   return(cp.lower_wick >= HammerWickMinRatio * cp.body &&
          cp.upper_wick < cp.body * 0.5 &&
          (cp.body / cp.range) <= HammerBodyMaxPercent);
}

//--- Vérifie Pendu (contexte haussier implicite par la forme)
bool IsHangingMan(const MqlRates &r[], int index)
{
   return IsHammer(r, index);
}

//--- Vérifie Marteau Inversé
bool IsInvertedHammer(const MqlRates &r[], int index)
{
   if(index < 0 || index >= ArraySize(r)) return false;
   MqlRates candle = r[index];
   CandleParts cp;
   cp.Calculate(candle);

   if(cp.range == 0 || cp.body == 0) return false;

   return(cp.upper_wick >= HammerWickMinRatio * cp.body &&
          cp.lower_wick < cp.body * 0.5 &&
          (cp.body / cp.range) <= HammerBodyMaxPercent);
}

//--- Vérifie Étoile Filante
bool IsShootingStar(const MqlRates &r[], int index)
{
   return IsInvertedHammer(r, index);
}

//--- Vérifie Avalement Haussier
bool IsBullishEngulfing(const MqlRates &r[], int index)
{
   if(index + 1 >= ArraySize(r) || index < 0) return false;
   MqlRates current_candle = r[index];
   MqlRates prev_candle    = r[index + 1];

   bool basic_engulfing =
      current_candle.close > current_candle.open &&
      prev_candle.close < prev_candle.open &&
      current_candle.close > prev_candle.open &&
      current_candle.open < prev_candle.close;

   if(!basic_engulfing) return false;
   if(EngulfingStrictRange)
   {
      return (current_candle.high >= prev_candle.high && current_candle.low <= prev_candle.low);
   }
   return true;
}

//--- Vérifie Avalement Baissier
bool IsBearishEngulfing(const MqlRates &r[], int index)
{
   if(index + 1 >= ArraySize(r) || index < 0) return false;
   MqlRates current_candle = r[index];
   MqlRates prev_candle    = r[index + 1];

   bool basic_engulfing =
      current_candle.close < current_candle.open &&
      prev_candle.close > prev_candle.open &&
      current_candle.open > prev_candle.close &&
      current_candle.close < prev_candle.open;

   if(!basic_engulfing) return false;
   if(EngulfingStrictRange)
   {
      return (current_candle.high >= prev_candle.high && current_candle.low <= prev_candle.low);
   }
   return true;
}

//--- Vérifie Harami Haussier
bool IsBullishHarami(const MqlRates &r[], int index)
{
   if(index + 1 >= ArraySize(r) || index < 0) return false;
   MqlRates current_candle = r[index];
   MqlRates prev_candle    = r[index + 1];

   bool basic_harami =
      prev_candle.close < prev_candle.open &&
      current_candle.close > current_candle.open &&
      MathMax(current_candle.open, current_candle.close) < MathMax(prev_candle.open, prev_candle.close) &&
      MathMin(current_candle.open, current_candle.close) > MathMin(prev_candle.open, prev_candle.close);

   if(!basic_harami) return false;
   if(HaramiStrictRange)
   {
      return (current_candle.high < prev_candle.high && current_candle.low > prev_candle.low);
   }
   return true;
}

//--- Vérifie Harami Baissier
bool IsBearishHarami(const MqlRates &r[], int index)
{
   if(index + 1 >= ArraySize(r) || index < 0) return false;
   MqlRates current_candle = r[index];
   MqlRates prev_candle    = r[index + 1];

   bool basic_harami =
      prev_candle.close > prev_candle.open &&
      current_candle.close < current_candle.open &&
      MathMax(current_candle.open, current_candle.close) < MathMax(prev_candle.open, prev_candle.close) &&
      MathMin(current_candle.open, current_candle.close) > MathMin(prev_candle.open, prev_candle.close);

   if(!basic_harami) return false;
   if(HaramiStrictRange)
   {
      return (current_candle.high < prev_candle.high && current_candle.low > prev_candle.low);
   }
   return true;
}

//--- Vérifie Inside Bar
bool IsInsideBar(const MqlRates &r[], int index)
{
    if(index + 1 >= ArraySize(r) || index < 0) return false;
    MqlRates current_candle = r[index];
    MqlRates mother_candle  = r[index + 1];
    return (current_candle.high < mother_candle.high &&
            current_candle.low > mother_candle.low);
}
//+------------------------------------------------------------------+
