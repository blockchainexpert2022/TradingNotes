//+------------------------------------------------------------------+
//|               ICTDailyBiasReversalOrContinuation005-UDUU-DUDD.mq5|
//|                          Copyright 2025, Invest Data Systems FR. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+

// This version logs the date and time of the current price in the logged data

#property copyright "Copyright 2025, Invest Data Systems France."
#property link      "https://www.mql5.com"
#property version   "1.01"

#include <Trade\Trade.mqh> // Inclusion de la bibliothèque pour les opérations de trading

double bid, ask;

input bool enableTrading = true; // Option pour activer ou désactiver le trading

input bool showReachedTargets = true; // MAJOR IMPROVEMENT IN THIS VERSION

CTrade trade;
MqlRates mql_rates[]; // Tableau pour stocker les données de marché

//+------------------------------------------------------------------+
//| Fonction principale exécutée par le script                      |
//+------------------------------------------------------------------+
void OnStart()
{
    printf("Début des traitements ICTDailyBias");

    // Configure les tableaux comme séries
    ArraySetAsSeries(mql_rates, true);

    bool onlySymbolsInMarketwatch = true;
    int stotal = SymbolsTotal(onlySymbolsInMarketwatch); // Seulement les symboles du MarketWatch

    // Boucle sur tous les symboles pour exécuter la logique Ichimoku
    for (int sindex = 0; sindex < stotal; sindex++)
    {
        string sname = SymbolName(sindex, onlySymbolsInMarketwatch);
        if (sname != "")
        {
            Ichimoku(sname);
        }
    }

    printf("Fin des traitements ICTDailyBias");
}

//+------------------------------------------------------------------+
//| Fonction d'analyse Ichimoku pour un symbole donné               |
//+------------------------------------------------------------------+
void Ichimoku(string sname)
{
    // Vérifier si le trading est activé
    if (!enableTrading)
    {
        printf("Trading désactivé pour " + sname);
        return;
    }

    // Récupération des données de marché
    if (CopyRates(sname, PERIOD_CURRENT, 0, 32, mql_rates) <= 0)
    {
        printf("Erreur lors de la copie des données pour " + sname + ". Erreur: " + GetLastError());
        return;
    }

    bid = SymbolInfoDouble(sname, SYMBOL_BID);
    ask = SymbolInfoDouble(sname, SYMBOL_ASK);

    // Vérification des tailles avant d'accéder aux données
    if (ArraySize(mql_rates) <= 10)
    {
        printf("Index hors limite détecté pour " + sname);
        return;
    }
    
    datetime barTime = mql_rates[0].time;
    string strdt = TimeToString(barTime, TIME_DATE | TIME_MINUTES); 

    // Condition pour valider un reversal (tendance haussière vers tendance baissière)
    if ( 
      mql_rates[1].high > mql_rates[2].high // High(-1) > High(-2)
      && mql_rates[1].close > mql_rates[2].close // Close(-1) > Close(-2)
      && mql_rates[1].open < mql_rates[1].close // Candle(-1) is green
      && mql_rates[2].open < mql_rates[2].close // Candle(-2) is green
      && mql_rates[1].close < mql_rates[2].high // Close(-1) < High(-2)
    )
    {
        bool bTargetReached = false;
        if (mql_rates[0].low < mql_rates[1].low) {
         //printf(">>> Target has already been reached");
         bTargetReached = true;
        }
        if (showReachedTargets && bTargetReached) printf("ICT DB REVERSAL (U->D) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].low + " " + (bTargetReached?">>> Target has already been reached":""));
        else if (!bTargetReached) printf("ICT DB REVERSAL (U->D) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].low + " " + (bTargetReached?">>> Target has already been reached":""));        
    }

    // Condition pour valider une continuation tendance haussière
    if ( 
      mql_rates[1].high > mql_rates[2].high // High(-1) > High(-2)
      && mql_rates[1].close > mql_rates[2].high // Close(-1) > High(-2)
      && mql_rates[1].open < mql_rates[1].close // Candle(-1) is green
      && mql_rates[2].open < mql_rates[2].close // Candle(-2) is green
    )
    {
        bool bTargetReached = false;
        if (mql_rates[0].high > mql_rates[1].high) {
        bTargetReached = true;
         //printf(">>> Target has already been reached");
        }
        if (showReachedTargets && bTargetReached) printf("ICT DB CONTINUATION (U->U) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].high + " " + (bTargetReached?">>> Target has already been reached":""));
        else if (!bTargetReached) printf("ICT DB CONTINUATION (U->U) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].high + " " + (bTargetReached?">>> Target has already been reached":""));
    }


    // Condition pour valider un reversal (tendance baissière vers tendance haussière)
    if ( 
      mql_rates[1].low < mql_rates[2].low // Close(-1) < Close(-2)
      && mql_rates[1].close < mql_rates[2].close // Close(-1) < Close(-2)
      && mql_rates[1].open > mql_rates[1].close // Candle(-1) is red
      && mql_rates[2].open > mql_rates[2].close // Candle(-2) is red
      && mql_rates[1].close > mql_rates[2].low // Close(-1) > Low(-2)
    )
    {
        bool bTargetReached = false;
        if (mql_rates[0].high > mql_rates[1].high) {
         //printf(">>> Target has already been reached");
         bTargetReached = true;
        }
        if (showReachedTargets && bTargetReached) printf("ICT DB REVERSAL (D->U) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].high + " " + (bTargetReached?">>> Target has already been reached":""));
        else if (!bTargetReached) printf("ICT DB REVERSAL (D->U) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].high + " " + (bTargetReached?">>> Target has already been reached":""));
    }

    // Condition pour valider une continuation tendance baissière
    if ( 
      mql_rates[1].low < mql_rates[2].low // Close(-1) < Close(-2)
      && mql_rates[1].close < mql_rates[2].low // Close(-1) < Low(-2)
      && mql_rates[1].open > mql_rates[1].close // Candle(-1) is red
      && mql_rates[2].open > mql_rates[2].close // Candle(-2) is red
    )
    {
        bool bTargetReached = false;
        if (mql_rates[0].low < mql_rates[1].low) {
        bTargetReached = true;
         //printf(">>> Target has already been reached");
        }        
        if (showReachedTargets && bTargetReached) printf("ICT DB CONTINUATION (D->D) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].low + " " + (bTargetReached?">>> Target has already been reached":""));
        else if (!bTargetReached) printf("ICT DB CONTINUATION (D->D) detected for " + sname + " (" + strdt + ") at " + mql_rates[0].close + " target = " + mql_rates[1].low + " " + (bTargetReached?">>> Target has already been reached":""));
    }


    // Libération des buffers pour éviter les fuites mémoire
    ArrayFree(mql_rates);
}
