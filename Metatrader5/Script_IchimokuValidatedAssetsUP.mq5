//+------------------------------------------------------------------+
//|                                                      Scanner.mq5 |
//|                        Analyse Ichimoku sur tous les actifs      |
//+------------------------------------------------------------------+
#property copyright "2024"
#property version   "1.03"
#property strict

#include <Trade/Trade.mqh>

//--- Variables globales
input ENUM_TIMEFRAMES TimeFrame = PERIOD_H1; // Timeframe pour l'analyse

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("Début du scan Ichimoku sur tous les actifs dans le MarketWatch.");
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("Fin du scan Ichimoku.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnStart()
{
   Print("Scan Started");
   ScanMarketWatch();
   Print("Scan Ended");
}

//+------------------------------------------------------------------+
//| Fonction de scan du MarketWatch                                  |
//+------------------------------------------------------------------+
void ScanMarketWatch()
{
    int totalSymbols = SymbolsTotal(true); // Obtenir tous les actifs visibles dans le MarketWatch

    for (int i = 0; i < totalSymbols; i++)
    {
        string symbol = SymbolName(i, true);
        if (symbol == "") continue; // Passer les symboles invalides
        
        //if (symbol != "USDJPY") continue;

        double price = SymbolInfoDouble(symbol, SYMBOL_BID);
        if (price == 0) continue; // Passer les symboles sans cotations

        if (IsAboveIchimoku(symbol, PERIOD_CURRENT, price))
        {
            PrintFormat("%s est au-dessus de SSA, SSB, Kijun, Tenkan, et Chikou valide (Prix actuel: %.5f)", symbol, price);
        }
    }
}

//+------------------------------------------------------------------+
//| Vérifie si le prix actuel est au-dessus des niveaux Ichimoku     |
//+------------------------------------------------------------------+
bool IsAboveIchimoku(string symbol, ENUM_TIMEFRAMES timeframe, double price)
{
    int ichimokuHandle = iIchimoku(symbol, timeframe, 9, 26, 52);

    if (ichimokuHandle == INVALID_HANDLE)
    {
        PrintFormat("Erreur lors de la création de l'indicateur Ichimoku pour %s", symbol);
        return false;
    }

    double SSA[], SSB[], Kijun[], Tenkan[], Chikou[], HighPrices[];

    // Charger les données Ichimoku et les prix de clôture
    if (!CopyBuffer(ichimokuHandle, 0, 0, 1, SSA) ||  // SSA
        !CopyBuffer(ichimokuHandle, 1, 0, 1, SSB) ||  // SSB
        !CopyBuffer(ichimokuHandle, 2, 0, 1, Tenkan) ||  // Tenkan-sen
        !CopyBuffer(ichimokuHandle, 3, 0, 1, Kijun) ||  // Kijun-sen
        !CopyBuffer(ichimokuHandle, 4, 0, 100, Chikou) || // Chikou Span (décalé de 26 périodes)
        !CopyHigh(symbol, timeframe, 0, 50, HighPrices)) // Récupérer le prix de clôture 26 périodes avant
    {
        PrintFormat("Erreur lors de la récupération des données Ichimoku pour %s", symbol);
        return false;
    }

    // Fermer le handle pour libérer des ressources
    IndicatorRelease(ichimokuHandle);
    
    //Print(Chikou[25], " ", ClosePrices[0]);
    //for (int i=0; i<100; i++) Print(i, " ", Chikou[i]);
    //for (int i=0; i<50; i++) Print(i, " ", HighPrices[i]);
    
    // Comparer le prix avec les niveaux Ichimoku
    if (price > SSA[0] && price > SSB[0] && price > Kijun[0] && price > Tenkan[0] &&
        Chikou[25] > SSA[0] && Chikou[25] > SSB[0] && Chikou[25] > Kijun[0] && Chikou[25] > Tenkan[0] &&
        Chikou[71] > HighPrices[23]) // Vérification Chikou Span au-dessus du prix correspondant (26 périodes en arrière)
    {
        return true;
    }

    return false;
}
