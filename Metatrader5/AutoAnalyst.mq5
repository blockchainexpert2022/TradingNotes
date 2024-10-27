//+------------------------------------------------------------------+
//|                                      HighLowLinesEA.mq5          |
//|                            Exemple d'Expert Advisor               |
//+------------------------------------------------------------------+
input int window = 9;             // Taille de la fenêtre pour la détection de points extrêmes
input double threshold = 0.01;    // Seuil de variation minimale (en %)

// Variables pour stocker les plus hauts et bas locaux
double HighBuffer[];
double LowBuffer[];

// Variables globales pour les données de prix
double high[];
double low[];
datetime time[];

// Fonction d'initialisation
int OnInit()
{
    ArraySetAsSeries(HighBuffer, true);
    ArraySetAsSeries(LowBuffer, true);
    return(INIT_SUCCEEDED);
}

// Fonction pour récupérer les données de prix limitées aux deux derniers jours
int GetPriceData()
{
    int rates_total = Bars(Symbol(), Period());  // Nombre total de barres
    datetime start_time = TimeCurrent() - 2 * 86400;  // Limite des deux derniers jours

    // Copie les données de prix dans les tableaux high, low, et time à partir de start_time
    ArrayResize(high, rates_total);
    ArrayResize(low, rates_total);
    ArrayResize(time, rates_total);

    int copied = CopyHigh(Symbol(), Period(), start_time, rates_total, high);
    CopyLow(Symbol(), Period(), start_time, rates_total, low);
    CopyTime(Symbol(), Period(), start_time, rates_total, time);

    return copied;  // Nombre de barres copiées
}

// Fonction principale pour détecter les points extrêmes
void DetectHighsLows(const int rates_total)
{
    ArrayResize(HighBuffer, rates_total);
    ArrayResize(LowBuffer, rates_total);

    for (int i = window; i < rates_total - window; i++)
    {
        HighBuffer[i] = 0;
        LowBuffer[i] = 0;

        // Détection des sommets locaux
        if (high[i] > high[i - 1] && high[i] > high[i + 1])
        {
            double diffHigh = MathAbs(high[i] - MathMin(high[i - 1], high[i + 1])) / high[i];
            if (diffHigh >= threshold)
                HighBuffer[i] = high[i];
        }

        // Détection des creux locaux
        if (low[i] < low[i - 1] && low[i] < low[i + 1])
        {
            double diffLow = MathAbs(MathMax(low[i - 1], low[i + 1]) - low[i]) / low[i];
            if (diffLow >= threshold)
                LowBuffer[i] = low[i];
        }
    }
}

// Fonction pour tracer les lignes horizontales
void DrawLines(int rates_total)
{
    // Effacer toutes les anciennes lignes pour éviter les doublons
    ObjectsDeleteAll(0, -1);

    for (int i = window; i < rates_total - window; i++)
    {
        // Tracer une ligne pour chaque sommet local détecté
        if (HighBuffer[i] > 0)
        {
            string highLineName = "HighLine_" + IntegerToString(i);
            ObjectCreate(0, highLineName, OBJ_HLINE, 0, time[i], HighBuffer[i]);
            ObjectSetInteger(0, highLineName, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, highLineName, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, highLineName, OBJPROP_WIDTH, 1);
        }

        // Tracer une ligne pour chaque creux local détecté
        if (LowBuffer[i] > 0)
        {
            string lowLineName = "LowLine_" + IntegerToString(i);
            ObjectCreate(0, lowLineName, OBJ_HLINE, 0, time[i], LowBuffer[i]);
            ObjectSetInteger(0, lowLineName, OBJPROP_COLOR, clrBlue);
            ObjectSetInteger(0, lowLineName, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, lowLineName, OBJPROP_WIDTH, 1);
        }
    }
}

// Fonction principale de calcul de l'EA
void OnStart()
{
    int rates_total = GetPriceData();
    Print(rates_total);
    DetectHighsLows(rates_total);
    DrawLines(rates_total);
}
