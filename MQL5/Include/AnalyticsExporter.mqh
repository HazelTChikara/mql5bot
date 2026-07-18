#ifndef ANALYTICS_EXPORTER_MQH
#define ANALYTICS_EXPORTER_MQH

// Stable contract shared with PythonAnalytics/src/schema.py.
#define ANALYTICS_SCHEMA_VERSION 1

enum AnalyticsOperatingMode
{
   MQL5_ONLY = 0,
   EXPORT_ONLY = 1,
   EXTERNAL_FILTER = 2,
   DRY_RUN_ANALYTICS = 3
};

struct ExternalAnalysisResult
{
   bool     available;
   double   qualityScore;
   string   modelVersion;
   string   decision;       // APPROVE, REJECT, REDUCE_RISK, NO_RESPONSE
   string   explanation;
   datetime generatedAt;
   double   riskMultiplier; // Only values in (0, 1] may be applied.
};

struct MarketSnapshot
{
   int             analyticsSchemaVersion;
   string          setupId;
   datetime        timestamp;
   string          symbol;
   datetime        brokerServerTime;
   ENUM_TIMEFRAMES entryTimeframe;
   ENUM_TIMEFRAMES trendTimeframe;
   double          bid;
   double          ask;
   double          spreadPoints;
   double          barOpen;
   double          barHigh;
   double          barLow;
   double          barClose;
   long            tickVolume;
   double          atrPoints;
   double          fastEma;
   double          slowEma;
   string          trendClassification;
   double          previousDayHigh;
   double          previousDayLow;
   double          asianSessionHigh;
   double          asianSessionLow;
   double          detectedSwingHigh;
   double          detectedSwingLow;
   string          sessionClassification;
};

struct SignalDecision
{
   int                    analyticsSchemaVersion;
   string                 setupId;
   datetime               timestamp;
   string                 symbol;
   string                 liquidityLevelType;
   double                 liquidityLevelPrice;
   string                 sweepDirection;
   double                 sweepExtreme;
   datetime               sweepConfirmationTime;
   string                 bosDirection;
   double                 brokenStructureLevel;
   double                 retestPrice;
   double                 retestDistancePoints;
   double                 confirmationOpen;
   double                 confirmationHigh;
   double                 confirmationLow;
   double                 confirmationClose;
   double                 confirmationBodyPoints;
   double                 confirmationUpperWickPoints;
   double                 confirmationLowerWickPoints;
   bool                   confirmationBullish;
   double                 proposedEntryPrice;
   double                 proposedStopLossPrice;
   double                 proposedTakeProfitPrice;
   double                 riskPoints;
   double                 rewardToRiskRatio;
   double                 calculatedPositionSize;
   string                 strategyState;
   bool                   signalAccepted;
   string                 rejectionReason;
   ExternalAnalysisResult externalAnalysis;
   bool                   externalDecisionApplied;
   double                 appliedRiskMultiplier;
};

struct TradeEvent
{
   int      analyticsSchemaVersion;
   string   setupId;
   datetime timestamp;
   string   symbol;
   ulong    tradeTicket;
   string   tradeEventType;       // OPENED, CLOSED, ORDER_REJECTED, MODIFIED
   string   finalTradeResult;     // WIN, LOSS, BREAKEVEN, OPEN, NOT_APPLICABLE
   double   profitLossMoney;
   double   profitLossR;
   double   maximumFavorableExcursionPoints;
   double   maximumAdverseExcursionPoints;
   double   slippagePoints;
   long     holdingDurationSeconds;
   string   exitReason;
   double   entryPrice;
   double   exitPrice;
   double   volume;
};

class IAnalyticsExporter
{
public:
   virtual bool Initialize(void) = 0;
   virtual void ExportMarketSnapshot(const MarketSnapshot &snapshot) = 0;
   virtual void ExportSignalDecision(const SignalDecision &decision) = 0;
   virtual void ExportTradeEvent(const TradeEvent &event) = 0;
   virtual void Shutdown(void) = 0;
};

class NullAnalyticsExporter : public IAnalyticsExporter
{
public:
   virtual bool Initialize(void) { return true; }
   virtual void ExportMarketSnapshot(const MarketSnapshot &snapshot) { }
   virtual void ExportSignalDecision(const SignalDecision &decision) { }
   virtual void ExportTradeEvent(const TradeEvent &event) { }
   virtual void Shutdown(void) { }
};

class CsvAnalyticsExporter : public IAnalyticsExporter
{
private:
   string m_directory;
   bool   m_commonFiles;
   bool   m_flushEachRecord;
   int    m_snapshotFile;
   int    m_decisionFile;
   int    m_tradeFile;
   bool   m_active;
   int    m_consecutiveFailures;

   string BoolText(const bool value)
   {
      return value ? "true" : "false";
   }

   string TimeText(const datetime value)
   {
      if(value <= 0)
         return "";
      return TimeToString(value, TIME_DATE | TIME_SECONDS);
   }

   int OpenOutputFile(const string fileName)
   {
      // Deliberately permit readers but not a second writer to the same stream.
      int flags = FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ;
      if(m_commonFiles)
         flags |= FILE_COMMON;

      ResetLastError();
      const int handle = FileOpen(m_directory + "\\" + fileName, flags, ',');
      if(handle == INVALID_HANDLE)
         PrintFormat("Analytics CSV open failed for %s (error %d)", fileName, GetLastError());
      return handle;
   }

   void RegisterWriteResult(const uint written, const string tableName)
   {
      if(written > 0)
      {
         m_consecutiveFailures = 0;
         return;
      }

      m_consecutiveFailures++;
      PrintFormat("Analytics CSV write failed for %s (error %d, failure %d)",
                  tableName, GetLastError(), m_consecutiveFailures);

      // Export must never control trading. Disable it after repeated failures.
      if(m_consecutiveFailures >= 3)
      {
         m_active = false;
         Print("Analytics CSV exporter disabled after repeated write failures; trading continues safely.");
      }
   }

public:
   CsvAnalyticsExporter(const string directory = "Analytics",
                        const bool commonFiles = false,
                        const bool flushEachRecord = true)
   {
      m_directory           = directory;
      m_commonFiles         = commonFiles;
      m_flushEachRecord     = flushEachRecord;
      m_snapshotFile        = INVALID_HANDLE;
      m_decisionFile        = INVALID_HANDLE;
      m_tradeFile           = INVALID_HANDLE;
      m_active              = false;
      m_consecutiveFailures = 0;
   }

   virtual bool Initialize(void)
   {
      const int commonFlag = m_commonFiles ? FILE_COMMON : 0;
      FolderCreate(m_directory, commonFlag);

      m_snapshotFile = OpenOutputFile("market_snapshots_v1.csv");
      m_decisionFile = OpenOutputFile("signal_decisions_v1.csv");
      m_tradeFile    = OpenOutputFile("trade_events_v1.csv");

      if(m_snapshotFile == INVALID_HANDLE ||
         m_decisionFile == INVALID_HANDLE ||
         m_tradeFile == INVALID_HANDLE)
      {
         Shutdown();
         return false;
      }

      bool headersWritten = true;
      if(FileSize(m_snapshotFile) == 0)
         headersWritten = FileWrite(m_snapshotFile,
                   "analytics_schema_version", "event_type", "setup_id", "timestamp",
                   "symbol", "broker_server_time", "entry_timeframe", "trend_timeframe",
                   "bid", "ask", "spread_points", "bar_open", "bar_high", "bar_low",
                   "bar_close", "tick_volume", "atr_points", "fast_ema", "slow_ema",
                   "trend_classification", "previous_day_high", "previous_day_low",
                   "asian_session_high", "asian_session_low", "detected_swing_high",
                   "detected_swing_low", "session_classification") > 0 && headersWritten;

      if(FileSize(m_decisionFile) == 0)
         headersWritten = FileWrite(m_decisionFile,
                   "analytics_schema_version", "event_type", "setup_id", "timestamp", "symbol",
                   "liquidity_level_type", "liquidity_level_price", "sweep_direction",
                   "sweep_extreme", "sweep_confirmation_time", "bos_direction",
                   "broken_structure_level", "retest_price", "retest_distance_points",
                   "confirmation_open", "confirmation_high", "confirmation_low",
                   "confirmation_close", "confirmation_body_points",
                   "confirmation_upper_wick_points", "confirmation_lower_wick_points",
                   "confirmation_bullish", "proposed_entry_price", "proposed_stop_loss_price",
                   "proposed_take_profit_price", "risk_points", "reward_to_risk_ratio",
                   "calculated_position_size", "strategy_state", "signal_accepted",
                   "rejection_reason", "external_available", "external_quality_score",
                   "external_model_version", "external_decision", "external_explanation",
                   "external_generated_at", "external_decision_applied", "applied_risk_multiplier") > 0 && headersWritten;

      if(FileSize(m_tradeFile) == 0)
         headersWritten = FileWrite(m_tradeFile,
                   "analytics_schema_version", "event_type", "setup_id", "timestamp", "symbol",
                   "trade_ticket", "trade_event_type", "final_trade_result",
                   "profit_loss_money", "profit_loss_r", "maximum_favorable_excursion_points",
                   "maximum_adverse_excursion_points", "slippage_points",
                   "holding_duration_seconds", "exit_reason", "entry_price", "exit_price", "volume") > 0 && headersWritten;

      if(!headersWritten)
      {
         PrintFormat("Analytics CSV header write failed (error %d)", GetLastError());
         Shutdown();
         return false;
      }

      FileSeek(m_snapshotFile, 0, SEEK_END);
      FileSeek(m_decisionFile, 0, SEEK_END);
      FileSeek(m_tradeFile, 0, SEEK_END);
      m_active = true;
      return true;
   }

   virtual void ExportMarketSnapshot(const MarketSnapshot &snapshot)
   {
      if(!m_active)
         return;

      ResetLastError();
      const uint written = FileWrite(m_snapshotFile,
         snapshot.analyticsSchemaVersion, "MARKET_SNAPSHOT", snapshot.setupId,
         TimeText(snapshot.timestamp), snapshot.symbol, TimeText(snapshot.brokerServerTime),
         EnumToString(snapshot.entryTimeframe), EnumToString(snapshot.trendTimeframe),
         snapshot.bid, snapshot.ask, snapshot.spreadPoints, snapshot.barOpen, snapshot.barHigh,
         snapshot.barLow, snapshot.barClose, snapshot.tickVolume, snapshot.atrPoints,
         snapshot.fastEma, snapshot.slowEma, snapshot.trendClassification,
         snapshot.previousDayHigh, snapshot.previousDayLow, snapshot.asianSessionHigh,
         snapshot.asianSessionLow, snapshot.detectedSwingHigh, snapshot.detectedSwingLow,
         snapshot.sessionClassification);
      RegisterWriteResult(written, "market_snapshots_v1");
      if(m_active && m_flushEachRecord)
         FileFlush(m_snapshotFile);
   }

   virtual void ExportSignalDecision(const SignalDecision &decision)
   {
      if(!m_active)
         return;

      ResetLastError();
      const uint written = FileWrite(m_decisionFile,
         decision.analyticsSchemaVersion, "SIGNAL_DECISION", decision.setupId,
         TimeText(decision.timestamp), decision.symbol, decision.liquidityLevelType,
         decision.liquidityLevelPrice, decision.sweepDirection, decision.sweepExtreme,
         TimeText(decision.sweepConfirmationTime), decision.bosDirection,
         decision.brokenStructureLevel, decision.retestPrice, decision.retestDistancePoints,
         decision.confirmationOpen, decision.confirmationHigh, decision.confirmationLow,
         decision.confirmationClose, decision.confirmationBodyPoints,
         decision.confirmationUpperWickPoints, decision.confirmationLowerWickPoints,
         BoolText(decision.confirmationBullish), decision.proposedEntryPrice,
         decision.proposedStopLossPrice, decision.proposedTakeProfitPrice, decision.riskPoints,
         decision.rewardToRiskRatio, decision.calculatedPositionSize, decision.strategyState,
         BoolText(decision.signalAccepted), decision.rejectionReason,
         BoolText(decision.externalAnalysis.available), decision.externalAnalysis.qualityScore,
         decision.externalAnalysis.modelVersion, decision.externalAnalysis.decision,
         decision.externalAnalysis.explanation, TimeText(decision.externalAnalysis.generatedAt),
         BoolText(decision.externalDecisionApplied), decision.appliedRiskMultiplier);
      RegisterWriteResult(written, "signal_decisions_v1");
      if(m_active && m_flushEachRecord)
         FileFlush(m_decisionFile);
   }

   virtual void ExportTradeEvent(const TradeEvent &event)
   {
      if(!m_active)
         return;

      ResetLastError();
      const uint written = FileWrite(m_tradeFile,
         event.analyticsSchemaVersion, "TRADE_EVENT", event.setupId, TimeText(event.timestamp),
         event.symbol, event.tradeTicket, event.tradeEventType, event.finalTradeResult,
         event.profitLossMoney, event.profitLossR, event.maximumFavorableExcursionPoints,
         event.maximumAdverseExcursionPoints, event.slippagePoints,
         event.holdingDurationSeconds, event.exitReason, event.entryPrice, event.exitPrice,
         event.volume);
      RegisterWriteResult(written, "trade_events_v1");
      if(m_active && m_flushEachRecord)
         FileFlush(m_tradeFile);
   }

   virtual void Shutdown(void)
   {
      if(m_snapshotFile != INVALID_HANDLE)
      {
         FileFlush(m_snapshotFile);
         FileClose(m_snapshotFile);
         m_snapshotFile = INVALID_HANDLE;
      }
      if(m_decisionFile != INVALID_HANDLE)
      {
         FileFlush(m_decisionFile);
         FileClose(m_decisionFile);
         m_decisionFile = INVALID_HANDLE;
      }
      if(m_tradeFile != INVALID_HANDLE)
      {
         FileFlush(m_tradeFile);
         FileClose(m_tradeFile);
         m_tradeFile = INVALID_HANDLE;
      }
      m_active = false;
   }
};

#endif
