﻿//+------------------------------------------------------------------+
//|                                                  ScanGainers.mq5 |
//|                        Copyright 2025, BCXP                      |
//|                                       https://www.mql5.com       |
//| https://build.nvidia.com/qwen/qwen2_5-coder-32b-instruct         |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
  {
   // Obtenir le nombre total de symboles
   int totalSymbols = SymbolsTotal(false);
   if(totalSymbols == 0)
     {
      Print("Aucun symbole disponible.");
      return;
     }

   // Parcourir tous les symboles
   for(int i = 0; i < totalSymbols; i++)
     {
      string symbol = SymbolName(i, false);
      if(symbol == "")
         continue;

      // Obtenir les données de la journée pour le symbole
      MqlRates rates[];
      int copied = CopyRates(symbol, PERIOD_D1, 0, 2, rates);
      if(copied < 2)
        {
         Print("Impossible d'obtenir les données pour ", symbol);
         continue;
        }

      // Calculer la progression en pourcentage
      double openPrice = rates[1].open;
      double closePrice = rates[0].close;
      double percentageChange = ((closePrice - openPrice) / openPrice) * 100.0;

      // Vérifier si la progression est de +1% ou plus
      if(percentageChange >= 1.0)
        {
         Print(symbol, " a progressé de ", DoubleToString(percentageChange, 2), "% aujourd'hui.");
        }
     }
  }
//+------------------------------------------------------------------+
