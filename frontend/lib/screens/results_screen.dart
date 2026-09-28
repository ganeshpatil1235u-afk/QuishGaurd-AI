import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class ResultsScreen extends StatefulWidget {
  final Map<String, dynamic> result;

  const ResultsScreen({Key? key, required this.result}) : super(key: key);

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  Map<String, dynamic> get result => widget.result;

  static const int _autoRedirectSeconds = 3;
  Timer? _timer;
  int _countdown = _autoRedirectSeconds;
  bool _autoRedirectActive = false;

  String get _payload => (result["decoded_payload"] ?? "").toString();
  String get _level => (result["risk_level"] ?? "UNKNOWN").toString();
  bool get _isUpi => (result["payload_type"] ?? "") == "UPI";

  // Only hand off to PhonePe when the backend says SAFE (never for MEDIUM+)
  bool get _canRedirect =>
      _isUpi && _level == "SAFE" && result["redirect_to_phonepe"] == true;

  @override
  void initState() {
    super.initState();
    if (_canRedirect) {
      _autoRedirectActive = true;
      _timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) return;
        if (_countdown <= 1) {
          t.cancel();
          setState(() => _autoRedirectActive = false);
          _openPhonePe();
        } else {
          setState(() => _countdown--);
        }
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _cancelAutoRedirect() {
    _timer?.cancel();
    setState(() => _autoRedirectActive = false);
  }

  // Opens PhonePe with the scanned UPI payment request.
  // 1) phonepe://pay?...  targets PhonePe directly
  // 2) upi://pay?...      Android app chooser fallback
  Future<void> _openPhonePe() async {
    final query = Uri.tryParse(_payload)?.query ?? "";
    if (query.isEmpty) {
      _toast("Invalid UPI payload");
      return;
    }

    final attempts = <Uri>[
      Uri.parse("phonepe://pay?$query"),
      Uri.parse("upi://pay?$query"),
    ];

    for (final uri in attempts) {
      try {
        final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
        if (ok) return;
      } catch (_) {
        // try next
      }
    }
    _toast("Could not open PhonePe. Is it installed?");
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: const Color(0xFFEF4444)),
    );
  }

  Widget _phonePeSection(Color color) {
    const phonePePurple = Color(0xFF5F259F);

    if (_canRedirect) {
      return Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _openPhonePe,
              icon: const Icon(Icons.open_in_new),
              label: Text(
                _autoRedirectActive
                    ? "Opening PhonePe in $_countdown..."
                    : "Pay with PhonePe",
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: phonePePurple,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          if (_autoRedirectActive)
            TextButton(
              onPressed: _cancelAutoRedirect,
              child: const Text("Cancel",
                  style: TextStyle(color: Colors.white54)),
            ),
          const SizedBox(height: 8),
        ],
      );
    }

    // MEDIUM: allow an explicit, deliberate override. HIGH/CRITICAL: blocked.
    if (_isUpi && _level == "MEDIUM") {
      return Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: _openPhonePe,
              style: OutlinedButton.styleFrom(
                foregroundColor: color,
                side: BorderSide(color: color),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text("Proceed to PhonePe anyway (at your risk)"),
            ),
          ),
          const SizedBox(height: 8),
        ],
      );
    }
    return const SizedBox.shrink();
  }

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
                "Payee: ${upi["payee_name"] ?? "Unknown"}\n"
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

            _card(
              "🔧 Debug",
              result["engine_version"] != null
                  ? "Backend engine: ${result["engine_version"]}"
                  : "⚠️ OLD BACKEND: this phone is NOT using your updated code",
              borderColor: result["engine_version"] != null
                  ? null
                  : const Color(0xFFEF4444),
              textColor: result["engine_version"] != null
                  ? null
                  : const Color(0xFFEF4444),
            ),
            const SizedBox(height: 12),

            // PhonePe redirect (SAFE only) / override (MEDIUM only)
            _phonePeSection(color),

            // Scan Again Button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  foregroundColor: Colors.white,
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
