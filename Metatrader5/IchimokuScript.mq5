//+------------------------------------------------------------------+
//|                                   IchimokuScript.mq5             |
//|                          Copyright 2025, Invest Data Systems FR. |
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

int handle = INVALID_HANDLE; // Handle for the Ichimoku indicator

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

    // Paramètres Ichimoku
    int tenkan_sen = 9;
    int kijun_sen = 26;
    int senkou_span_b = 52;

    int max = 64;
    handle = iIchimoku(sname, PERIOD_CURRENT, tenkan_sen, kijun_sen, senkou_span_b);
    if (handle == INVALID_HANDLE)
    {
        printf("Impossible de créer l'indicateur Ichimoku pour " + sname + ". Erreur: " + GetLastError());
        return;
    }

    // Copie des valeurs des buffers Ichimoku
    if (CopyBuffer(handle, TENKANSEN_LINE, 0, max, tenkan_sen_buffer) <= 0 ||
        CopyBuffer(handle, KIJUNSEN_LINE, 0, max, kijun_sen_buffer) <= 0 ||
        CopyBuffer(handle, SENKOUSPANA_LINE, 0, max, senkou_span_a_buffer) <= 0 ||
        CopyBuffer(handle, SENKOUSPANB_LINE, 0, max, senkou_span_b_buffer) <= 0 ||
        CopyBuffer(handle, CHIKOUSPAN_LINE, 0, max, chikou_span_buffer) <= 0)
    {
        printf("Erreur lors de la copie des buffers pour " + sname + ". Erreur: " + GetLastError());
        IndicatorRelease(handle); // Release the indicator handle
        return;
    }

    int index = 0;

    // Vérification des tailles avant d'accéder aux données
    if (ArraySize(mql_rates) <= index ||
        ArraySize(senkou_span_a_buffer) <= index ||
        ArraySize(senkou_span_b_buffer) <= index)
    {
        printf("Index hors limite détecté pour " + sname);
        IndicatorRelease(handle); // Release the indicator handle
        return;
    }

    // Exemple de condition pour valider un signal d'achat
    if ((senkou_span_a_buffer[index] < senkou_span_b_buffer[index] &&
         mql_rates[index].open < senkou_span_b_buffer[index] &&
         mql_rates[index].close > senkou_span_b_buffer[index]) ||
        (senkou_span_a_buffer[index] > senkou_span_b_buffer[index] &&
         mql_rates[index].open < senkou_span_a_buffer[index] &&
         mql_rates[index].close > senkou_span_a_buffer[index]))
    {
        printf("BUY SIGNAL DETECTED FOR " + sname + " à " + mql_rates[index].close);
        // trade.Buy(0.5, sname, ask, 0, 0, "Signal d'achat Ichimoku");
    }

    // Exemple de condition pour valider un signal de vente
    if ((senkou_span_a_buffer[index] < senkou_span_b_buffer[index] &&
         mql_rates[index].open > senkou_span_a_buffer[index] &&
         mql_rates[index].close < senkou_span_a_buffer[index]) ||
        (senkou_span_a_buffer[index] > senkou_span_b_buffer[index] &&
         mql_rates[index].open > senkou_span_b_buffer[index] &&
         mql_rates[index].close < senkou_span_b_buffer[index]))
    {
        printf("SELL SIGNAL DETECTED FOR " + sname + " à " + mql_rates[index].close);
        // trade.Sell(0.5, sname, bid, 0, 0, "Signal de vente Ichimoku");
    }

    // Libération des buffers pour éviter les fuites mémoire
    ArrayFree(senkou_span_b_buffer);
    ArrayFree(senkou_span_a_buffer);
    ArrayFree(tenkan_sen_buffer);
    ArrayFree(kijun_sen_buffer);
    ArrayFree(chikou_span_buffer);
    ArrayFree(mql_rates);

    // Release the indicator handle
    IndicatorRelease(handle);
}

//+------------------------------------------------------------------+
//| Fonction de désinitialisation                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    printf("Script terminé. Raison: " + IntegerToString(reason));

    // Release the indicator handle if it was created
    if (handle != INVALID_HANDLE)
    {
        IndicatorRelease(handle);
        printf("Handle de l'indicateur Ichimoku libéré.");
    }

    // Free all arrays
    ArrayFree(senkou_span_b_buffer);
    ArrayFree(senkou_span_a_buffer);
    ArrayFree(tenkan_sen_buffer);
    ArrayFree(kijun_sen_buffer);
    ArrayFree(chikou_span_buffer);
    ArrayFree(mql_rates);

    printf("Nettoyage des ressources terminé.");
}