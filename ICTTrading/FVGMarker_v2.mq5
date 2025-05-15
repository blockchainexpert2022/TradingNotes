//+------------------------------------------------------------------+
//|                                                 FVGMarker_v2.mq5 |
//|                                  Copyright 2024, IDSYS/Reuniware |
//|                                              https://ntic974.blogspot.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, IDSYS/RNW"
#property link      "https://ntic974.blogspot.com"
#property version   "1.02" // Version incremented
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

// --- Paramètres d'entrée
input group "Affichage des FVG"
input color BullishFVGColor = clrDodgerBlue;     // Couleur pour les FVG haussiers
input color BearishFVGColor = clrTomato;        // Couleur pour les FVG baissiers
input bool ShowBullishFVG = true;               // Afficher les FVG Haussiers
input bool ShowBearishFVG = true;              // Afficher les FVG Baissiers
input bool FillFVGRectangles = true;           // Remplir les rectangles FVG (sinon, seulement les bordures)

input group "Filtres et Extension"
input int MinFVGHeightPips = 0;                 // Hauteur minimale du FVG en PIPS pour être affiché (0 = pas de filtre)
input bool ExtendFVG = true;                   // Étendre le FVG
input int ExtensionBars = 50;                  // Nombre de barres pour étendre le FVG s'il est activé

input group "Performance"
input int MaxBarsToScan = 1000;                 // Barres max à analyser (0 = toutes, peut impacter la performance)
input string RectanglePrefix = "FVG_";          // Préfixe pour les noms d'objets rectangle

// Variables globales pour les pips
double p_point;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Déterminer la valeur d'un point pour le calcul des pips
   if(Digits() == 3 || Digits() == 5) // Pour les courtiers à 3/5 décimales
      p_point = _Point * 10;
   else // Pour les courtiers à 2/4 décimales
      p_point = _Point;

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                     |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, RectanglePrefix);
  }

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 3)
      return(0);

   int first_bar_to_calculate;

   // Logique pour déterminer la barre de départ et gérer le nettoyage
   if(prev_calculated == 0 || prev_calculated < 3 || rates_total != prev_calculated)
     {
      ObjectsDeleteAll(0, RectanglePrefix); // Nettoyage complet avant de redessiner
      if (MaxBarsToScan > 0 && MaxBarsToScan < rates_total)
        {
         first_bar_to_calculate = rates_total - MathMin(rates_total - 2, MaxBarsToScan);
        }
      else
        {
         first_bar_to_calculate = 0; // Commencer du début si MaxBarsToScan = 0
        }
     }
   else // prev_calculated == rates_total (nouveau tick, pas de nouvelle barre)
     {
      // Si ExtendFVG est vrai, nous devons potentiellement mettre à jour les extrémités des rectangles
      // existants. Le plus simple est de recalculer la dernière portion.
      // Ou, si les objets sont bien nommés et que leur heure de fin est dynamique,
      // il faut juste les mettre à jour.
      // Pour cet exemple, un recalcul limité sur les dernières barres à chaque tick si ExtendFVG.
      if (ExtendFVG)
        {
         // Recalculer une petite fenêtre pour mettre à jour les extensions
         int recalc_window = MathMax(3, ExtensionBars + 5); // Fenêtre de recalcul
         first_bar_to_calculate = MathMax(0, rates_total - recalc_window);
        }
      else
        {
         return(rates_total); // Pas de nouvelles barres, pas d'extension, rien à faire.
        }
     }
   if(first_bar_to_calculate < 0) first_bar_to_calculate = 0;


   // Boucle de la barre la plus ancienne à calculer vers la plus récente
   // L'index i est la 3ème bougie du pattern FVG. La bougie 1 est i+2, la bougie 2 est i+1.
   // Nous voulons donc que i+2 soit >= first_bar_to_calculate.
   // Donc i >= first_bar_to_calculate - 2.
   // Et i doit aller jusqu'à rates_total - 3 (pour que i, i+1, i+2 soient des index valides).
   for(int i = MathMax(0, first_bar_to_calculate -2) ; i <= rates_total - 3; i++)
     {
      // --- Identification d'un FVG Haussier (Bullish FVG) ---
      // Bougie 1: high[i+2], Bougie 2: high[i+1], low[i+1], Bougie 3: low[i]
      // Le vide est entre high[i+2] (haut de la bougie 1) et low[i] (bas de la bougie 3)
      if (ShowBullishFVG && low[i] > high[i+2])
        {
         double fvg_top_price = low[i];
         double fvg_bottom_price = high[i+2];
         double fvg_height = (fvg_top_price - fvg_bottom_price) / p_point; // Hauteur en pips

         if (MinFVGHeightPips == 0 || fvg_height >= MinFVGHeightPips)
           {
            // S'assurer que la bougie du milieu (i+1) ne comble pas le gap avec ses mèches
            // Cette condition (low[i] > high[i+2]) l'implique déjà pour la formation.
            DrawFVG("Bullish", time[i+2], fvg_bottom_price, time[i], fvg_top_price, BullishFVGColor, i);
           }
        }

      // --- Identification d'un FVG Baissier (Bearish FVG) ---
      // Bougie 1: low[i+2], Bougie 2: high[i+1], low[i+1], Bougie 3: high[i]
      // Le vide est entre low[i+2] (bas de la bougie 1) et high[i] (haut de la bougie 3)
      if (ShowBearishFVG && high[i] < low[i+2])
        {
         double fvg_top_price = low[i+2];
         double fvg_bottom_price = high[i];
         double fvg_height = (fvg_top_price - fvg_bottom_price) / p_point; // Hauteur en pips

         if (MinFVGHeightPips == 0 || fvg_height >= MinFVGHeightPips)
           {
            DrawFVG("Bearish", time[i+2], fvg_bottom_price, time[i], fvg_top_price, BearishFVGColor, i);
           }
        }
     }
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| Function to draw FVG rectangles                                  |
//+------------------------------------------------------------------+
void DrawFVG(string type, datetime anchor_time1, double price_level1, datetime formation_end_time, double price_level2, color fvg_color, int bar_idx_for_name_part)
  {
   // Nom unique basé sur l'heure de la première bougie du FVG et son type
   string obj_name = RectanglePrefix + type + "_" + TimeToString(anchor_time1, TIME_DATE|TIME_MINUTES|TIME_SECONDS) + "_" + IntegerToString(bar_idx_for_name_part);

   datetime final_render_time2 = formation_end_time; // Par défaut, le FVG s'arrête à la bougie 3

   if (ExtendFVG && ExtensionBars > 0)
     {
      // Étendre à partir de la fin de la formation du FVG pour un nombre de barres donné
      final_render_time2 = formation_end_time + PeriodSeconds() * ExtensionBars;
     }

   // Supprimer l'ancien rectangle s'il existe pour le redessiner (utile pour l'extension ou changement de paramètres)
   if(ObjectFind(0, obj_name) != -1)
     {
      ObjectDelete(0, obj_name);
     }

   if(!ObjectCreate(0, obj_name, OBJ_RECTANGLE, 0, anchor_time1, price_level1, final_render_time2, price_level2))
     {
      // Print("Erreur création FVG (", obj_name, "): ", GetLastError());
      return;
     }

   ObjectSetInteger(0, obj_name, OBJPROP_COLOR, fvg_color);
   ObjectSetInteger(0, obj_name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, obj_name, OBJPROP_BACK, true);
   ObjectSetInteger(0, obj_name, OBJPROP_FILL, FillFVGRectangles); // Utilise le paramètre d'entrée

   string description = StringFormat("%s FVG (%.*f - %.*f)", type, _Digits, price_level1, _Digits, price_level2);
   if (MinFVGHeightPips > 0)
     {
      description = StringFormat("%s (%.1f Pips) FVG (%.*f - %.*f)", type, (MathAbs(price_level1 - price_level2) / p_point), _Digits, price_level1, _Digits, price_level2);
     }
   ObjectSetString(0, obj_name, OBJPROP_TEXT, description); // Utile pour le débogage via la liste d'objets
   ObjectSetString(0, obj_name, OBJPROP_TOOLTIP, description); // Tooltip amélioré
  }
//+------------------------------------------------------------------+


// Comment utiliser ce script :
// Ouvrez MetaEditor dans MetaTrader 5 (F4 ou via le menu Outils).
// Dans MetaEditor, créez un nouveau fichier (Fichier -> Nouveau).
// Choisissez "Indicateur personnalisé" et cliquez sur "Suivant".
// Donnez un nom à votre indicateur (par exemple, FVGIdentifier) et cliquez sur "Suivant" puis "Terminer".
// Copiez et collez le code MQL5 ci-dessus dans la fenêtre de l'éditeur, en remplaçant le contenu par défaut.
// Modifiez "VotreNomOuPseudo" et "https://www.example.com" avec vos informations si vous le souhaitez.
// Cliquez sur "Compiler" (ou F7). S'il n'y a pas d'erreurs, l'indicateur sera compilé.
// Retournez à MetaTrader 5.
// Dans la fenêtre "Navigateur", trouvez votre indicateur sous la section "Indicateurs".
// Faites glisser l'indicateur sur le graphique de votre choix.
// Vous pourrez ajuster les paramètres d'entrée (couleurs, afficher/masquer, etc.) avant de cliquer sur "OK".
