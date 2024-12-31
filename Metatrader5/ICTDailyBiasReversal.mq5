//+------------------------------------------------------------------+
//|                                                 ICTDailyBiasReversal.mq5|
//|                          Copyright 2024, Invest Data Systems FR. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+

#property copyright "Copyright 2023, Invest Data Systems France."
#property link      "https://www.mql5.com"
#property version   "1.01"

#include <Trade\Trade.mqh> // Inclusion de la bibliothèque pour les opérations de trading

double bid, ask;

input bool enableTrading = true; // Option pour activer ou désactiver le trading

CTrade trade;
MqlRates mql_rates[]; // Tableau pour stocker les données de marché
double tenkan_sen_buffer[];
double kijun_sen_buffer[];
double senkou_span_a_buffer[];
double senkou_span_b_buffer[];
double chikou_span_buffer[];

//+------------------------------------------------------------------+
//| Fonction principale exécutée par le script                      |
//+------------------------------------------------------------------+
void OnStart()
{
    printf("Début des traitements Ichimoku");

    // Configure les tableaux comme séries
    ArraySetAsSeries(mql_rates, true);
    ArraySetAsSeries(tenkan_sen_buffer, true);
    ArraySetAsSeries(kijun_sen_buffer, true);
    ArraySetAsSeries(senkou_span_a_buffer, true);
    ArraySetAsSeries(senkou_span_b_buffer, true);
    ArraySetAsSeries(chikou_span_buffer, true);

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

    printf("Fin des traitements Ichimoku");
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

    // Condition pour valider un reversal (tendance haussière vers tendance baissière)
    if ( 
      mql_rates[1].high > mql_rates[2].high // High(-1) > High(-2)
      && mql_rates[1].close > mql_rates[2].close // Close(-1) > Close(-2)
      && mql_rates[1].open < mql_rates[1].close // Candle(-1) is green
      && mql_rates[2].open < mql_rates[2].close // Candle(-2) is green
      && mql_rates[1].close < mql_rates[2].high // Close(-1) < High(-2)
    )
    {
        printf("ICT DB REVERSAL détecté pour " + sname + " à " + mql_rates[0].close);
    }

    // Libération des buffers pour éviter les fuites mémoire
    ArrayFree(mql_rates);
}
