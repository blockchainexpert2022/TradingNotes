//+------------------------------------------------------------------+
//|                          ICT_Confluence_Scanner_EA.mq5           |
//|                        Copyright 2025, InvestDataSystems / Reuniware                 |
//|                        Corrected Version (v1.11)                 |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, InvestDataSystems / Reuniware"
#property link      ""
#property version   "1.11" // Version incremented
#property description "Attempts to scan for ICT Confluence Setups (Short & Long - Experimental)"

#include <Trade\Trade.mqh>
#include <MovingAverages.mqh> // For HTF MA Bias

//--- Enums
enum ENUM_TRADE_DIRECTION
{
   ShortOnly,
   LongOnly,
   Both
};

enum ENUM_HTF_BIAS_MODE
{
   Manual_Input, // Use the ManualBias input
   MA_Filter     // Use Moving Average Filter
};

//--- Input Parameters
input group               "----- Trade Settings -----"
input ENUM_TRADE_DIRECTION TradeDirection       = Both;          // Trade Direction to Scan For
input double              Lots                  = 0.01;        // Position size
input int                 StopLossPips          = 0;           // Stop Loss in Pips (0 = use structure)
input double              StopLossStructureBufferPips = 3.0;    // Buffer above/below structure for SL
input double              RiskRewardRatio       = 2.0;         // Take Profit based on Risk:Reward
input int                 TakeProfitPips        = 0;           // Take Profit in Pips (Overrides RR if > 0)
input ulong               MagicNumber           = 67890;       // Unique Magic Number
input int                 MaxSpreadPoints       = 50;          // Max allowed spread in points
input bool                AllowMultipleTrades   = false;       // Allow multiple trades in same direction?

input group               "----- HTF Bias Settings -----"
input ENUM_HTF_BIAS_MODE  BiasMode              = MA_Filter;   // How to determine bias
input ENUM_TIMEFRAMES     HTF_Timeframe         = PERIOD_H4;   // Timeframe for Bias Check (if MA_Filter)
input int                 HTF_MA_Period         = 50;          // MA Period for HTF Bias
input ENUM_MA_METHOD      HTF_MA_Method         = MODE_SMA;    // MA Method for HTF Bias
// Manual Bias Setting (Only used if BiasMode = Manual_Input)
input ENUM_TRADE_DIRECTION ManualBias           = Both; // Both=No manual bias, LongOnly=Bullish, ShortOnly=Bearish

input group               "----- Pattern Detection -----"
input ENUM_TIMEFRAMES     EntryTimeframe        = PERIOD_M15;  // Timeframe to run the checks on
input int                 LiquidityLookback     = 2;           // Lookback days for PDH/PDL (1=PDH/L, 2=Day Before etc)
input int                 SwingLookback         = 5;           // Bars for MSS Swing Point identification
input double              DisplacementMinFactor = 1.5;         // Displacement leg must be X times ATR
input int                 DisplacementATRPeriod = 14;          // ATR Period for displacement check
input int                 MinLargeCandlePoints  = 100;         // Displacement leg needs >=1 candle this big (points)
input double              FVG_MinPips           = 1.0;         // Minimum FVG size in pips
input bool                RequireOTE            = true;        // Must retracement be in OTE zone?
input double              OTE_Level_1           = 0.62;        // OTE Zone Start
input double              OTE_Level_2           = 0.79;        // OTE Zone End

input group               "----- Time Filters -----"
input bool                UseKillzoneFilter     = true;        // Enable Killzone Time Filter?
//--- London Killzone (Server Time)
input int                 LOKZ_Start_Hour       = 3;           // London Start Hour
input int                 LOKZ_Start_Min        = 0;
input int                 LOKZ_End_Hour         = 6;           // London End Hour
input int                 LOKZ_End_Min          = 0;
//--- New York Killzone (Server Time)
input int                 NYKZ_Start_Hour       = 8;           // NY Start Hour
input int                 NYKZ_Start_Min        = 0;
input int                 NYKZ_End_Hour         = 11;          // NY End Hour
input int                 NYKZ_End_Min          = 0;


//--- Global Variables
CTrade trade;
double pointValue;
int    digitsValue;
string symbol;
int    htf_ma_handle = INVALID_HANDLE; // Correct type and initialize

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   symbol = Symbol();
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50); // Slippage
   trade.SetTypeFillingBySymbol(symbol);

   pointValue = SymbolInfoDouble(symbol, SYMBOL_POINT);
   digitsValue = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   // Initialize HTF MA Handle if needed
   if(BiasMode == MA_Filter)
   {
      htf_ma_handle = iMA(symbol, HTF_Timeframe, HTF_MA_Period, 0, HTF_MA_Method, PRICE_CLOSE);
      if(htf_ma_handle == INVALID_HANDLE)
      {
         Print("Error creating HTF MA indicator handle - ", GetLastError());
         return(INIT_FAILED);
      }
   }

   Print("ICT Confluence Scanner EA Initialized (EXPERIMENTAL)");
   Print("Symbol: ", symbol);
   Print("Entry Timeframe: ", EnumToString(EntryTimeframe));
   Print("---");

   // Check if EntryTimeframe is valid
   if(EntryTimeframe < PERIOD_M1 || EntryTimeframe > PERIOD_D1)
   {
      Print("Invalid Entry Timeframe selected!");
      return(INIT_FAILED);
   }
    // Check if HTF Timeframe is valid and higher than Entry TF
   if(BiasMode == MA_Filter && HTF_Timeframe <= EntryTimeframe)
   {
        Print("HTF Timeframe must be higher than Entry Timeframe for MA Filter!");
        return(INIT_FAILED);
   }


   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("ICT Confluence Scanner EA Deinitialized. Reason: ", reason);
   if(BiasMode == MA_Filter && htf_ma_handle != INVALID_HANDLE) // Release handle only if valid
       IndicatorRelease(htf_ma_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   static datetime lastBarTime = 0;
   datetime currentBarTime = (datetime)SeriesInfoInteger(symbol, EntryTimeframe, SERIES_LASTBAR_DATE);

   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      CheckForSetups(); // Call the main check function
   }
}

//+------------------------------------------------------------------+
//| Main Check Function                                              |
//+------------------------------------------------------------------+
void CheckForSetups()
{
   //--- Check existing positions (MQL5 Style)
   bool shortPositionExists = false;
   bool longPositionExists = false;
   if(PositionsTotal() > 0)
   {
       for(int i = PositionsTotal() - 1; i >= 0; i--)
       {
           ulong pos_ticket = PositionGetTicket(i);
           if(PositionSelectByTicket(pos_ticket)) // Select position to check properties
           {
                if(PositionGetString(POSITION_SYMBOL) == symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
                {
                    if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL) shortPositionExists = true;
                    if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) longPositionExists = true;
                }
           }
           if(shortPositionExists && longPositionExists) break; // Optimization
       }
   }
   // If multiple trades not allowed, and either exists, return
   if(!AllowMultipleTrades && (shortPositionExists || longPositionExists)) return;


   //--- Check trading conditions (spread etc.)
   if(!CheckTradingConditions()) return;

   //--- Check Killzone Time
   if(UseKillzoneFilter && !IsInKillzone()) return;


   //--- Determine Bias
   bool allowShort = false;
   bool allowLong = false;

   if(BiasMode == Manual_Input)
   {
       if(ManualBias == ShortOnly || ManualBias == Both) allowShort = true;
       if(ManualBias == LongOnly || ManualBias == Both) allowLong = true;
   }
   else // MA_Filter
   {
       if(htf_ma_handle == INVALID_HANDLE) { Print("HTF MA Handle invalid in CheckForSetups"); return; }
       double ma_buffer[2];
       if(CopyBuffer(htf_ma_handle, 0, 0, 2, ma_buffer) >= 2)
       {
           MqlRates htf_rates[2];
           if(CopyRates(symbol, HTF_Timeframe, 0, 2, htf_rates) >= 2)
           {
               ArraySetAsSeries(htf_rates, true);
               if(htf_rates[0].close < ma_buffer[1]) allowShort = true;
               if(htf_rates[0].close > ma_buffer[1]) allowLong = true;
           } else { Print("Failed to get HTF rates for bias check."); return; }
       } else { Print("Failed to get HTF MA buffer for bias check."); return; }
   }


   //--- Execute Checks based on Inputs and Bias
   if((TradeDirection == ShortOnly || TradeDirection == Both) && allowShort)
   {
      // Check if a short position already exists if multiple trades are disallowed
      if(!AllowMultipleTrades && shortPositionExists) {} // Do nothing
      else { CheckForShortSetup(); }
   }

   if((TradeDirection == LongOnly || TradeDirection == Both) && allowLong)
   {
       // Check if a long position already exists if multiple trades are disallowed
       if(!AllowMultipleTrades && longPositionExists) {} // Do nothing
       else { CheckForLongSetup(); }
   }
}


//+------------------------------------------------------------------+
//| Check for the SHORT Setup                                        |
//+------------------------------------------------------------------+
void CheckForShortSetup()
{
   MqlRates rates[];
   int barsNeeded = 200;
   if(CopyRates(symbol, EntryTimeframe, 0, barsNeeded, rates) < barsNeeded) return;
   ArraySetAsSeries(rates, true); // Error 193 is sometimes spurious if other errors exist, should be okay now.

   int atrHandle = iATR(symbol, EntryTimeframe, DisplacementATRPeriod);
   if(atrHandle == INVALID_HANDLE) { Print("Failed to create ATR handle"); return; }
   double atrBuffer[2];
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuffer) < 1) { IndicatorRelease(atrHandle); return; }
   double currentATR = atrBuffer[0];
   IndicatorRelease(atrHandle); // Release handle


   int sweepHighIndex = -1; double sweepHighPrice = 0; bool pdhSwept = false;
   MqlRates dailyRates[];
   if(CopyRates(symbol, PERIOD_D1, 0, LiquidityLookback + 1, dailyRates) < LiquidityLookback + 1) return;
   ArraySetAsSeries(dailyRates, true);
   double pdh = dailyRates[LiquidityLookback].high;

   int searchRange = 50;
   for(int i = 1; i < searchRange; i++) { if(rates[i].high > sweepHighPrice) { sweepHighPrice = rates[i].high; sweepHighIndex = i; } }
   if(sweepHighIndex < 1) return;
   if(sweepHighPrice > pdh) pdhSwept = true;
   if(!pdhSwept) { bool sweptRecent = false; for(int k=sweepHighIndex+1; k<sweepHighIndex+15 && k < barsNeeded; k++){if(rates[k].high < sweepHighPrice){sweptRecent=true; break;}} if(!sweptRecent) return;}


   int mssIndex = -1; double mssLevel = 0; int mssSwingLowIndex = -1;
   bool mssFound = false; // Flag to replace goto
   for(int i = 1; i < sweepHighIndex; i++) {
      if(IsSwingLow(rates, i, SwingLookback)) {
          mssSwingLowIndex = i;
          mssLevel = rates[i].low;
          for(int j = sweepHighIndex - 1; j >= 1; j--) {
              if(rates[j].low < mssLevel) {
                  mssIndex = j;
                  mssFound = true; // Set flag
                  break; // Exit inner loop
              }
          }
          if(mssFound) break; // Exit outer loop if MSS found
      }
   }
   if(!mssFound || mssIndex < 1) return; // Check flag


   double displacementLow = rates[mssIndex].low;
   for(int k = mssIndex -1; k > 0 && k > mssIndex - 10; k--) { if(rates[k].low < displacementLow) displacementLow = rates[k].low; }
   double displacementRangePoints = (sweepHighPrice - displacementLow) / pointValue;
   double requiredDisplacementPoints = currentATR * DisplacementMinFactor / pointValue;
   bool hasLargeCandle = false;
   if(displacementRangePoints < requiredDisplacementPoints) return;
   for(int i = sweepHighIndex -1; i >= mssIndex; i--) { if((rates[i].open - rates[i].close) / pointValue >= MinLargeCandlePoints) { hasLargeCandle = true; break; } }
   if(!hasLargeCandle) return;


   int fvgIndex = -1; double fvgHigh = 0, fvgLow = 0;
   bool fvgFound = false; // Flag to replace goto
   for(int i = sweepHighIndex - 1; i > mssIndex ; i--) {
      if(i + 1 < barsNeeded && i - 1 >= 0) {
          if(rates[i-1].low > rates[i+1].high) {
              double gapPips = (rates[i-1].low - rates[i+1].high) / (pointValue * pow(10, digitsValue - 1));
              if (gapPips >= FVG_MinPips) {
                  fvgIndex = i;
                  fvgHigh = rates[i-1].low;
                  fvgLow = rates[i+1].high;
                  fvgFound = true; // Set flag
                  break; // Exit loop
              }
          }
      }
   }
   if(!fvgFound || fvgIndex < 1) return; // Check flag


   bool retraced = false;
   if(rates[0].high >= fvgLow && rates[0].close < fvgHigh) retraced = true;
   if(!retraced && rates[1].high >= fvgLow && rates[1].high <= fvgHigh) retraced = true;
   if(!retraced) return;


   if(RequireOTE) {
       double displacementActualLow = displacementLow;
       for(int i = sweepHighIndex -1; i >= 1; i--) { if(rates[i].low < displacementActualLow) displacementActualLow = rates[i].low; if(rates[i].high > fvgHigh && i < fvgIndex) break; }
       if(sweepHighPrice <= displacementActualLow) return; // Avoid division by zero or invalid range
       double fibLevel = (rates[0].high - displacementActualLow) / (sweepHighPrice - displacementActualLow);
       if(rates[0].high < fvgLow || fibLevel < OTE_Level_1 || fibLevel > OTE_Level_2) return;
   }


   double entryPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double stopLossPrice = sweepHighPrice + (StopLossStructureBufferPips * pointValue * pow(10, digitsValue - 1));
   if(StopLossPips > 0) { stopLossPrice = entryPrice + (StopLossPips * pointValue * pow(10, digitsValue - 1)); }
   double takeProfitPrice = 0;
   if(TakeProfitPips > 0) { takeProfitPrice = entryPrice - (TakeProfitPips * pointValue * pow(10, digitsValue - 1)); }
   else if(RiskRewardRatio > 0) { double riskPoints = (stopLossPrice - entryPrice) / pointValue; if(riskPoints > 0.1) { takeProfitPrice = entryPrice - (riskPoints * RiskRewardRatio * pointValue); } else return; } // Added min risk check
   else { if(sweepHighPrice > mssLevel) takeProfitPrice = mssLevel - (sweepHighPrice - mssLevel); else return; } // Basic 1:1 projection, ensure valid calc

   if(takeProfitPrice <= 0) return; // Safety check for TP

   PrintFormat("SHORT SETUP FOUND & TRIGGERED:");
   PrintFormat("Sweep High: %.5f | MSS Low Break: %.5f | FVG: %.5f-%.5f", sweepHighPrice, mssLevel, fvgLow, fvgHigh);
   PrintFormat("Entry: ~%.5f | SL: %.5f | TP: %.5f", entryPrice, stopLossPrice, takeProfitPrice);
   if(!trade.Sell(Lots, symbol, entryPrice, stopLossPrice, takeProfitPrice, "ICT Conf Short")) { Print("Sell Order failed: ", GetLastError(), " - ", trade.ResultComment()); } else { Print("Sell Order successful: ", trade.ResultDeal()); }
}

//+------------------------------------------------------------------+
//| Check for the LONG Setup                                         |
//+------------------------------------------------------------------+
void CheckForLongSetup()
{
   MqlRates rates[];
   int barsNeeded = 200;
   if(CopyRates(symbol, EntryTimeframe, 0, barsNeeded, rates) < barsNeeded) return;
   ArraySetAsSeries(rates, true);

   int atrHandle = iATR(symbol, EntryTimeframe, DisplacementATRPeriod);
   if(atrHandle == INVALID_HANDLE) { Print("Failed to create ATR handle"); return; }
   double atrBuffer[2];
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuffer) < 1) { IndicatorRelease(atrHandle); return; }
   double currentATR = atrBuffer[0];
   IndicatorRelease(atrHandle);


   int sweepLowIndex = -1; double sweepLowPrice = 9999999.0; bool pdlSwept = false;
   MqlRates dailyRates[];
   if(CopyRates(symbol, PERIOD_D1, 0, LiquidityLookback + 1, dailyRates) < LiquidityLookback + 1) return;
   ArraySetAsSeries(dailyRates, true);
   double pdl = dailyRates[LiquidityLookback].low;

   int searchRange = 50;
   for(int i = 1; i < searchRange; i++) { if(rates[i].low < sweepLowPrice) { sweepLowPrice = rates[i].low; sweepLowIndex = i; } }
   if(sweepLowIndex < 1) return;
   if(sweepLowPrice < pdl) pdlSwept = true;
   if(!pdlSwept) { bool sweptRecent = false; for(int k=sweepLowIndex+1; k<sweepLowIndex+15 && k < barsNeeded; k++){if(rates[k].low > sweepLowPrice){sweptRecent=true; break;}} if(!sweptRecent) return;}


   int mssIndex = -1; double mssLevel = 0; int mssSwingHighIndex = -1;
   bool mssFound = false; // Flag to replace goto
   for(int i = 1; i < sweepLowIndex; i++) {
       if(IsSwingHigh(rates, i, SwingLookback)) {
           mssSwingHighIndex = i;
           mssLevel = rates[i].high;
           for(int j = sweepLowIndex - 1; j >= 1; j--) {
               if(rates[j].high > mssLevel) {
                   mssIndex = j;
                   mssFound = true; // Set flag
                   break; // Exit inner loop
               }
           }
           if(mssFound) break; // Exit outer loop if MSS found
       }
   }
   if(!mssFound || mssIndex < 1) return; // Check flag


   double displacementHigh = rates[mssIndex].high;
   for(int k = mssIndex -1; k > 0 && k > mssIndex - 10; k--) { if(rates[k].high > displacementHigh) displacementHigh = rates[k].high; }
   double displacementRangePoints = (displacementHigh - sweepLowPrice) / pointValue;
   double requiredDisplacementPoints = currentATR * DisplacementMinFactor / pointValue;
   bool hasLargeCandle = false;
   if(displacementRangePoints < requiredDisplacementPoints) return;
   for(int i = sweepLowIndex -1; i >= mssIndex; i--) { if((rates[i].close - rates[i].open) / pointValue >= MinLargeCandlePoints) { hasLargeCandle = true; break; } }
   if(!hasLargeCandle) return;


   int fvgIndex = -1; double fvgHigh = 0, fvgLow = 0;
   bool fvgFound = false; // Flag to replace goto
   for(int i = sweepLowIndex - 1; i > mssIndex ; i--) {
      if(i + 1 < barsNeeded && i - 1 >= 0) {
          if(rates[i-1].high < rates[i+1].low) {
              double gapPips = (rates[i+1].low - rates[i-1].high) / (pointValue * pow(10, digitsValue - 1));
              if (gapPips >= FVG_MinPips) {
                  fvgIndex = i;
                  fvgHigh = rates[i+1].low;
                  fvgLow = rates[i-1].high;
                  fvgFound = true; // Set flag
                  break; // Exit loop
              }
          }
      }
   }
   if(!fvgFound || fvgIndex < 1) return; // Check flag


   bool retraced = false;
   if(rates[0].low <= fvgHigh && rates[0].close > fvgLow) retraced = true;
   if(!retraced && rates[1].low <= fvgHigh && rates[1].low >= fvgLow) retraced = true;
   if(!retraced) return;


   if(RequireOTE) {
       double displacementActualHigh = displacementHigh;
       for(int i = sweepLowIndex -1; i >= 1; i--) { if(rates[i].high > displacementActualHigh) displacementActualHigh = rates[i].high; if(rates[i].low < fvgLow && i < fvgIndex) break; }
       if(displacementActualHigh <= sweepLowPrice) return; // Avoid division by zero or invalid range
       double fibLevel = (rates[0].low - sweepLowPrice) / (displacementActualHigh - sweepLowPrice);
       if(rates[0].low > fvgHigh || fibLevel < OTE_Level_1 || fibLevel > OTE_Level_2) return;
   }


   double entryPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
   double stopLossPrice = sweepLowPrice - (StopLossStructureBufferPips * pointValue * pow(10, digitsValue - 1));
   if(StopLossPips > 0) { stopLossPrice = entryPrice - (StopLossPips * pointValue * pow(10, digitsValue - 1)); }
   double takeProfitPrice = 0;
   if(TakeProfitPips > 0) { takeProfitPrice = entryPrice + (TakeProfitPips * pointValue * pow(10, digitsValue - 1)); }
   else if(RiskRewardRatio > 0) { double riskPoints = (entryPrice - stopLossPrice) / pointValue; if(riskPoints > 0.1) { takeProfitPrice = entryPrice + (riskPoints * RiskRewardRatio * pointValue); } else return; } // Added min risk check
   else { if(mssLevel > sweepLowPrice) takeProfitPrice = mssLevel + (mssLevel - sweepLowPrice); else return; } // Basic 1:1 projection, ensure valid calc

   if(takeProfitPrice <= entryPrice && TakeProfitPips <=0 && RiskRewardRatio <= 0) return; // Safety check for TP if not fixed pips/RR

   PrintFormat("LONG SETUP FOUND & TRIGGERED:");
   PrintFormat("Sweep Low: %.5f | MSS High Break: %.5f | FVG: %.5f-%.5f", sweepLowPrice, mssLevel, fvgLow, fvgHigh);
   PrintFormat("Entry: ~%.5f | SL: %.5f | TP: %.5f", entryPrice, stopLossPrice, takeProfitPrice);
   if(!trade.Buy(Lots, symbol, entryPrice, stopLossPrice, takeProfitPrice, "ICT Conf Long")) { Print("Buy Order failed: ", GetLastError(), " - ", trade.ResultComment()); } else { Print("Buy Order successful: ", trade.ResultDeal()); }
}


//+------------------------------------------------------------------+
//| Helper: Is price currently within a defined Killzone?            |
//+------------------------------------------------------------------+
bool IsInKillzone()
{
   MqlDateTime currentTime;
   TimeCurrent(currentTime); // Get server time
   int currentHour = currentTime.hour;
   int currentMin = currentTime.min;
   int currentTimeMinutes = currentHour * 60 + currentMin;

   //--- London KZ Check
   int lokzStartMinutes = LOKZ_Start_Hour * 60 + LOKZ_Start_Min;
   int lokzEndMinutes = LOKZ_End_Hour * 60 + LOKZ_End_Min;
   if(currentTimeMinutes >= lokzStartMinutes && currentTimeMinutes < lokzEndMinutes) return true;

   //--- New York KZ Check
   int nykzStartMinutes = NYKZ_Start_Hour * 60 + NYKZ_Start_Min;
   int nykzEndMinutes = NYKZ_End_Hour * 60 + NYKZ_End_Min;
   if(currentTimeMinutes >= nykzStartMinutes && currentTimeMinutes < nykzEndMinutes) return true;

   return false; // Not in any defined KZ
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
   for(int i = 1; i <= lookback; i++) { if(rates[index + i].high >= currentHigh) return false; }
   for(int i = 1; i <= lookback; i++) { if(rates[index - i].high >= currentHigh) return false; }
   return true;
}

//+------------------------------------------------------------------+
//| Check Trading Conditions (Spread etc)                            |
//+------------------------------------------------------------------+
bool CheckTradingConditions()
{
   if(MaxSpreadPoints > 0) { double spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD); if(spread > MaxSpreadPoints && spread > 0) { /*Print("Spread too high: ",spread);*/ return false; } } // Added spread > 0 check
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) { Print("Automated trading is disabled in Terminal settings."); return false; }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) { Print("Automated trading is disabled for this EA in settings."); return false; }
   return true;
}

// Removed IsTradeContextBusy as it was causing errors and isn't standard robust check

//+------------------------------------------------------------------+
