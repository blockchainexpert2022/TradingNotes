//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Get the list of symbols in the Market Watch
    string symbols[];
    int symbol_count = SymbolsTotal(true);
    
    // Resize the array to hold all symbols
    ArrayResize(symbols, symbol_count);
    
    // Fill the array with symbols from the Market Watch
    for(int i = 0; i < symbol_count; i++)
    {
        symbols[i] = SymbolName(i, true);
    }
    
    // Initialize the highest and lowest prices for each symbol
    for(int i = 0; i < symbol_count; i++)
    {
        string symbol = symbols[i];
        double highest_price = GetHighestPrice(symbol, 55);
        double lowest_price = GetLowestPrice(symbol, 55);
        Print("Initialized for symbol: ", symbol, " - Highest: ", highest_price, " - Lowest: ", lowest_price);
    }
    
    return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Deinitialization logic here
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Get the list of symbols in the Market Watch
    string symbols[];
    int symbol_count = SymbolsTotal(true);
    
    // Resize the array to hold all symbols
    ArrayResize(symbols, symbol_count);
    
    // Fill the array with symbols from the Market Watch
    for(int i = 0; i < symbol_count; i++)
    {
        symbols[i] = SymbolName(i, true);
    }
    
    // Loop through each symbol
    for(int i = 0; i < symbol_count; i++)
    {
        string symbol = symbols[i];
        
        // Get the current price
        double current_price = SymbolInfoDouble(symbol, SYMBOL_BID);
        
        // Check if a new candle has started
        static datetime last_time[];
        if(ArraySize(last_time) != symbol_count)
        {
            ArrayResize(last_time, symbol_count);
            ArrayInitialize(last_time, 0);
        }
        
        datetime current_time = iTime(symbol, PERIOD_CURRENT, 0);
        if(last_time[i] != current_time)
        {
            // New candle started, recalculate highest and lowest prices
            last_time[i] = current_time;
            double highest_price = GetHighestPrice(symbol, 55);
            double lowest_price = GetLowestPrice(symbol, 55);
            
            // Check if the current price is above the highest price or below the lowest price
            if(current_price > highest_price)
            {
                Print("Symbol: ", symbol, " - Price is above the highest price of the last 55 candles: ", highest_price);
                PlaySound("alert.wav"); // Play beep sound
            }
            else if(current_price < lowest_price)
            {
                Print("Symbol: ", symbol, " - Price is below the lowest price of the last 55 candles: ", lowest_price);
                PlaySound("alert.wav"); // Play beep sound
            }
        }
    }
}
//+------------------------------------------------------------------+

// Function to get the highest price of the last N candles
double GetHighestPrice(string symbol, int candles)
{
    double highest_price = 0;
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(symbol, PERIOD_CURRENT, 0, candles, rates);
    if(copied > 0)
    {
        for(int i = 0; i < copied; i++)
        {
            highest_price = MathMax(highest_price, rates[i].high);
        }
    }
    return highest_price;
}

// Function to get the lowest price of the last N candles
double GetLowestPrice(string symbol, int candles)
{
    double lowest_price = DBL_MAX;
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(symbol, PERIOD_CURRENT, 0, candles, rates);
    if(copied > 0)
    {
        for(int i = 0; i < copied; i++)
        {
            lowest_price = MathMin(lowest_price, rates[i].low);
        }
    }
    return lowest_price;
}

// Function to get the time of the current bar
datetime iTime(string symbol, int timeframe, int shift)
{
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(symbol, (ENUM_TIMEFRAMES)timeframe, shift, 1, rates);
    if(copied > 0)
    {
        return rates[0].time;
    }
    else
    {
        return 0;
    }
}
//+------------------------------------------------------------------+
