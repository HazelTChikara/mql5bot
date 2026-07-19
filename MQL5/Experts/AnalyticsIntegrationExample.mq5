#property copyright "Architecture example"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <AnalyticsExporter.mqh>
#include <ExternalAnalysis.mqh>

input AnalyticsOperatingMode InpOperatingMode       = EXPORT_ONLY;
input ENUM_TIMEFRAMES        InpEntryTimeframe       = PERIOD_M15;
input ENUM_TIMEFRAMES        InpTrendTimeframe       = PERIOD_H1;
input int                    InpFastEmaPeriod        = 20;
input int                    InpSlowEmaPeriod        = 50;
input int                    InpAtrPeriod            = 14;
input double                 InpStopAtrMultiple      = 1.5;
input double                 InpRewardToRisk         = 2.0;
input double                 InpMinTrendSeparationAtr = 0.10;
input double                 InpMinBreakoutAtr       = 0.05;
input double                 InpMinBodyAtr           = 0.20;
input double                 InpRiskPercent          = 0.5;
input double                 InpMaxDailyLossPercent  = 2.0;
input double                 InpMaxSpreadPoints      = 30.0;
input long                   InpMagicNumber          = 26071701;
input int                    InpMaxSlippagePoints    = 10;
input string                 InpAnalyticsDirectory  = "Analytics";
input bool                   InpUseCommonFiles       = false;
input string                 InpExpectedModelVersion = "";
input int                    InpExternalTimeoutMs    = 100;
input int                    InpExternalMaxAgeSeconds = 30;

CTrade                     g_trade;
IAnalyticsExporter        *g_exporter       = NULL;
IExternalAnalysisProvider *g_external       = NULL;
ExternalAnalysisGuard     *g_externalGuard  = NULL;

int      g_atrHandle       = INVALID_HANDLE;
int      g_fastEmaHandle   = INVALID_HANDLE;
int      g_slowEmaHandle   = INVALID_HANDLE;
datetime g_lastBarTime     = 0;
uint     g_setupSequence   = 0;
string   g_runId           = "";
int      g_dayKey          = -1;
bool     g_stoppedForDay   = false;

bool     g_trackingTrade   = false;
string   g_activeSetupId   = "";
ulong    g_activeTicket    = 0;
ulong    g_activePositionId = 0;
datetime g_activeEntryTime = 0;
double   g_activeEntry     = 0.0;
double   g_activeRiskMoney = 0.0;
double   g_activeVolume    = 0.0;
double   g_mfePoints       = 0.0;
double   g_maePoints       = 0.0;

string MakeSetupId(const datetime decisionBarTime)
{
   g_setupSequence++;
   return StringFormat("%s-%s-%I64d-%u", _Symbol, g_runId,
                       (long)decisionBarTime, g_setupSequence);
}

datetime StartOfBrokerDay(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   parts.hour = 0;
   parts.min  = 0;
   parts.sec  = 0;
   return StructToTime(parts);
}

int BrokerDayKey(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   return parts.year * 1000 + parts.day_of_year;
}

string SessionName(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   if(parts.hour < 7)
      return "ASIAN";
   if(parts.hour < 12)
      return "LONDON";
   if(parts.hour < 17)
      return "NEW_YORK";
   return "OFF_HOURS";
}

bool ReadIndicatorValue(const int handle, const int shift, double &value)
{
   double values[1];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, 0, shift, 1, values) != 1)
      return false;
   value = values[0];
   return MathIsValidNumber(value) && value != EMPTY_VALUE;
}

void ReadAsianRange(const datetime serverTime, double &rangeHigh, double &rangeLow)
{
   rangeHigh = 0.0;
   rangeLow  = 0.0;
   const datetime dayStart = StartOfBrokerDay(serverTime);
   const datetime asianEnd = dayStart + 7 * 60 * 60;
   const datetime endTime  = serverTime < asianEnd ? serverTime : asianEnd;
   if(endTime <= dayStart)
      return;

   MqlRates bars[];
   const int count = CopyRates(_Symbol, PERIOD_M15, dayStart, endTime, bars);
   if(count <= 0)
      return;

   rangeHigh = bars[0].high;
   rangeLow  = bars[0].low;
   for(int i = 1; i < count; i++)
   {
      rangeHigh = MathMax(rangeHigh, bars[i].high);
      rangeLow  = MathMin(rangeLow, bars[i].low);
   }
}

void ReadRecentSwings(double &swingHigh, double &swingLow)
{
   swingHigh = 0.0;
   swingLow  = 0.0;
   for(int shift = 2; shift <= 6; shift++)
   {
      const double high = iHigh(_Symbol, InpEntryTimeframe, shift);
      const double low  = iLow(_Symbol, InpEntryTimeframe, shift);
      if(high > 0.0 && (swingHigh == 0.0 || high > swingHigh))
         swingHigh = high;
      if(low > 0.0 && (swingLow == 0.0 || low < swingLow))
         swingLow = low;
   }
}

bool BuildSnapshot(const MqlRates &closedBar, const datetime serverTime,
                   MarketSnapshot &snapshot)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return false;

   double atr = 0.0;
   double fastEma = 0.0;
   double slowEma = 0.0;
   if(!ReadIndicatorValue(g_atrHandle, 1, atr) ||
      !ReadIndicatorValue(g_fastEmaHandle, 1, fastEma) ||
      !ReadIndicatorValue(g_slowEmaHandle, 1, slowEma))
      return false;

   MqlRates previousDay[1];
   if(CopyRates(_Symbol, PERIOD_D1, 1, 1, previousDay) != 1)
      return false;

   ZeroMemory(snapshot);
   snapshot.analyticsSchemaVersion = ANALYTICS_SCHEMA_VERSION;
   snapshot.setupId                = MakeSetupId(closedBar.time);
   snapshot.timestamp              = closedBar.time;
   snapshot.symbol                 = _Symbol;
   snapshot.brokerServerTime       = serverTime;
   snapshot.entryTimeframe         = InpEntryTimeframe;
   snapshot.trendTimeframe         = InpTrendTimeframe;
   snapshot.bid                    = tick.bid;
   snapshot.ask                    = tick.ask;
   snapshot.spreadPoints           = (tick.ask - tick.bid) / _Point;
   snapshot.barOpen                = closedBar.open;
   snapshot.barHigh                = closedBar.high;
   snapshot.barLow                 = closedBar.low;
   snapshot.barClose               = closedBar.close;
   snapshot.tickVolume             = closedBar.tick_volume;
   snapshot.atrPoints              = atr / _Point;
   snapshot.fastEma                = fastEma;
   snapshot.slowEma                = slowEma;
   snapshot.trendClassification    = fastEma > slowEma ? "BULLISH" :
                                     (fastEma < slowEma ? "BEARISH" : "NEUTRAL");
   snapshot.previousDayHigh        = previousDay[0].high;
   snapshot.previousDayLow         = previousDay[0].low;
   ReadAsianRange(serverTime, snapshot.asianSessionHigh, snapshot.asianSessionLow);
   ReadRecentSwings(snapshot.detectedSwingHigh, snapshot.detectedSwingLow);
   snapshot.sessionClassification  = SessionName(serverTime);
   return true;
}

void TodayStrategyProfit(const datetime serverTime, double &realizedProfit,
                         double &floatingProfit)
{
   realizedProfit = 0.0;
   floatingProfit = 0.0;
   if(!HistorySelect(StartOfBrokerDay(serverTime), serverTime))
      return;

   const int count = HistoryDealsTotal();
   for(int i = 0; i < count; i++)
   {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagicNumber)
         continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
         continue;
      realizedProfit += HistoryDealGetDouble(deal, DEAL_PROFIT);
      realizedProfit += HistoryDealGetDouble(deal, DEAL_COMMISSION);
      realizedProfit += HistoryDealGetDouble(deal, DEAL_SWAP);
   }

   if(PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      floatingProfit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
}

bool DailyRiskAllowsTrading(const datetime serverTime, string &reason)
{
   const int key = BrokerDayKey(serverTime);
   if(key != g_dayKey)
   {
      g_dayKey        = key;
      g_stoppedForDay = false;
   }

   if(g_stoppedForDay)
   {
      reason = "DAILY_STOP_ALREADY_ACTIVE";
      return false;
   }

   double realizedProfit = 0.0;
   double floatingProfit = 0.0;
   TodayStrategyProfit(serverTime, realizedProfit, floatingProfit);
   const double todayProfit = realizedProfit + floatingProfit;
   const double startBalance = MathMax(1.0,
      AccountInfoDouble(ACCOUNT_BALANCE) - realizedProfit);
   const double maximumLoss = startBalance * InpMaxDailyLossPercent / 100.0;
   if(todayProfit <= -maximumLoss)
   {
      g_stoppedForDay = true;
      reason = "DAILY_LOSS_LIMIT_REACHED";
      return false;
   }
   return true;
}

void EnforceDailyRiskLimit(void)
{
   static datetime lastCheck = 0;
   const datetime serverTime = TimeTradeServer();
   if(serverTime <= 0 || serverTime == lastCheck)
      return;
   lastCheck = serverTime;

   string reason = "";
   const bool allowed = DailyRiskAllowsTrading(serverTime, reason);
   if(allowed || !g_stoppedForDay || !PositionSelect(_Symbol) ||
      PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
      return;

   if(!g_trade.PositionClose(_Symbol))
      PrintFormat("Emergency daily-limit close failed: %u %s",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
}

bool ValidateProtectivePrices(const bool isLong, const double entry,
                              const double stopLoss, const double takeProfit,
                              string &reason)
{
   if(entry <= 0.0 || stopLoss <= 0.0 || takeProfit <= 0.0)
   {
      reason = "INVALID_PROTECTIVE_PRICE";
      return false;
   }
   if((isLong && !(stopLoss < entry && takeProfit > entry)) ||
      (!isLong && !(stopLoss > entry && takeProfit < entry)))
   {
      reason = "STOP_OR_TARGET_WRONG_SIDE";
      return false;
   }

   const double minimumDistance =
      (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(MathAbs(entry - stopLoss) < minimumDistance ||
      MathAbs(takeProfit - entry) < minimumDistance)
   {
      reason = "BROKER_MINIMUM_STOP_DISTANCE";
      return false;
   }
   return true;
}

double CalculatePositionSize(const bool isLong, const double entry,
                             const double stopLoss, const double riskMultiplier,
                             string &reason)
{
   const double tickSize      = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double tickValueLoss = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   const double volumeMin     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double volumeMax     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double volumeStep    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(tickSize <= 0.0 || tickValueLoss <= 0.0 || volumeStep <= 0.0)
   {
      reason = "INVALID_BROKER_SIZING_METADATA";
      return 0.0;
   }

   const double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) *
                           InpRiskPercent / 100.0 * MathMin(1.0, riskMultiplier);
   const double moneyPerLot = MathAbs(entry - stopLoss) / tickSize * tickValueLoss;
   if(riskCash <= 0.0 || moneyPerLot <= 0.0)
   {
      reason = "NON_POSITIVE_RISK_BUDGET";
      return 0.0;
   }

   double volume = MathFloor((riskCash / moneyPerLot) / volumeStep) * volumeStep;
   if(volume < volumeMin)
   {
      reason = "MINIMUM_VOLUME_WOULD_EXCEED_RISK";
      return 0.0;
   }
   volume = MathMin(volume, volumeMax);

   double margin = 0.0;
   const ENUM_ORDER_TYPE orderType = isLong ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(orderType, _Symbol, volume, entry, margin) ||
      margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   {
      reason = "INSUFFICIENT_FREE_MARGIN";
      return 0.0;
   }
   return NormalizeDouble(volume, 8);
}

void InitializeDecision(const MarketSnapshot &snapshot, const MqlRates &closedBar,
                        const MqlRates &priorBar, SignalDecision &decision)
{
   ZeroMemory(decision);
   decision.analyticsSchemaVersion          = ANALYTICS_SCHEMA_VERSION;
   decision.setupId                         = snapshot.setupId;
   decision.timestamp                       = snapshot.timestamp;
   decision.symbol                          = snapshot.symbol;
   decision.liquidityLevelType              = "RECENT_SWING";
   decision.liquidityLevelPrice             = 0.0;
   decision.sweepDirection                  = "NONE";
   decision.sweepExtreme                    = 0.0;
   decision.sweepConfirmationTime           = 0;
   decision.bosDirection                    = "NONE";
   decision.brokenStructureLevel            = 0.0;
   decision.retestPrice                     = 0.0;
   decision.retestDistancePoints            = 0.0;
   decision.confirmationOpen                = closedBar.open;
   decision.confirmationHigh                = closedBar.high;
   decision.confirmationLow                 = closedBar.low;
   decision.confirmationClose               = closedBar.close;
   decision.confirmationBodyPoints          = MathAbs(closedBar.close - closedBar.open) / _Point;
   decision.confirmationUpperWickPoints      =
      (closedBar.high - MathMax(closedBar.open, closedBar.close)) / _Point;
   decision.confirmationLowerWickPoints      =
      (MathMin(closedBar.open, closedBar.close) - closedBar.low) / _Point;
   decision.confirmationBullish              = closedBar.close > closedBar.open;
   decision.proposedEntryPrice               = 0.0;
   decision.proposedStopLossPrice            = 0.0;
   decision.proposedTakeProfitPrice          = 0.0;
   decision.riskPoints                       = 0.0;
   decision.rewardToRiskRatio                = InpRewardToRisk;
   decision.calculatedPositionSize           = 0.0;
   decision.strategyState                    = "EVALUATING";
   decision.signalAccepted                   = false;
   decision.rejectionReason                  = "NO_DIRECTIONAL_BREAKOUT";
   decision.externalAnalysis.available       = false;
   decision.externalAnalysis.qualityScore    = 0.0;
   decision.externalAnalysis.modelVersion    = "";
   decision.externalAnalysis.decision        = "NO_RESPONSE";
   decision.externalAnalysis.explanation     = "External filter not requested";
   decision.externalAnalysis.generatedAt     = 0;
   decision.externalAnalysis.riskMultiplier  = 1.0;
   decision.externalDecisionApplied          = false;
   decision.appliedRiskMultiplier            = 1.0;

   const double atrPrice = snapshot.atrPoints * _Point;
   if(atrPrice <= 0.0)
   {
      decision.rejectionReason = "INVALID_ATR";
      return;
   }
   const double trendSeparationAtr = MathAbs(snapshot.fastEma - snapshot.slowEma) / atrPrice;
   const double bodyAtr = MathAbs(closedBar.close - closedBar.open) / atrPrice;
   const double bullishDisplacementAtr = (closedBar.close - priorBar.high) / atrPrice;
   const double bearishDisplacementAtr = (priorBar.low - closedBar.close) / atrPrice;
   const bool qualityConfirmed = trendSeparationAtr >= InpMinTrendSeparationAtr &&
                                 bodyAtr >= InpMinBodyAtr;
   const bool bullishBreakout = qualityConfirmed &&
                                bullishDisplacementAtr >= InpMinBreakoutAtr &&
                                snapshot.trendClassification == "BULLISH" &&
                                closedBar.close > priorBar.high &&
                                closedBar.close > closedBar.open;
   const bool bearishBreakout = qualityConfirmed &&
                                bearishDisplacementAtr >= InpMinBreakoutAtr &&
                                snapshot.trendClassification == "BEARISH" &&
                                closedBar.close < priorBar.low &&
                                closedBar.close < closedBar.open;
   if(!bullishBreakout && !bearishBreakout)
   {
      if(!qualityConfirmed)
         decision.rejectionReason = "SIGNAL_QUALITY_FILTER";
      else
         decision.rejectionReason = "INSUFFICIENT_BREAKOUT_DISPLACEMENT";
      return;
   }

   const bool isLong = bullishBreakout;
   decision.signalAccepted        = true;
   decision.rejectionReason       = "";
   decision.bosDirection          = isLong ? "UP" : "DOWN";
   decision.brokenStructureLevel  = isLong ? priorBar.high : priorBar.low;
   decision.liquidityLevelPrice   = decision.brokenStructureLevel;
   decision.proposedEntryPrice    = isLong ? snapshot.ask : snapshot.bid;
   const double stopDistance      = snapshot.atrPoints * _Point * InpStopAtrMultiple;
   decision.proposedStopLossPrice = isLong ? decision.proposedEntryPrice - stopDistance :
                                             decision.proposedEntryPrice + stopDistance;
   decision.proposedTakeProfitPrice = isLong ?
      decision.proposedEntryPrice + stopDistance * InpRewardToRisk :
      decision.proposedEntryPrice - stopDistance * InpRewardToRisk;
   decision.riskPoints = stopDistance / _Point;
   decision.strategyState = "RULE_ACCEPTED";
}

void ApplyRiskAndExternalGuards(const MarketSnapshot &snapshot, SignalDecision &decision)
{
   if(!decision.signalAccepted)
      return;

   string reason = "";
   if(!DailyRiskAllowsTrading(snapshot.brokerServerTime, reason))
   {
      decision.signalAccepted  = false;
      decision.rejectionReason = reason;
      decision.strategyState   = "RISK_REJECTED";
      return;
   }
   if(PositionSelect(_Symbol))
   {
      decision.signalAccepted  = false;
      decision.rejectionReason = "POSITION_ALREADY_OPEN_NO_PYRAMIDING";
      decision.strategyState   = "RISK_REJECTED";
      return;
   }
   if(snapshot.spreadPoints > InpMaxSpreadPoints)
   {
      decision.signalAccepted  = false;
      decision.rejectionReason = "SPREAD_LIMIT_EXCEEDED";
      decision.strategyState   = "BROKER_REJECTED";
      return;
   }

   const bool isLong = decision.bosDirection == "UP";
   if(!ValidateProtectivePrices(isLong, decision.proposedEntryPrice,
                                decision.proposedStopLossPrice,
                                decision.proposedTakeProfitPrice, reason))
   {
      decision.signalAccepted  = false;
      decision.rejectionReason = reason;
      decision.strategyState   = "BROKER_REJECTED";
      return;
   }

   double riskMultiplier = 1.0;
   if(InpOperatingMode == EXTERNAL_FILTER)
   {
      ExternalAnalysisResult external;
      ZeroMemory(external);
      external.decision       = "NO_RESPONSE";
      external.explanation    = "No cached response available within timeout";
      external.riskMultiplier = 1.0;

      // This call is contractually non-blocking. InpExternalTimeoutMs is an upper
      // bound for a future asynchronous adapter, never a sleep inside OnTick.
      g_external.TryGetLatest(decision.setupId, external);
      decision.externalAnalysis = external;

      string externalReason = "";
      const ExternalFilterStatus status = g_externalGuard.Apply(
         true, snapshot.brokerServerTime, external,
         decision.signalAccepted, riskMultiplier, externalReason);
      if(status == EXTERNAL_VALID_REJECT)
      {
         decision.externalDecisionApplied = true;
         decision.rejectionReason          = externalReason;
         decision.strategyState            = "EXTERNAL_REJECTED";
      }
      else if(status == EXTERNAL_VALID_REDUCE_RISK)
      {
         decision.externalDecisionApplied = true;
         decision.strategyState            = "EXTERNAL_RISK_REDUCED";
      }
      else if(status == EXTERNAL_INVALID_FALLBACK)
      {
         decision.externalAnalysis.explanation = externalReason;
         decision.strategyState = "MQL5_FALLBACK";
      }
   }

   decision.appliedRiskMultiplier = riskMultiplier;
   if(!decision.signalAccepted)
      return;

   decision.calculatedPositionSize = CalculatePositionSize(
      isLong, decision.proposedEntryPrice, decision.proposedStopLossPrice,
      riskMultiplier, reason);
   if(decision.calculatedPositionSize <= 0.0)
   {
      decision.signalAccepted  = false;
      decision.rejectionReason = reason;
      decision.strategyState   = "RISK_REJECTED";
   }
}

void ExportOrderRejection(const SignalDecision &decision, const string reason)
{
   TradeEvent event;
   ZeroMemory(event);
   event.analyticsSchemaVersion = ANALYTICS_SCHEMA_VERSION;
   event.setupId                 = decision.setupId;
   event.timestamp               = TimeTradeServer();
   event.symbol                  = decision.symbol;
   event.tradeEventType          = "ORDER_REJECTED";
   event.finalTradeResult        = "NOT_APPLICABLE";
   event.exitReason              = reason;
   event.entryPrice              = decision.proposedEntryPrice;
   event.volume                  = decision.calculatedPositionSize;
   g_exporter.ExportTradeEvent(event);
}

void TrackOpenedPosition(const SignalDecision &decision)
{
   if(!PositionSelect(_Symbol))
      return;

   g_trackingTrade   = true;
   g_activeSetupId   = decision.setupId;
   g_activeTicket    = (ulong)PositionGetInteger(POSITION_TICKET);
   g_activePositionId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   g_activeEntryTime = (datetime)PositionGetInteger(POSITION_TIME);
   g_activeEntry     = PositionGetDouble(POSITION_PRICE_OPEN);
   g_activeVolume    = PositionGetDouble(POSITION_VOLUME);
   const double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double tickValueLoss = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   const double actualStop = PositionGetDouble(POSITION_SL);
   g_activeRiskMoney = tickSize > 0.0 && tickValueLoss > 0.0 ?
      MathAbs(g_activeEntry - actualStop) / tickSize * tickValueLoss * g_activeVolume : 0.0;
   g_mfePoints       = 0.0;
   g_maePoints       = 0.0;

   TradeEvent event;
   ZeroMemory(event);
   event.analyticsSchemaVersion = ANALYTICS_SCHEMA_VERSION;
   event.setupId                 = g_activeSetupId;
   event.timestamp               = g_activeEntryTime;
   event.symbol                  = _Symbol;
   event.tradeTicket             = g_activeTicket;
   event.tradeEventType          = "OPENED";
   event.finalTradeResult        = "OPEN";
   event.slippagePoints          = MathAbs(g_activeEntry - decision.proposedEntryPrice) / _Point;
   event.entryPrice              = g_activeEntry;
   event.volume                  = g_activeVolume;
   g_exporter.ExportTradeEvent(event);
}

void PlaceAcceptedOrder(const SignalDecision &decision)
{
   if(InpOperatingMode == DRY_RUN_ANALYTICS)
      return;

   const bool isLong = decision.bosDirection == "UP";
   const bool sent = isLong ?
      g_trade.Buy(decision.calculatedPositionSize, _Symbol, 0.0,
                  decision.proposedStopLossPrice, decision.proposedTakeProfitPrice,
                  "analytics:" + decision.setupId) :
      g_trade.Sell(decision.calculatedPositionSize, _Symbol, 0.0,
                   decision.proposedStopLossPrice, decision.proposedTakeProfitPrice,
                   "analytics:" + decision.setupId);
   if(!sent || (g_trade.ResultRetcode() != TRADE_RETCODE_DONE &&
                g_trade.ResultRetcode() != TRADE_RETCODE_DONE_PARTIAL &&
                g_trade.ResultRetcode() != TRADE_RETCODE_PLACED))
   {
      ExportOrderRejection(decision,
         StringFormat("BROKER_RETCODE_%u_%s", g_trade.ResultRetcode(),
                      g_trade.ResultRetcodeDescription()));
      return;
   }
   TrackOpenedPosition(decision);
}

void UpdateOpenTradeExcursions(void)
{
   if(!g_trackingTrade || !PositionSelect(_Symbol) ||
      (ulong)PositionGetInteger(POSITION_TICKET) != g_activeTicket)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;
   const ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const double current = type == POSITION_TYPE_BUY ? tick.bid : tick.ask;
   const double signedMove = type == POSITION_TYPE_BUY ?
      (current - g_activeEntry) / _Point : (g_activeEntry - current) / _Point;
   g_mfePoints = MathMax(g_mfePoints, signedMove);
   g_maePoints = MathMax(g_maePoints, -signedMove);
}

string DealExitReason(const long reason)
{
   switch((ENUM_DEAL_REASON)reason)
   {
      case DEAL_REASON_SL:     return "STOP_LOSS";
      case DEAL_REASON_TP:     return "TAKE_PROFIT";
      case DEAL_REASON_SO:     return "STOP_OUT";
      case DEAL_REASON_EXPERT: return "EXPERT";
      case DEAL_REASON_CLIENT: return "CLIENT";
      case DEAL_REASON_MOBILE: return "MOBILE";
      case DEAL_REASON_WEB:    return "WEB";
   }
   return "OTHER";
}

void ExportClosedPositionIfNeeded(const ulong exitDealHint = 0)
{
   if(!g_trackingTrade)
      return;
   if(PositionSelect(_Symbol) &&
      (ulong)PositionGetInteger(POSITION_TICKET) == g_activeTicket)
      return;

   const datetime now = TimeTradeServer();
   ulong exitDeal = 0;
   if(exitDealHint > 0 && HistoryDealSelect(exitDealHint) &&
      HistoryDealGetInteger(exitDealHint, DEAL_MAGIC) == InpMagicNumber &&
      HistoryDealGetString(exitDealHint, DEAL_SYMBOL) == _Symbol &&
      (ulong)HistoryDealGetInteger(exitDealHint, DEAL_POSITION_ID) == g_activePositionId)
   {
      const ENUM_DEAL_ENTRY hintedEntry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(exitDealHint, DEAL_ENTRY);
      if(hintedEntry == DEAL_ENTRY_OUT || hintedEntry == DEAL_ENTRY_OUT_BY)
         exitDeal = exitDealHint;
   }

   // HistoryDealSelect narrows the selected history to one deal. Restore the
   // complete position window before calculating P/L or searching a fallback.
   if(!HistorySelect(g_activeEntryTime - 60, now + 60))
      return;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagicNumber ||
         HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) != g_activePositionId)
         continue;
      const ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      {
         exitDeal = deal;
         break;
      }
   }
   if(exitDeal == 0)
      return;

   const datetime exitTime = (datetime)HistoryDealGetInteger(exitDeal, DEAL_TIME);
   double profit = 0.0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
   {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) != g_activePositionId)
         continue;
      profit += HistoryDealGetDouble(deal, DEAL_PROFIT);
      profit += HistoryDealGetDouble(deal, DEAL_COMMISSION);
      profit += HistoryDealGetDouble(deal, DEAL_SWAP);
   }

   TradeEvent event;
   ZeroMemory(event);
   event.analyticsSchemaVersion            = ANALYTICS_SCHEMA_VERSION;
   event.setupId                            = g_activeSetupId;
   event.timestamp                          = exitTime;
   event.symbol                             = _Symbol;
   event.tradeTicket                        = g_activeTicket;
   event.tradeEventType                     = "CLOSED";
   event.finalTradeResult                   = profit > 0.0 ? "WIN" :
                                              (profit < 0.0 ? "LOSS" : "BREAKEVEN");
   event.profitLossMoney                    = profit;
   event.profitLossR                        = g_activeRiskMoney > 0.0 ?
                                              profit / g_activeRiskMoney : 0.0;
   event.maximumFavorableExcursionPoints    = g_mfePoints;
   event.maximumAdverseExcursionPoints      = g_maePoints;
   event.holdingDurationSeconds             = (long)(exitTime - g_activeEntryTime);
   event.exitReason                         = DealExitReason(
      HistoryDealGetInteger(exitDeal, DEAL_REASON));
   event.entryPrice                         = g_activeEntry;
   event.exitPrice                          = HistoryDealGetDouble(exitDeal, DEAL_PRICE);
   event.volume                             = HistoryDealGetDouble(exitDeal, DEAL_VOLUME);
   g_exporter.ExportTradeEvent(event);

   g_trackingTrade = false;
   g_activeSetupId = "";
   g_activeTicket  = 0;
   g_activePositionId = 0;
}

int OnInit(void)
{
   if(InpFastEmaPeriod <= 0 || InpSlowEmaPeriod <= InpFastEmaPeriod ||
      InpAtrPeriod <= 0 || InpRiskPercent <= 0.0 || InpRiskPercent > 100.0 ||
      InpMaxDailyLossPercent <= 0.0 || InpMaxDailyLossPercent > 100.0 ||
      InpRewardToRisk <= 0.0 || InpStopAtrMultiple <= 0.0 ||
      InpMinTrendSeparationAtr < 0.0 || InpMinBreakoutAtr < 0.0 ||
      InpMinBodyAtr < 0.0 ||
      InpMaxSpreadPoints <= 0.0 || InpMagicNumber <= 0 ||
      InpMaxSlippagePoints < 0 || InpExternalTimeoutMs <= 0 ||
      InpExternalMaxAgeSeconds <= 0)
      return INIT_PARAMETERS_INCORRECT;

   g_atrHandle     = iATR(_Symbol, InpEntryTimeframe, InpAtrPeriod);
   g_fastEmaHandle = iMA(_Symbol, InpTrendTimeframe, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_slowEmaHandle = iMA(_Symbol, InpTrendTimeframe, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_atrHandle == INVALID_HANDLE || g_fastEmaHandle == INVALID_HANDLE ||
      g_slowEmaHandle == INVALID_HANDLE)
      return INIT_FAILED;

   if(InpOperatingMode == MQL5_ONLY)
      g_exporter = new NullAnalyticsExporter();
   else
      g_exporter = new CsvAnalyticsExporter(InpAnalyticsDirectory, InpUseCommonFiles, true);

   if(g_exporter == NULL || !g_exporter.Initialize())
   {
      if(g_exporter != NULL)
         delete g_exporter;
      g_exporter = new NullAnalyticsExporter();
      g_exporter.Initialize();
      Print("Analytics initialization failed; using no-op exporter. Trading remains available.");
   }

   g_external      = new NullExternalAnalysisProvider();
   g_externalGuard = new ExternalAnalysisGuard(InpExpectedModelVersion,
                                                InpExternalMaxAgeSeconds);
   if(g_external == NULL || g_externalGuard == NULL ||
      !g_external.Initialize(InpExternalTimeoutMs))
      return INIT_FAILED;

   g_trade.SetExpertMagicNumber((ulong)InpMagicNumber);
   g_trade.SetDeviationInPoints((ulong)InpMaxSlippagePoints);
   g_trade.SetAsyncMode(false);
   if(!g_trade.SetTypeFillingBySymbol(_Symbol))
      return INIT_FAILED;
   g_runId = StringFormat("%I64d-%I64d-%I64u",
      AccountInfoInteger(ACCOUNT_LOGIN), (long)TimeLocal(), GetTickCount64());
   g_dayKey = BrokerDayKey(TimeTradeServer());
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   // The Strategy Tester can liquidate a final position after the last market
   // tick. Reconcile that exit while the exporter is still available.
   if(g_exporter != NULL)
      ExportClosedPositionIfNeeded();

   if(g_exporter != NULL)
   {
      g_exporter.Shutdown();
      delete g_exporter;
      g_exporter = NULL;
   }
   if(g_external != NULL)
   {
      g_external.Shutdown();
      delete g_external;
      g_external = NULL;
   }
   if(g_externalGuard != NULL)
   {
      delete g_externalGuard;
      g_externalGuard = NULL;
   }
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
   if(g_fastEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_fastEmaHandle);
   if(g_slowEmaHandle != INVALID_HANDLE)
      IndicatorRelease(g_slowEmaHandle);
}

void OnTradeTransaction(const MqlTradeTransaction &transaction,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(!g_trackingTrade || transaction.type != TRADE_TRANSACTION_DEAL_ADD ||
      transaction.deal == 0 || !HistoryDealSelect(transaction.deal))
      return;

   if(HistoryDealGetInteger(transaction.deal, DEAL_MAGIC) != InpMagicNumber ||
      HistoryDealGetString(transaction.deal, DEAL_SYMBOL) != _Symbol ||
      (ulong)HistoryDealGetInteger(transaction.deal, DEAL_POSITION_ID) != g_activePositionId)
      return;

   const ENUM_DEAL_ENTRY entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(transaction.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      ExportClosedPositionIfNeeded(transaction.deal);
}

void OnTick(void)
{
   UpdateOpenTradeExcursions();
   EnforceDailyRiskLimit();
   ExportClosedPositionIfNeeded();

   const datetime currentBar = iTime(_Symbol, InpEntryTimeframe, 0);
   if(currentBar <= 0 || currentBar == g_lastBarTime)
      return;
   g_lastBarTime = currentBar;

   MqlRates bars[];
   ArrayResize(bars, 3);
   ArraySetAsSeries(bars, true);
   if(CopyRates(_Symbol, InpEntryTimeframe, 0, 3, bars) != 3)
      return;

   MarketSnapshot snapshot;
   if(!BuildSnapshot(bars[1], TimeTradeServer(), snapshot))
      return;

   SignalDecision decision;
   InitializeDecision(snapshot, bars[1], bars[2], decision);
   ApplyRiskAndExternalGuards(snapshot, decision);
   if(InpOperatingMode == DRY_RUN_ANALYTICS && decision.signalAccepted)
      decision.strategyState = "DRY_RUN_ACCEPTED_NO_ORDER";

   // Every evaluated setup emits both rows, including exact rejection reasons.
   g_exporter.ExportMarketSnapshot(snapshot);
   g_exporter.ExportSignalDecision(decision);

   if(decision.signalAccepted)
      PlaceAcceptedOrder(decision);
}
