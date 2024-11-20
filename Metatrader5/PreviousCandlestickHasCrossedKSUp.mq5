//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
// Previous candlestick has opened below KS and closed above KS

#include <Trade\Trade.mqh>
void OnStart()
{
   // Liste des symboles dans le Market Watch
   string symbol_name;
   int total_symbols = SymbolsTotal(true);
   
   Print("Scan des actifs dans le Market Watch...");
   
   for (int i = 0; i < total_symbols; i++)
   {
      // Obtenir le nom du symbole
      symbol_name = SymbolName(i, true);
      if (symbol_name == "") continue;
      
      // Accéder aux données des prix et vérifier si elles sont disponibles
      if (!SymbolSelect(symbol_name, true))
      {
         Print("Impossible de sélectionner le symbole ", symbol_name);
         continue;
      }
      
      // Paramètres de l'indicateur Ichimoku
      int tenkan = 9;
      int kijun = 26;
      int senkou_span_b = 52;
      
      // Charger les données de l'indicateur Ichimoku
      double kijun_sen[];
      if (CopyBuffer(iIchimoku(symbol_name, PERIOD_CURRENT, tenkan, kijun, senkou_span_b), 1, 1, 2, kijun_sen) < 2)
      {
         Print("Impossible de charger les données Ichimoku pour ", symbol_name);
         continue;
      }
      
      // Charger les données d'ouverture et de clôture des bougies
      double open_prices[], close_prices[];
      if (CopyOpen(symbol_name, PERIOD_CURRENT, 1, 2, open_prices) < 2 || CopyClose(symbol_name, PERIOD_CURRENT, 1, 2, close_prices) < 2)
      {
         Print("Impossible de charger les données des prix pour ", symbol_name);
         continue;
      }
      
      // Comparer l'ouverture et la clôture de la dernière bougie par rapport à la Kijun-sen
      if (open_prices[1] < kijun_sen[1] && close_prices[1] > kijun_sen[1])
      {
         Print("Le symbole ", symbol_name, " a une bougie qui a ouvert sous la Kijun-sen et fermé au-dessus.");
      }
   }
   
   Print("Scan terminé.");
}
