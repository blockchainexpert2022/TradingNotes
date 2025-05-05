//+------------------------------------------------------------------+
//|                                ICT_FVG_Scanner_EA_LongShort.mq5 |
//|                        Copyright 2025, InvestDataSystems Reuniware         |
//|                                              https://ntic974.blogspot.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, Your Name/Company"
#property link      "https://www.example.com"
#property version   "1.10" // Version incremented
#property description "Scans for ICT-style Short & Long Setups: Liquidity Sweep -> MSS -> FVG -> Retracement Entry"

#include <Trade\Trade.mqh> // Include CTrade library

//--- Enumeration for Trade Direction
enum ENUM_TRADE_DIRECTION
{
   ShortOnly,
   LongOnly,
   Both
};

//--- Input Parameters
input group               "Trade Settings"
input ENUM_TRADE_DIRECTION TradeDirection       = Both;          // Trade Direction to Scan For
input double              LotSize               = 0.01;        // Lot Size
input int                 StopLossPips          = 20;          // Stop Loss in Pips (relative to High/Low/FVG)
input int                 TakeProfitPips        = 60;          // Take Profit in Pips
input int                 MaxSpreadPoints       = 30;          // Maximum Allowed Spread in Points (0 = disabled)
input ulong               MagicNumber           = 12346;       // EA Magic Number (changed slightly)

input group               "Pattern Detection Settings"
input int                 LookbackBarsLiquidity = 100;         // How many bars back to look for the initial high/low liquidity sweep
input int                 SwingLookback         = 5;           // Bars left/right to define a swing high/low for MSS
input int                 DisplacementMinPoints = 150;         // Minimum points move from High/Low to MSS point (proxy for displacement)
input double              FVG_MinPips           = 1.0;         // Minimum FVG size in Pips to consider valid
input bool                EnterOnFVGRetrace     = true;        // Enter when price touches FVG
input bool                AllowMultipleTrades   = false;       // Allow more than one trade open (per direction if Both)?

//--- Global Variables
CTrade trade;
double pointValue;
int    digitsValue;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(Symbol());

   pointValue = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   digitsValue = (int)SymbolInfoInteger(Symbol(), SYMBOL_DIGITS);

   Print("ICT FVG Long/Short Scanner EA Initialized");
   Print("Symbol: ", Symbol());
   Print("Timeframe: ", EnumToString(Period()));
   Print("Trade Direction: ", EnumToString(TradeDirection));
   Print("Lot Size: ", LotSize);
   Print("SL Pips: ", StopLossPips);
   Print("TP Pips: ", TakeProfitPips);
   Print("Magic Number: ", MagicNumber);
   Print("---");

   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   static datetime lastBarTime = 0;
   datetime currentBarTime = (datetime)SeriesInfoInteger(Symbol(), Period(), SERIES_LASTBAR_DATE);

   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;

      //--- Check based on selected direction
      if(TradeDirection == ShortOnly || TradeDirection == Both)
      {
         CheckForShortSetup();
      }
      if(TradeDirection == LongOnly || TradeDirection == Both)
      {
         CheckForLongSetup();
      }
   }
}

//+------------------------------------------------------------------+
//| Check for the SHORT Setup                                        |
//+------------------------------------------------------------------+
void CheckForShortSetup()
{
    // Check if allowed to trade (prevents multiple shorts if AllowMultipleTrades is false)
   if(!AllowMultipleTrades && PositionsTotal() > 0)
   {
      bool positionFound = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
         {
            positionFound = true;
            break;
         }
      }
      if(positionFound) return;
   }

   MqlRates rates[];
   int bars = LookbackBarsLiquidity + 50;
   if(CopyRates(Symbol(), Period(), 0, bars, rates) < bars) return;
   ArraySetAsSeries(rates, true);

   int    highIndex = -1;
   double highPrice = 0;
   int    swingLowIndex = -1;
   double swingLowPrice = 0;
   int    mssIndex = -1;
   int    fvgIndex = -1;
   double fvgHigh = 0;
   double fvgLow = 0;
   bool   fvgFound = false;

   // STEP 1: Find High
   for(int i = 1; i < LookbackBarsLiquidity; i++) { if(rates[i].high > highPrice) { highPrice = rates[i].high; highIndex = i; } }
   if(highIndex <= SwingLookback + 1) return;

   // STEP 2: Find recent relevant Swing Low *before* the high
   for(int i = highIndex + 1; i < LookbackBarsLiquidity - SwingLookback; i++) { if(IsSwingLow(rates, i, SwingLookback)) { swingLowIndex = i; swingLowPrice = rates[i].low; break; } }
   if(swingLowIndex == -1) return;

   // STEP 3: Check for MSS Bearish (Break below swingLowPrice) and Displacement
   for(int i = highIndex - 1; i >= 1; i--) { if(rates[i].low < swingLowPrice) { mssIndex = i; if((highPrice - rates[mssIndex].low) / pointValue < DisplacementMinPoints) return; break; } }
   if(mssIndex == -1) return;

   // STEP 4: Find Bearish FVG between high and MSS
   for(int i = mssIndex; i > highIndex; i--) { if(i + 1 < bars && i - 1 >= 0) { if(rates[i-1].low > rates[i+1].high) { double gapPips = (rates[i-1].low - rates[i+1].high) / (pointValue * pow(10, digitsValue - 1)); if (gapPips >= FVG_MinPips) { fvgIndex = i; fvgHigh = rates[i-1].low; fvgLow = rates[i+1].high; fvgFound = true; break; } } } }
   if(!fvgFound) return;

   // STEP 5: Check Retracement into FVG
   if (fvgIndex > 0 && EnterOnFVGRetrace) {
       bool retraced = false;
       if (rates[0].high >= fvgLow && rates[0].high <= fvgHigh) retraced = true;
       if (!retraced && rates[1].high >= fvgLow && rates[1].high <= fvgHigh) retraced = true;

       if(retraced) {
         PrintFormat("SHORT SETUP: Retracement into Bearish FVG (%.5f - %.5f) detected.", fvgLow, fvgHigh);
         // STEP 6: Entry
         if(CheckTradingConditions()) {
            double entryPrice = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
            double stopLossPrice = highPrice + (StopLossPips * pointValue * pow(10, digitsValue - 1));
            double takeProfitPrice = entryPrice - (TakeProfitPips * pointValue * pow(10, digitsValue - 1));
            PrintFormat("Attempting SELL Order: Entry ~%.5f, SL %.5f, TP %.5f", entryPrice, stopLossPrice, takeProfitPrice);
            if(!trade.Sell(LotSize, Symbol(), entryPrice, stopLossPrice, takeProfitPrice, "ICT FVG Short")) { Print("Sell Order failed: ", GetLastError(), " - ", trade.ResultComment()); } else { Print("Sell Order successful: ", trade.ResultDeal()); }
         }
       }
   }
}

//+------------------------------------------------------------------+
//| Check for the LONG Setup                                         |
//+------------------------------------------------------------------+
void CheckForLongSetup()
{
    // Check if allowed to trade (prevents multiple longs if AllowMultipleTrades is false)
   if(!AllowMultipleTrades && PositionsTotal() > 0)
   {
      bool positionFound = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
         {
            positionFound = true;
            break;
         }
      }
      if(positionFound) return;
   }


   MqlRates rates[];
   int bars = LookbackBarsLiquidity + 50;
   if(CopyRates(Symbol(), Period(), 0, bars, rates) < bars) return;
   ArraySetAsSeries(rates, true);

   int    lowIndex = -1;
   double lowPrice = 9999999; // Initialize high for finding minimum
   int    swingHighIndex = -1;
   double swingHighPrice = 0;
   int    mssIndex = -1;
   int    fvgIndex = -1;
   double fvgHigh = 0; // Top of Bullish FVG
   double fvgLow = 0;  // Bottom of Bullish FVG
   bool   fvgFound = false;

   // STEP 1: Find Low within the lookback period
   for(int i = 1; i < LookbackBarsLiquidity; i++)
   {
      if(rates[i].low < lowPrice)
      {
         lowPrice = rates[i].low;
         lowIndex = i;
      }
   }
   if(lowIndex <= SwingLookback + 1) return; // Ensure low isn't too close

   // STEP 2: Find recent relevant Swing High *before* the low
   for(int i = lowIndex + 1; i < LookbackBarsLiquidity - SwingLookback; i++) // Search backwards from *before* the low
   {
      if(IsSwingHigh(rates, i, SwingLookback))
      {
         swingHighIndex = i;
         swingHighPrice = rates[i].high;
         break; // Found the *most recent* one before the low
      }
   }
    if(swingHighIndex == -1) return; // Relevant swing high not found

   // STEP 3: Check for MSS Bullish (Break above swingHighPrice) and Displacement
   for(int i = lowIndex - 1; i >= 1; i--) // Search forward from *after* the low
   {
      if(rates[i].high > swingHighPrice)
      {
         mssIndex = i;
         // Check for upward displacement
         if((rates[mssIndex].high - lowPrice) / pointValue < DisplacementMinPoints)
         {
             return; // Displacement insufficient
         }
         break; // Found the MSS
      }
   }
   if(mssIndex == -1) return; // MSS not found

   // STEP 4: Find Bullish FVG between low and the MSS bar
   // Search backwards from the bar *before* MSS up to the bar *after* the low
   for(int i = mssIndex; i > lowIndex; i--)
   {
      if(i + 1 < bars && i - 1 >= 0) // Bounds check
      {
         // Check for Bullish FVG (Gap between High[i-1] and Low[i+1])
         if(rates[i-1].high < rates[i+1].low) // Potential Bullish FVG
         {
            double gapPips = (rates[i+1].low - rates[i-1].high) / (pointValue * pow(10, digitsValue - 1));
            if(gapPips >= FVG_MinPips)
            {
               fvgIndex = i;
               fvgHigh = rates[i+1].low;  // Top of the gap (higher price)
               fvgLow = rates[i-1].high; // Bottom of the gap (lower price)
               fvgFound = true;
               break; // Found the most recent valid FVG
            }
         }
      }
   }
   if(!fvgFound) return; // FVG not found

   // STEP 5: Check Retracement into Bullish FVG
   if (fvgIndex > 0 && EnterOnFVGRetrace)
   {
       bool retraced = false;
       // Check if current forming bar [0] or last closed bar [1] has hit the FVG from above
       if (rates[0].low <= fvgHigh && rates[0].low >= fvgLow) retraced = true;
       if (!retraced && rates[1].low <= fvgHigh && rates[1].low >= fvgLow) retraced = true;

       if(retraced)
       {
         PrintFormat("LONG SETUP: Retracement into Bullish FVG (%.5f - %.5f) detected.", fvgLow, fvgHigh);
         // STEP 6: Entry Conditions Check & Place Order
         if(CheckTradingConditions())
         {
            double entryPrice = SymbolInfoDouble(Symbol(), SYMBOL_BID); // Use Bid for Buy order
            double stopLossPrice = lowPrice - (StopLossPips * pointValue * pow(10, digitsValue - 1)); // SL below the *initial* low
            // Alternative SL: double stopLossPrice = fvgLow - (StopLossPips * pointValue * pow(10, digitsValue-1)); // SL below FVG Low + buffer
            double takeProfitPrice = entryPrice + (TakeProfitPips * pointValue * pow(10, digitsValue - 1));

            PrintFormat("Attempting BUY Order: Entry ~%.5f, SL %.5f, TP %.5f", entryPrice, stopLossPrice, takeProfitPrice);
            if(!trade.Buy(LotSize, Symbol(), entryPrice, stopLossPrice, takeProfitPrice, "ICT FVG Long Entry"))
            {
               Print("Buy Order failed: ", GetLastError(), " - ", trade.ResultComment());
            }
            else
            {
               Print("Buy Order successful: ", trade.ResultDeal());
            }
         }
       }
   }
}


//+------------------------------------------------------------------+
//| Helper: Identify Swing Low                                       |
//+------------------------------------------------------------------+
bool IsSwingLow(const MqlRates &rates[], int index, int lookback)
{
   if(index < lookback || index >= ArraySize(rates) - lookback) return false;
   double currentLow = rates[index].low;
   for(int i = 1; i <= lookback; i++) { if(rates[index + i].low <= currentLow) return false; }
   for(int i = 1; i <= lookback; i++) { if(rates[index - i].low <= currentLow) return false; }
   return true;
}

//+------------------------------------------------------------------+
//| Helper: Identify Swing High                                      |
//+------------------------------------------------------------------+
bool IsSwingHigh(const MqlRates &rates[], int index, int lookback)
{
   if(index < lookback || index >= ArraySize(rates) - lookback) return false;
   double currentHigh = rates[index].high;
   // Check bars to the left (older bars)
   for(int i = 1; i <= lookback; i++) { if(rates[index + i].high >= currentHigh) return false; } // Use >= to ensure it's the *highest*
   // Check bars to the right (newer bars)
   for(int i = 1; i <= lookback; i++) { if(rates[index - i].high >= currentHigh) return false; } // Use >=
   return true; // It's a swing high
}

//+------------------------------------------------------------------+
//| Check Trading Conditions (Spread etc)                            |
//+------------------------------------------------------------------+
bool CheckTradingConditions()
{
    //--- Check Spread
   if(MaxSpreadPoints > 0) { double spread = SymbolInfoInteger(Symbol(), SYMBOL_SPREAD); if(spread > MaxSpreadPoints) { return false; } }
   //--- Check if trade is allowed
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) { Print("Automated trading is disabled in Terminal settings."); return false; }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) { Print("Automated trading is disabled for this EA in settings."); return false; }
   return true;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("ICT FVG Long/Short Scanner EA Deinitialized. Reason: ", reason);
}
//+------------------------------------------------------------------+
