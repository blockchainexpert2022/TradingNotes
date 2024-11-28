//+------------------------------------------------------------------+
//|                                                 IchimokuScript.mq5|
//|                          Copyright 2023, Invest Data Systems FR. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+

#property copyright "Copyright 2023, Invest Data Systems France. mailto: investdatasystems@yahoo.com"
#property link      "https://www.mql5.com"
#property version   "1.00"

// Inclusion de la bibliothèque pour les opérations de trading (facultative)
#include <Trade\Trade.mqh>

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
         printf("Analyse du symbole : " + sname);
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
   int handle = iIchimoku(sname, PERIOD_CURRENT, tenkan_sen, kijun_sen, senkou_span_b);
   if (handle == INVALID_HANDLE)
     {
      printf("Impossible de créer l'indicateur Ichimoku pour " + sname + ". Erreur: " + GetLastError());
      return;
     }

   // Copie des valeurs des buffers Ichimoku
   CopyBuffer(handle, TENKANSEN_LINE, 0, max, tenkan_sen_buffer);
   CopyBuffer(handle, KIJUNSEN_LINE, 0, max, kijun_sen_buffer);
   CopyBuffer(handle, SENKOUSPANA_LINE, 0, max, senkou_span_a_buffer);
   CopyBuffer(handle, SENKOUSPANB_LINE, 0, max, senkou_span_b_buffer);
   CopyBuffer(handle, CHIKOUSPAN_LINE, 0, max, chikou_span_buffer);

   // Validation des conditions Ichimoku
   double cs = chikou_span_buffer[26];
   double ssb_cs = senkou_span_b_buffer[26];
   double ssa_cs = senkou_span_a_buffer[27];
   double tenkan_cs = tenkan_sen_buffer[27];
   double kijun_cs = kijun_sen_buffer[26];

   // Exemple de condition pour valider un signal d'achat
   if (mql_rates[0].close > senkou_span_b_buffer[0]
       && mql_rates[0].close > senkou_span_a_buffer[0]
       && mql_rates[0].close > tenkan_sen_buffer[0]
       && mql_rates[0].close > kijun_sen_buffer[0]
       && cs > tenkan_cs
       && cs > kijun_cs
       && cs > ssa_cs
       && cs > ssb_cs)
     {
      printf("Signal d'achat détecté pour " + sname);
     }

   // Exemple de condition pour valider un signal de vente
   if (mql_rates[0].close < senkou_span_b_buffer[0]
       && mql_rates[0].close < senkou_span_a_buffer[0]
       && mql_rates[0].close < tenkan_sen_buffer[0]
       && mql_rates[0].close < kijun_sen_buffer[0]
       && cs < tenkan_cs
       && cs < kijun_cs
       && cs < ssa_cs
       && cs < ssb_cs)
     {
      printf("Signal de vente détecté pour " + sname);
     }

   // Libération des buffers pour éviter les fuites mémoire
   ArrayFree(senkou_span_b_buffer);
   ArrayFree(senkou_span_a_buffer);
   ArrayFree(tenkan_sen_buffer);
   ArrayFree(kijun_sen_buffer);
   ArrayFree(chikou_span_buffer);
   ArrayFree(mql_rates);
  }
