#ifndef EXTERNAL_ANALYSIS_MQH
#define EXTERNAL_ANALYSIS_MQH

#include "AnalyticsExporter.mqh"

// Implementations must return immediately. Network adapters should perform I/O
// asynchronously (for example from OnTimer) and expose only their cached result here.
class IExternalAnalysisProvider
{
public:
   virtual bool Initialize(const int timeoutMs) = 0;
   virtual bool TryGetLatest(const string setupId, ExternalAnalysisResult &result) = 0;
   virtual void Shutdown(void) = 0;
};

class NullExternalAnalysisProvider : public IExternalAnalysisProvider
{
public:
   virtual bool Initialize(const int timeoutMs) { return timeoutMs > 0; }

   virtual bool TryGetLatest(const string setupId, ExternalAnalysisResult &result)
   {
      result.available       = false;
      result.qualityScore    = 0.0;
      result.modelVersion    = "";
      result.decision        = "NO_RESPONSE";
      result.explanation     = "No external provider configured";
      result.generatedAt     = 0;
      result.riskMultiplier  = 1.0;
      return false;
   }

   virtual void Shutdown(void) { }
};

enum ExternalFilterStatus
{
   EXTERNAL_NOT_USED = 0,
   EXTERNAL_VALID_APPROVE = 1,
   EXTERNAL_VALID_REJECT = 2,
   EXTERNAL_VALID_REDUCE_RISK = 3,
   EXTERNAL_INVALID_FALLBACK = 4
};

class ExternalAnalysisGuard
{
private:
   string m_expectedModelVersion;
   int    m_maxResponseAgeSeconds;

public:
   ExternalAnalysisGuard(const string expectedModelVersion = "",
                         const int maxResponseAgeSeconds = 30)
   {
      m_expectedModelVersion   = expectedModelVersion;
      m_maxResponseAgeSeconds  = maxResponseAgeSeconds > 0 ? maxResponseAgeSeconds : 1;
   }

   ExternalFilterStatus Apply(const bool filterEnabled,
                              const datetime decisionTime,
                              const ExternalAnalysisResult &external,
                              bool &signalAccepted,
                              double &riskMultiplier,
                              string &reason)
   {
      riskMultiplier = 1.0;
      if(!filterEnabled)
         return EXTERNAL_NOT_USED;

      // Fail open to the already-validated MQL5 rule decision. External analysis
      // can only reject or reduce risk; it can never turn a rejection into approval.
      if(!external.available || external.decision == "NO_RESPONSE")
      {
         reason = "EXTERNAL_NO_RESPONSE_MQL5_FALLBACK";
         return EXTERNAL_INVALID_FALLBACK;
      }

      if(m_expectedModelVersion == "")
      {
         reason = "EXTERNAL_EXPECTED_MODEL_VERSION_NOT_CONFIGURED_MQL5_FALLBACK";
         return EXTERNAL_INVALID_FALLBACK;
      }

      if(external.generatedAt <= 0 ||
         MathAbs((double)(decisionTime - external.generatedAt)) > m_maxResponseAgeSeconds)
      {
         reason = "EXTERNAL_STALE_MQL5_FALLBACK";
         return EXTERNAL_INVALID_FALLBACK;
      }

      if(external.modelVersion != m_expectedModelVersion)
      {
         reason = "EXTERNAL_MODEL_VERSION_MISMATCH_MQL5_FALLBACK";
         return EXTERNAL_INVALID_FALLBACK;
      }

      if(!MathIsValidNumber(external.qualityScore) ||
         external.qualityScore < 0.0 || external.qualityScore > 1.0)
      {
         reason = "EXTERNAL_MALFORMED_SCORE_MQL5_FALLBACK";
         return EXTERNAL_INVALID_FALLBACK;
      }

      if(external.decision == "APPROVE")
      {
         // Deliberately do not change signalAccepted.
         reason = "EXTERNAL_APPROVE_NO_RISK_CHANGE";
         return EXTERNAL_VALID_APPROVE;
      }

      if(external.decision == "REJECT")
      {
         signalAccepted = false;
         reason = "EXTERNAL_REJECT: " + external.explanation;
         return EXTERNAL_VALID_REJECT;
      }

      if(external.decision == "REDUCE_RISK")
      {
         if(!MathIsValidNumber(external.riskMultiplier) ||
            external.riskMultiplier <= 0.0 || external.riskMultiplier >= 1.0)
         {
            reason = "EXTERNAL_INVALID_RISK_MULTIPLIER_MQL5_FALLBACK";
            return EXTERNAL_INVALID_FALLBACK;
         }
         riskMultiplier = external.riskMultiplier;
         reason = "EXTERNAL_REDUCE_RISK: " + external.explanation;
         return EXTERNAL_VALID_REDUCE_RISK;
      }

      reason = "EXTERNAL_UNKNOWN_DECISION_MQL5_FALLBACK";
      return EXTERNAL_INVALID_FALLBACK;
   }
};

#endif
