import 'package:flutter/material.dart';

class ResultsScreen extends StatelessWidget {
  final Map<String, dynamic> result;

  ResultsScreen({Key? key, required this.result}) : super(key: key);

  Color _riskColor(String level) {
    switch (level) {
      case "CRITICAL": return const Color(0xFFEF4444);
      case "HIGH":     return const Color(0xFFF97316);
      case "MEDIUM":   return const Color(0xFFEAB308);
      default:         return const Color(0xFF22C55E);
    }
  }

  String _riskIcon(String level) {
    switch (level) {
      case "CRITICAL": return "🚨";
      case "HIGH":     return "⚠️";
      case "MEDIUM":   return "⚡";
      default:         return "✅";
    }
  }

  @override
  Widget build(BuildContext context) {
    final score       = (result["threat_score"] as num?)?.toDouble() ?? 0;
    final level       = (result["risk_level"] ?? "UNKNOWN").toString();
    final verdict     = (result["verdict"] ?? "").toString();
    final payload     = (result["decoded_payload"] ?? "").toString();
    final payloadType = (result["payload_type"] ?? "").toString();
    final recommendation = (result["recommendation"] ?? "").toString();
    final color       = _riskColor(level);
    final icon        = _riskIcon(level);

    final analysis = (result["analysis"] as Map?) ?? {};
    final upi   = analysis["upi_analysis"]  as Map? ?? {};
    final hf    = analysis["huggingface_ai"] as Map? ?? {};
    final whois = analysis["whois_api"]      as Map? ?? {};
    final vt    = analysis["virustotal_api"] as Map? ?? {};

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text(
          "🛡️ Threat Report",
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [

            // Score Circle
            Container(
              width: 150,
              height: 150,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: color, width: 4),
                color: color.withOpacity(0.08),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(icon, style: const TextStyle(fontSize: 32)),
                  Text(
                    score.toStringAsFixed(1),
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  const Text(
                    "/ 100",
                    style: TextStyle(fontSize: 12, color: Colors.white54),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Level
            Text(
              level,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 8),

            // Badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white10,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                payloadType,
                style: const TextStyle(fontSize: 12, color: Colors.white54),
              ),
            ),
            const SizedBox(height: 16),

            _card("Verdict", verdict, borderColor: color, textColor: color),
            const SizedBox(height: 8),
            _card("Recommendation", recommendation),
            const SizedBox(height: 8),
            _card("Decoded Payload", payload),
            const SizedBox(height: 8),

            // UPI
            if (upi["is_upi"] == true) ...[
              _card(
                "💳 UPI Analysis",
                "VPA: ${upi["payee_vpa"] ?? "Unknown"}\n"
                "Amount: Rs.${upi["amount"] ?? 0}\n"
                "Action: ${upi["actual_action"] ?? "DEBIT"}\n"
                "Risk Score: ${upi["upi_risk_score"] ?? 0}/100",
              ),
              const SizedBox(height: 8),
              if ((upi["risks"] as List?)?.isNotEmpty == true)
                ...((upi["risks"] as List).map((r) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _card(
                    "⚠️ ${r["severity"]}: ${r["type"]}",
                    r["detail"] ?? "",
                    borderColor: const Color(0xFFEF4444),
                    textColor: const Color(0xFFEF4444),
                  ),
                ))),
            ],

            // HF
            if (hf.isNotEmpty && hf["model"] != "skipped") ...[
              _card(
                "🧠 AI Analysis",
                "Model: ${hf["model"] ?? "Heuristic"}\n"
                "Phishing: ${(((hf["phishing_probability"] ?? 0) as num) * 100).toStringAsFixed(1)}%\n"
                "Is Phishing: ${hf["is_phishing"] ?? false}",
              ),
              const SizedBox(height: 8),
            ],

            // WHOIS
            if (whois.isNotEmpty && whois["domain"] != null) ...[
              _card(
                "🌐 WHOIS",
                "Domain: ${whois["domain"]}\n"
                "Age: ${whois["age_days"]} days\n"
                "Zero-Day: ${whois["is_zero_day"]}\n"
                "Risk: ${whois["risk_score"]}",
              ),
              const SizedBox(height: 8),
            ],

            // VT
            if (vt.isNotEmpty && vt["service"] != "skipped") ...[
              _card(
                "🦠 VirusTotal",
                "Malicious: ${vt["malicious_votes"] ?? 0}\n"
                "Flagged: ${vt["flagged"] ?? false}\n"
                "Score: ${vt["threat_score"] ?? 0}",
              ),
              const SizedBox(height: 8),
            ],

            const SizedBox(height: 16),

            // Scan Again Button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  "Scan Another",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _card(
    String title,
    String body, {
    Color? borderColor,
    Color? textColor,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor ?? Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Color(0xFF6366F1),
              fontWeight: FontWeight.bold,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: TextStyle(
              color: textColor ?? Colors.white70,
              fontSize: 12,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }
}