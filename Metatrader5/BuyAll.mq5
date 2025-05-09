//+------------------------------------------------------------------+
//|                                                  BuyAllAssets.mq5 |
//|                        Script for MetaTrader 5                   |
//|                       Acheté 0.01 lot de chaque actif             |
//+------------------------------------------------------------------+
#include <Trade/Trade.mqh>

// Créer un objet pour la gestion des transactions
CTrade trade;

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
    // Récupérer le nombre total de symboles dans le Market Watch
    int totalSymbols = SymbolsTotal(true);

    // Vérifier si le nombre de symboles est supérieur à zéro
    if (totalSymbols <= 0)
    {
        Print("Aucun symbole trouvé dans le Market Watch.");
        return;
    }

    // Parcourir tous les symboles dans le Market Watch
    for (int i = 0; i < totalSymbols; i++)
    {
        // Récupérer le nom du symbole
        string symbol = SymbolName(i, true);

        // Vérifier si le symbole est valide
        if (symbol == "" || !SymbolSelect(symbol, true))
        {
            Print("Impossible de sélectionner le symbole: ", symbol);
            continue;
        }

        // Vérifier que le marché est ouvert pour le symbole
        if (SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL)
        {
            Print("Le symbole ", symbol, " n'est pas disponible pour le trading.");
            continue;
        }

        // Ouvrir une position d'achat de 0.01 lot
        double lotSize = 0.01;
        double slippage = 10 * SymbolInfoDouble(symbol, SYMBOL_POINT);

        // Envoyer l'ordre d'achat
        if (trade.Buy(lotSize, symbol, slippage, 0, 0, "Achat automatique"))
        {
            Print("Ordre d'achat exécuté avec succès pour: ", symbol);
        }
        else
        {
            Print("Erreur lors de l'exécution de l'ordre pour: ", symbol, ". Code d'erreur: ", GetLastError());
        }
    }

    Print("Script terminé.");
}
