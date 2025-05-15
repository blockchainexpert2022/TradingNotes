//+------------------------------------------------------------------+
//|                                              FVGMarker_MTF.mq5 |
//|                                  Copyright 2024, VotreNomOuPseudo |
//|                                              https://www.example.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, VotreNomOuPseudo"
#property link      "https://www.example.com"
#property version   "1.12" // Version incremented for 50% line
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

// --- Paramètres d'entrée
input group "Configuration FVG"
input ENUM_TIMEFRAMES FVGTimeframe = PERIOD_D1;     // Unité de temps pour la détection des FVG
input color BullishFVGColor = clrDodgerBlue;        // Couleur pour les FVG haussiers
input color BearishFVGColor = clrTomato;           // Couleur pour les FVG baissiers
input bool ShowBullishFVG = true;                  // Afficher les FVG Haussiers
input bool ShowBearishFVG = true;                 // Afficher les FVG Baissiers
input bool FillFVGRectangles = true;              // Remplir les rectangles FVG

input group "Niveau 50% FVG"
input bool ShowFVG50pct = true;                 // Afficher la ligne des 50% du FVG
input color FVG50pctColor = clrYellow;          // Couleur pour la ligne des 50%
input ENUM_LINE_STYLE FVG50pctStyle = STYLE_DOT; // Style de la ligne des 50%
input int FVG50pctWidth = 1;                    // Épaisseur de la ligne des 50%

input group "Filtres et Extension"
input int MinFVGHeightPips = 0;                    // Hauteur minimale du FVG en PIPS (0 = pas de filtre)
input bool ExtendFVG = true;                      // Étendre le FVG
input int ExtensionBarsHTF = 50;                 // Nombre de barres (de FVGTimeframe) pour étendre le FVG

input group "Performance et Identifiants"
input int MaxHTFBarsToScan = 1000;                // Barres max de FVGTimeframe à analyser (0 = toutes)
input string RectanglePrefix = "FVG_";             // Préfixe pour les noms d'objets

// Variables globales
double p_point;
string current_obj_prefix; // Préfixe dynamique basé sur FVGTimeframe

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(Digits() == 3 || Digits() == 5)
      p_point = _Point * 10;
   else
      p_point = _Point;

   current_obj_prefix = RectanglePrefix + EnumToString(FVGTimeframe) + "_";
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                     |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // Supprime tous les objets créés par cette instance (FVG et lignes 50%)
   ObjectsDeleteAll(0, current_obj_prefix);
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
   datetime time_htf[];
   double open_htf[];
   double high_htf[];
   double low_htf[];
   double close_htf[];

   int bars_to_request = MaxHTFBarsToScan > 0 ? MaxHTFBarsToScan + 5 : 2000;
   if (MaxHTFBarsToScan == 0) bars_to_request = 2000;

   int copied_time = CopyTime(_Symbol, FVGTimeframe, 0, bars_to_request, time_htf);
   if(copied_time <= 0) return(0);

   int htf_bars_available = ArraySize(time_htf);
   if(htf_bars_available < 3) return(0);

   if(CopyOpen(_Symbol, FVGTimeframe, 0, htf_bars_available, open_htf) != htf_bars_available ||
      CopyHigh(_Symbol, FVGTimeframe, 0, htf_bars_available, high_htf) != htf_bars_available ||
      CopyLow(_Symbol, FVGTimeframe, 0, htf_bars_available, low_htf) != htf_bars_available ||
      CopyClose(_Symbol, FVGTimeframe, 0, htf_bars_available, close_htf) != htf_bars_available)
     {
      return(0);
     }

   static datetime last_htf_bar_time_processed = 0;
   bool force_redraw_all = false;

   if (prev_calculated == 0 || rates_total != prev_calculated)
     {
      force_redraw_all = true;
     }
   if (htf_bars_available > 0 && time_htf[0] != last_htf_bar_time_processed)
     {
      force_redraw_all = true;
      last_htf_bar_time_processed = time_htf[0];
     }

   if (force_redraw_all)
     {
      ObjectsDeleteAll(0, current_obj_prefix); // Supprime FVG et lignes 50% associées
     }

   int start_idx = 0;
   int loop_end_idx = htf_bars_available - 3;

   if (MaxHTFBarsToScan > 0)
     {
      int max_i_due_to_scan_limit = MaxHTFBarsToScan - 3;
      loop_end_idx = MathMin(loop_end_idx, max_i_due_to_scan_limit);
     }

   for(int i = start_idx; i <= loop_end_idx; i++)
     {
      if (ShowBullishFVG && low_htf[i] > high_htf[i+2])
        {
         double fvg_top_price = low_htf[i];
         double fvg_bottom_price = high_htf[i+2];
         double fvg_height = (fvg_top_price - fvg_bottom_price) / p_point;

         if (MinFVGHeightPips == 0 || fvg_height >= MinFVGHeightPips)
           {
            DrawFVG("Bullish", time_htf[i+2], fvg_bottom_price, time_htf[i], fvg_top_price, BullishFVGColor, i);
           }
        }

      if (ShowBearishFVG && high_htf[i] < low_htf[i+2])
        {
         double fvg_top_price = low_htf[i+2];
         double fvg_bottom_price = high_htf[i];
         double fvg_height = (fvg_top_price - fvg_bottom_price) / p_point;

         if (MinFVGHeightPips == 0 || fvg_height >= MinFVGHeightPips)
           {
            DrawFVG("Bearish", time_htf[i+2], fvg_bottom_price, time_htf[i], fvg_top_price, BearishFVGColor, i);
           }
        }
     }
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| Function to draw FVG rectangles and 50% line                   |
//+------------------------------------------------------------------+
void DrawFVG(string type, datetime anchor_time1_htf, double price_level1, datetime formation_candle_open_time_htf, double price_level2, color fvg_color, int bar_idx_htf)
  {
   // Nom de base pour le FVG (rectangle)
   string obj_name_base = current_obj_prefix + type + "_" + TimeToString(anchor_time1_htf, TIME_DATE|TIME_MINUTES|TIME_SECONDS) + "_" + IntegerToString(bar_idx_htf);
   string obj_name_rect = obj_name_base + "_Rect";
   string obj_name_50pct = obj_name_base + "_50pct";


   long bar_duration_htf_seconds = (long)PeriodSeconds(FVGTimeframe);
   if (bar_duration_htf_seconds == 0)
     {
      bar_duration_htf_seconds = (long)PeriodSeconds(Period());
      if(bar_duration_htf_seconds == 0) bar_duration_htf_seconds = 3600;
     }

   datetime fvg_base_end_time = formation_candle_open_time_htf + bar_duration_htf_seconds;
   datetime final_render_time2;

   if (ExtendFVG && ExtensionBarsHTF > 0)
     {
      long total_extension_seconds = bar_duration_htf_seconds * ExtensionBarsHTF;
      final_render_time2 = fvg_base_end_time + total_extension_seconds;
     }
   else
     {
      final_render_time2 = fvg_base_end_time;
     }

   // --- Suppression des anciens objets (rectangle et ligne 50%) ---
   if(ObjectFind(0, obj_name_rect) != -1)
     {
      ObjectDelete(0, obj_name_rect);
     }
   if(ObjectFind(0, obj_name_50pct) != -1)
     {
      ObjectDelete(0, obj_name_50pct);
     }

   // --- Dessiner le rectangle FVG ---
   if(!ObjectCreate(0, obj_name_rect, OBJ_RECTANGLE, 0, anchor_time1_htf, price_level1, final_render_time2, price_level2))
     {
      // Print("Erreur création FVG Rectangle (", obj_name_rect, "): ", GetLastError());
      return; // Si le rectangle ne peut être créé, ne pas dessiner la ligne 50% non plus
     }

   ObjectSetInteger(0, obj_name_rect, OBJPROP_COLOR, fvg_color);
   ObjectSetInteger(0, obj_name_rect, OBJPROP_STYLE, STYLE_SOLID); // Style de la bordure du rectangle
   ObjectSetInteger(0, obj_name_rect, OBJPROP_BACK, true);
   ObjectSetInteger(0, obj_name_rect, OBJPROP_FILL, FillFVGRectangles);

   string description = StringFormat("%s FVG HTF (%s) (%.*f - %.*f)",
                                    type, EnumToString(FVGTimeframe),
                                    _Digits, price_level1, _Digits, price_level2);
   if (MinFVGHeightPips > 0)
     {
      description = StringFormat("%s (%.1f Pips) FVG HTF (%s) (%.*f - %.*f)",
                                 type, (MathAbs(price_level1 - price_level2) / p_point),
                                 EnumToString(FVGTimeframe),
                                 _Digits, price_level1, _Digits, price_level2);
     }
   ObjectSetString(0, obj_name_rect, OBJPROP_TEXT, description);
   ObjectSetString(0, obj_name_rect, OBJPROP_TOOLTIP, description);

   // --- Dessiner la ligne des 50% si activée ---
   if(ShowFVG50pct)
     {
      double mid_price = (price_level1 + price_level2) / 2.0;

      if(ObjectCreate(0, obj_name_50pct, OBJ_TREND, 0, anchor_time1_htf, mid_price, final_render_time2, mid_price))
        {
         ObjectSetInteger(0, obj_name_50pct, OBJPROP_COLOR, FVG50pctColor);
         ObjectSetInteger(0, obj_name_50pct, OBJPROP_STYLE, FVG50pctStyle);
         ObjectSetInteger(0, obj_name_50pct, OBJPROP_WIDTH, FVG50pctWidth);
         ObjectSetInteger(0, obj_name_50pct, OBJPROP_BACK, false); // Mettre la ligne 50% au premier plan par rapport au rectangle
         ObjectSetInteger(0, obj_name_50pct, OBJPROP_RAY_RIGHT, false); // Ne pas étendre la ligne à l'infini
         ObjectSetString(0, obj_name_50pct, OBJPROP_TOOLTIP, StringFormat("50%% FVG (%s) @ %.*f", type, _Digits, mid_price));
        }
      else
        {
         // Print("Erreur création Ligne 50% FVG (", obj_name_50pct, "): ", GetLastError());
        }
     }
  }
//+------------------------------------------------------------------+
